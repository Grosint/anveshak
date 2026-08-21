"""Database helpers for vision service — asyncpg connection pool and SQL operations.

All SQL is defined as module-level constants (AGENTS.md patterns + testability).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Optional

import asyncpg
import structlog
from anveshak.db import DBConnection

from ..settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_GET_MEDIA_ASSET = """
    SELECT ma.id, ma.content_item_id, ma.asset_type, ma.storage_path,
           ma.content_hash,
           ci.topic_id
    FROM media_assets ma
    JOIN content_items ci ON ci.id = ma.content_item_id
    WHERE ma.id = $1
"""

SQL_GET_TOPIC_CLIP_CATEGORIES = """
    SELECT clip_categories FROM topics WHERE id = $1
"""

SQL_UPDATE_MEDIA_ASSET_EXIF_PHASH = """
    UPDATE media_assets
    SET exif_data = $1::jsonb,
        phash     = $2
    WHERE id = $3
"""

SQL_INSERT_VISION_RESULT = """
    INSERT INTO vision_results (
        id, media_asset_id,
        yolo_detections, clip_labels,
        deepfake_score, deepfake_model,
        synthetic_probability,
        processed_at, labels
    )
    VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, $7, $8,
            '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT (media_asset_id) DO UPDATE
    SET yolo_detections     = EXCLUDED.yolo_detections,
        clip_labels         = EXCLUDED.clip_labels,
        deepfake_score      = EXCLUDED.deepfake_score,
        deepfake_model      = EXCLUDED.deepfake_model,
        synthetic_probability = EXCLUDED.synthetic_probability,
        processed_at        = EXCLUDED.processed_at
"""

SQL_TAG_CONTENT_ITEM_LABELS = """
    UPDATE content_items
    SET labels = labels || $1::jsonb,
        updated_at = $2
    WHERE id = $3
"""

SQL_GET_MEDIA_ASSETS_BY_PHASH_RANGE = """
    SELECT ma.id, ma.content_item_id, ma.storage_path,
           ma.content_hash, ma.asset_type,
           ci.url, ci.topic_id,
           BIT_COUNT(ma.phash # $1::bigint) AS hamming_distance
    FROM media_assets ma
    JOIN content_items ci ON ci.id = ma.content_item_id
    WHERE ma.phash IS NOT NULL
      AND BIT_COUNT(ma.phash # $1::bigint) <= $2
    ORDER BY BIT_COUNT(ma.phash # $1::bigint)
    LIMIT 20
"""

SQL_GET_VISION_RESULTS_FOR_CONTENT = """
    SELECT vr.id, vr.media_asset_id, vr.yolo_detections, vr.clip_labels,
           vr.deepfake_score, vr.deepfake_model, vr.synthetic_probability,
           vr.processed_at,
           ma.storage_path, ma.asset_type, ma.exif_data, ma.phash, ma.content_hash
    FROM vision_results vr
    JOIN media_assets ma ON ma.id = vr.media_asset_id
    JOIN content_items ci ON ci.id = ma.content_item_id
    WHERE ci.id = $1
"""

SQL_GET_EXPIRED_MEDIA_ASSETS = """
    SELECT ma.id, ma.storage_path
    FROM media_assets ma
    JOIN vision_results vr ON vr.media_asset_id = ma.id
    WHERE ma.created_at < $1
      AND ma.storage_path IS NOT NULL
    LIMIT 100
"""

SQL_CLEAR_MEDIA_STORAGE_PATH = """
    UPDATE media_assets SET storage_path = NULL WHERE id = $1
"""

# ---------------------------------------------------------------------------
# Connection pool lifecycle
# ---------------------------------------------------------------------------


async def create_pool() -> asyncpg.Pool:
    from anveshak.db import create_db_pool

    return await create_db_pool(settings.postgres_url)


async def get_media_asset(conn: DBConnection, media_asset_id: str) -> Optional[asyncpg.Record]:
    return await conn.fetchrow(SQL_GET_MEDIA_ASSET, media_asset_id)


async def get_topic_clip_categories(conn: DBConnection, topic_id: str) -> list[str]:
    row = await conn.fetchrow(SQL_GET_TOPIC_CLIP_CATEGORIES, topic_id)
    return list(row["clip_categories"]) if row and row["clip_categories"] else []


async def update_media_asset_exif_phash(
    conn: DBConnection,
    media_asset_id: str,
    exif_data: Optional[dict],
    phash: Optional[int],
) -> None:
    exif_json = json.dumps(exif_data or {})
    await conn.execute(SQL_UPDATE_MEDIA_ASSET_EXIF_PHASH, exif_json, phash, media_asset_id)


async def insert_vision_result(
    conn: DBConnection,
    media_asset_id: str,
    yolo_detections: list[dict],
    clip_labels: list[dict],
    # Optional, not float: None is the error signal for a score that could not be
    # computed. AGENTS.md rule 7 plus
    # .agents/skills/learned/references/deepfake-none-error-signal.md.
    deepfake_score: Optional[float],
    deepfake_model: str,
    synthetic_probability: Optional[float],
) -> str:
    """Insert or update vision_results row. Returns the result id."""
    result_id = str(uuid.uuid4())
    await conn.execute(
        SQL_INSERT_VISION_RESULT,
        result_id,
        media_asset_id,
        json.dumps(yolo_detections),
        json.dumps(clip_labels),
        deepfake_score,
        deepfake_model,
        synthetic_probability,
        datetime.now(UTC),
    )
    return result_id


async def tag_content_item(
    conn: DBConnection,
    content_item_id: str,
    extra_labels: dict,
) -> None:
    """Merge extra_labels into content_items.labels JSONB (criteria 4.11)."""
    await conn.execute(
        SQL_TAG_CONTENT_ITEM_LABELS,
        json.dumps(extra_labels),
        datetime.now(UTC),
        content_item_id,
    )


async def reverse_search_by_phash(
    conn: DBConnection,
    phash: int,
    threshold: int,
) -> list[asyncpg.Record]:
    """Find near-duplicate media assets by Hamming distance on pHash."""
    return await conn.fetch(SQL_GET_MEDIA_ASSETS_BY_PHASH_RANGE, phash, threshold)


async def get_vision_results_for_content(
    conn: DBConnection,
    content_item_id: str,
) -> list[asyncpg.Record]:
    return await conn.fetch(SQL_GET_VISION_RESULTS_FOR_CONTENT, content_item_id)


async def get_expired_media_assets(
    conn: DBConnection,
    cutoff: datetime,
) -> list[asyncpg.Record]:
    """Fetch media assets older than cutoff that have completed vision analysis."""
    return await conn.fetch(SQL_GET_EXPIRED_MEDIA_ASSETS, cutoff)


async def clear_media_storage_path(
    conn: DBConnection,
    media_asset_id: str,
) -> None:
    """Set storage_path to NULL after file deletion (preserves metadata)."""
    await conn.execute(SQL_CLEAR_MEDIA_STORAGE_PATH, media_asset_id)


# ---------------------------------------------------------------------------
# Stub content items for standalone (non-topic) vision requests
#
# jobs.py imports this when a YouTube analysis request arrives without a
# content_item_id. It previously did `from .db import
# get_or_create_stub_content_item`, but the function only existed in the API
# service's own db module, so that path raised ImportError at runtime. Services
# own their DB access, so the vision service carries its own copy rather than
# importing across a service boundary.
# ---------------------------------------------------------------------------

_MANUAL_SOURCE_ID = "00000000-0000-0000-0000-000000000001"

SQL_UPSERT_MANUAL_SOURCE = """
    INSERT INTO sources (id, name, url_or_handle, platform, credibility_score,
                         auto_score_enabled, labels)
    VALUES ($1, 'Manual Upload', 'manual://upload', 'manual', 50.0, false,
            '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT (id) DO NOTHING
"""

SQL_INSERT_STUB_CONTENT_ITEM = """
    INSERT INTO content_items (id, source_id, raw_text, clean_text, content_hash, topic_id, labels)
    VALUES ($1, $2, $3, $3, $4, $5,
            '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT (content_hash) DO NOTHING
    RETURNING id
"""

SQL_GET_STUB_CONTENT_ITEM_BY_HASH = """
    SELECT id FROM content_items WHERE content_hash = $1
"""

SQL_UPSERT_TOPIC_CONTENT_ITEM = """
    INSERT INTO topic_content_items (topic_id, content_item_id, similarity_score, assigned_at)
    VALUES ($1, $2, 1.0, NOW())
    ON CONFLICT (topic_id, content_item_id) DO NOTHING
"""


async def get_or_create_stub_content_item(
    conn: DBConnection,
    content_hash: str,
    filename: str,
    topic_id: Optional[str] = None,
) -> str:
    """Return content_item.id for an ad-hoc vision request.

    Creates a 'manual-upload' source stub and a minimal content_item so that
    media_assets.content_item_id (NOT NULL FK) is always satisfied.
    """
    await conn.execute(SQL_UPSERT_MANUAL_SOURCE, _MANUAL_SOURCE_ID)

    stub_text = f"[manual upload: {filename}]"
    stub_hash = hashlib.sha256(f"manual:{content_hash}".encode()).hexdigest()
    stub_id = str(uuid.uuid4())

    row = await conn.fetchrow(
        SQL_INSERT_STUB_CONTENT_ITEM,
        stub_id,
        _MANUAL_SOURCE_ID,
        stub_text,
        stub_hash,
        topic_id,
    )
    if row:
        content_item_id = str(row["id"])
    else:
        # ON CONFLICT: fetch existing. Reachable as None if the conflicting row
        # was deleted between the insert and this read (retention purge), so fail
        # loudly instead of raising an opaque TypeError on the subscript.
        existing = await conn.fetchrow(SQL_GET_STUB_CONTENT_ITEM_BY_HASH, stub_hash)
        if existing is None:
            raise RuntimeError(f"stub content item vanished after ON CONFLICT: hash={stub_hash}")
        content_item_id = str(existing["id"])

    if topic_id:
        await conn.execute(SQL_UPSERT_TOPIC_CONTENT_ITEM, topic_id, content_item_id)

    return content_item_id
