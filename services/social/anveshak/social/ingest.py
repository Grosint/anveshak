"""Content ingestion for social adapters.

All four adapters (Telegram, Reddit, Bluesky, X) call ingest_raw_item() to
insert a RawItem into content_items and enqueue the analyse_content ARQ job.
This is the same pipeline as the scraper — social content is not special.

Criteria 3.4: raw items from all adapters → same content_items table.
Criteria 1.5 / 3.4: ON CONFLICT(content_hash) DO NOTHING dedup.
Criteria 4.2: social adapters download media attachments (raw.media_urls).
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import structlog
from anveshak.media.downloader import download_media_asset
from arq import ArqRedis

from .adapters.base import RawItem
from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL — module-level constants (patterns.md convention)
# ---------------------------------------------------------------------------

SQL_GET_SOURCE_BY_HANDLE = """
    SELECT id, credibility_score
    FROM sources
    WHERE url_or_handle = $1 AND platform = $2 AND is_active = TRUE
    LIMIT 1
"""

SQL_INSERT_CONTENT = """
    INSERT INTO content_items (
        id, topic_id, source_id, raw_text, clean_text, language,
        content_hash, url, captured_at, credibility_score_at_capture,
        created_at, updated_at, labels,
        forwarded_from_channel_id, forwarded_from_channel_name, org_id
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
    ON CONFLICT(content_hash) DO NOTHING
    RETURNING id
"""

SQL_INSERT_MEDIA_ASSET = """
    INSERT INTO media_assets (
        id, content_item_id, asset_type, storage_path, content_hash, labels
    )
    VALUES ($1, $2, $3, $4, $5,
            '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT (content_hash) DO NOTHING
"""

SQL_GET_MEDIA_ASSET_BY_HASH = "SELECT id FROM media_assets WHERE content_hash = $1"

_LABELS_TEMPLATE = '{{"classification":"OPEN","domain":"social","owner_org":"anveshak","source_id":"{adapter_id}"}}'


# ---------------------------------------------------------------------------
# Helpers — same logic as scraper/normalise.py (no shared dep to avoid coupling)
# ---------------------------------------------------------------------------


def _normalise(text: str) -> str:
    """Lowercase and collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower()).strip()


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


async def ingest_raw_item(
    raw: RawItem,
    topic_id: str,
    pool: asyncpg.Pool,
    arq_pool: ArqRedis,
    adapter_id: str,
    *,
    org_id: str | None = None,
) -> bool:
    """Normalise a RawItem, insert into content_items, enqueue analyse_content.

    Args:
        raw:        RawItem yielded by an adapter.
        topic_id:   The topic being monitored.
        pool:       asyncpg connection pool.
        arq_pool:   ARQ Redis pool for enqueuing the NLP job.
        adapter_id: Adapter identifier (e.g. "reddit-v1") — recorded in labels.

    Returns:
        True  — new row inserted.
        False — content_hash already existed (dedup hit, no insert, no job).
    """
    clean_text = _normalise(raw.raw_text)
    if not clean_text:
        log.warning("social.ingest.empty_text", url=raw.url, platform=raw.platform)
        return False

    # RawItem owns the dedup key so a platform with a durable ID (YouTube video
    # or comment) can opt out of text hashing via stable_id. Everything else
    # falls through to the normalised-text hash RawItem computes by default.
    content_hash = raw.content_hash()

    # Look up source row by handle + platform
    async with pool.acquire() as conn:
        source_row = await conn.fetchrow(SQL_GET_SOURCE_BY_HANDLE, raw.source_handle, raw.platform)
        if source_row is None:
            log.warning(
                "social.ingest.unknown_source",
                handle=raw.source_handle,
                platform=raw.platform,
            )
            return False

        source_id: str = source_row["id"]
        credibility_score: float = source_row["credibility_score"]

        now = datetime.now(UTC)
        content_item_id = str(uuid.uuid4())

        # Build labels dict — engagement, author, reply metadata stored in JSONB
        labels_dict: dict[str, Any] = {
            "classification": "OPEN",
            "domain": "social",
            "owner_org": "anveshak",
            "source_id": adapter_id,
        }
        if raw.engagement:
            labels_dict["engagement"] = raw.engagement
        if raw.author_id:
            labels_dict["author_id"] = raw.author_id
        if raw.author_handle:
            labels_dict["author_handle"] = raw.author_handle
        if raw.reply_to_id:
            labels_dict["reply_to_id"] = raw.reply_to_id
        labels = json.dumps(labels_dict)

        result = await conn.fetchrow(
            SQL_INSERT_CONTENT,
            content_item_id,
            topic_id,
            source_id,
            raw.raw_text,  # raw_text — untouched
            clean_text,  # clean_text — normalised
            raw.language or "en",  # language — adapter may pre-detect or leave for NLP
            content_hash,
            raw.url,
            raw.captured_at,
            credibility_score,  # snapshot at ingest time (not FK — criteria 1.6)
            now,
            now,
            labels,
            raw.forwarded_from_channel_id,  # Telegram Level 2 discovery
            raw.forwarded_from_channel_name,  # Telegram Level 2 discovery
            org_id,  # $16 — org_id for multi-tenancy
        )

    if result is None:
        # ON CONFLICT(content_hash) DO NOTHING — duplicate, no row returned
        log.debug(
            "social.ingest.dedup",
            content_hash=content_hash,
            platform=raw.platform,
        )
        return False

    content_item_id = result["id"]

    # New row — enqueue NLP analysis job
    await arq_pool.enqueue_job("analyse_content", content_item_id, _queue_name="arq:analyst")
    log.info(
        "social.ingest.inserted",
        content_item_id=content_item_id,
        platform=raw.platform,
        content_hash=content_hash,
    )

    # Phase 4: download media attachments (criteria 4.2)
    if raw.media_urls:
        await _download_media_attachments(
            media_urls=raw.media_urls,
            topic_id=topic_id,
            content_item_id=content_item_id,
            pool=pool,
            arq_pool=arq_pool,
        )

    return True


async def _download_media_attachments(
    media_urls: list[str],
    topic_id: str,
    content_item_id: str,
    pool: asyncpg.Pool,
    arq_pool: ArqRedis,
) -> None:
    """Download media attachments from a social post, create media_assets rows.

    Criteria 4.2: social adapters download media → same storage path pattern.
    Criteria 4.3–4.4: media_assets rows with content_hash of raw bytes.
    Never crashes ingest — all errors caught and logged.
    """
    for media_url in media_urls:
        try:
            dl = await download_media_asset(
                url=media_url,
                topic_id=topic_id,
                storage_root=Path(settings.media_storage_root),
                max_size_mb=settings.media_max_size_mb,
                timeout_s=30,
            )
            if dl is None:
                continue

            async with pool.acquire() as conn:
                await conn.execute(
                    SQL_INSERT_MEDIA_ASSET,
                    str(uuid.uuid4()),
                    content_item_id,
                    dl.asset_type,
                    dl.storage_path,
                    dl.content_hash,
                )
                row = await conn.fetchrow(SQL_GET_MEDIA_ASSET_BY_HASH, dl.content_hash)

            if row:
                await arq_pool.enqueue_job(
                    "run_vision_analysis", row["id"], _queue_name="arq:vision"
                )
                log.debug(
                    "social.ingest.vision_dispatched",
                    media_asset_id=row["id"],
                    asset_type=dl.asset_type,
                )

        except Exception as exc:
            log.debug(
                "social.ingest.media_download_failed",
                url=media_url,
                error=str(exc),
            )
