"""Benchmark data injection — loads event corpus into PostgreSQL.

Reads YAML event definitions and JSON fixture files, then inserts
topics, sources, topic_sources links, and content_items directly
into the database with historical captured_at timestamps preserved.

All benchmark records carry labels: {"benchmark": true} for easy cleanup.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import asyncpg
import structlog
import yaml

from .settings import settings

log = structlog.get_logger(__name__)

BENCHMARK_LABELS = json.dumps({
    "benchmark": True,
    "classification": "OPEN",
    "domain": "benchmark",
    "owner_org": "anveshak",
})

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

SQL_CLEANUP = """
    DELETE FROM topics WHERE labels->>'benchmark' = 'true';
"""

SQL_CLEANUP_SOURCES = """
    DELETE FROM sources WHERE labels->>'benchmark' = 'true';
"""

SQL_INSERT_TOPIC = """
    INSERT INTO topics (
        id, name, keywords, languages, credibility_min, signal_threshold,
        status, clip_categories, scheduled_report_cron, scheduled_report_type,
        created_at, updated_at, labels
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
    ON CONFLICT (id) DO NOTHING
"""

SQL_INSERT_SOURCE = """
    INSERT INTO sources (
        id, name, url_or_handle, platform, credibility_score,
        is_active, created_at, updated_at, labels
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
    ON CONFLICT (id) DO NOTHING
"""

SQL_LINK_TOPIC_SOURCE = """
    INSERT INTO topic_sources (topic_id, source_id)
    VALUES ($1, $2)
    ON CONFLICT (topic_id, source_id) DO NOTHING
"""

SQL_INSERT_CONTENT = """
    INSERT INTO content_items (
        id, topic_id, source_id, raw_text, clean_text, language,
        content_hash, url, captured_at, credibility_score_at_capture,
        created_at, updated_at, labels
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
    ON CONFLICT(content_hash) DO NOTHING
    RETURNING id
"""


def _compute_hash(text: str) -> str:
    """SHA-256 of normalised text (lowercase + collapsed whitespace)."""
    normalised = " ".join(text.lower().split())
    return hashlib.sha256(normalised.encode()).hexdigest()


def _make_source_id(platform: str, source_name: str) -> str:
    """Deterministic source ID from platform + name."""
    raw = f"benchmark-{platform}-{source_name}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))


async def cleanup(pool: asyncpg.Pool) -> int:
    """Remove all benchmark data from the database and ARQ job cache."""
    import redis.asyncio as aioredis

    async with pool.acquire() as conn:
        # content_items cascade from topics (via FK topic_id)
        result = await conn.execute(SQL_CLEANUP)
        topic_count = int(result.split()[-1]) if result else 0
        result = await conn.execute(SQL_CLEANUP_SOURCES)
        source_count = int(result.split()[-1]) if result else 0

    # Flush ARQ job results so re-runs don't get deduplicated.
    # In production this never happens — content_item IDs are unique UUIDs
    # generated per scrape. The benchmark reuses deterministic IDs across runs.
    r = aioredis.from_url(settings.redis_url)
    job_keys = [k async for k in r.scan_iter("arq:job:*")]
    if job_keys:
        await r.delete(*job_keys)
    await r.aclose()

    log.info(
        "benchmark.cleanup_complete",
        topics_deleted=topic_count,
        sources_deleted=source_count,
        arq_jobs_flushed=len(job_keys),
    )
    return topic_count + source_count


async def inject_event(
    pool: asyncpg.Pool,
    event_path: Path,
    corpus_dir: Path,
) -> dict[str, Any]:
    """Inject a single event (topic + sources + content) into the database.

    Returns metadata about what was injected.
    """
    with open(event_path) as f:
        event = yaml.safe_load(f)

    event_id = event["id"]
    topic_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"benchmark-topic-{event_id}"))
    now = datetime.now(UTC)

    async with pool.acquire() as conn:
        # 1. Create topic
        await conn.execute(
            SQL_INSERT_TOPIC,
            topic_id,
            f"[BENCHMARK] {event['name']}",
            event["keywords"],
            event.get("languages", ["en"]),
            0.0,  # credibility_min
            settings.signal_threshold,
            "active",
            [],  # clip_categories
            None,  # scheduled_report_cron
            None,  # scheduled_report_type
            now,
            now,
            BENCHMARK_LABELS,
        )

        # 2. Create sources and link to topic
        source_ids: dict[str, str] = {}
        for src in event["sources"]:
            source_name = src["source_name"]
            platform = src["platform"]
            source_id = _make_source_id(platform, source_name)
            source_ids[src["fixture"]] = source_id

            await conn.execute(
                SQL_INSERT_SOURCE,
                source_id,
                f"[BENCHMARK] {source_name}",
                src.get("url", f"benchmark://{platform}/{source_name}"),
                platform,
                src.get("credibility", 50.0),
                True,
                now,
                now,
                BENCHMARK_LABELS,
            )

            await conn.execute(SQL_LINK_TOPIC_SOURCE, topic_id, source_id)

        # 3. Insert content items from fixtures
        fixtures_dir = corpus_dir / "fixtures"
        items_inserted = 0

        for src in event["sources"]:
            fixture_path = fixtures_dir / src["fixture"]
            if not fixture_path.exists():
                log.warning(
                    "benchmark.fixture_missing",
                    event=event_id,
                    fixture=src["fixture"],
                )
                continue

            with open(fixture_path) as f:
                fixture = json.load(f)

            content_hash = _compute_hash(fixture["clean_text"])
            content_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"benchmark-{content_hash}"))
            # Use recent timestamps so clustering window doesn't exclude them.
            # Shift captured_at to be within the last 7 days, preserving relative order.
            original_captured = datetime.fromisoformat(fixture["captured_at"])
            # Map all sources for this event into last 7 days relative to now
            event_earliest = datetime.fromisoformat(event["earliest_osint_signal"])
            offset_from_earliest = (original_captured - event_earliest).total_seconds()
            # Place earliest signal at 5 days ago, preserve relative offsets
            from datetime import timedelta
            captured_at = now - timedelta(days=5) + timedelta(seconds=offset_from_earliest)
            source_id = source_ids[src["fixture"]]

            result = await conn.fetchrow(
                SQL_INSERT_CONTENT,
                content_id,
                topic_id,
                source_id,
                fixture["raw_text"],
                fixture["clean_text"],
                fixture.get("language", "en"),
                content_hash,
                fixture.get("url", ""),
                captured_at,
                src.get("credibility", 50.0),
                now,
                now,
                BENCHMARK_LABELS,
            )
            if result:
                items_inserted += 1

    log.info(
        "benchmark.event_injected",
        event_id=event_id,
        topic_id=topic_id,
        sources=len(event["sources"]),
        items_inserted=items_inserted,
    )
    return {
        "event_id": event_id,
        "topic_id": topic_id,
        "items_inserted": items_inserted,
        "sources": len(event["sources"]),
    }


async def inject_all(pool: asyncpg.Pool, corpus_dir: Path | None = None) -> list[dict]:
    """Inject all events from the corpus directory."""
    if corpus_dir is None:
        corpus_dir = Path(settings.corpus_dir)

    events_dir = corpus_dir / "events"
    event_files = sorted(events_dir.glob("evt_*.yaml"))

    if not event_files:
        log.error("benchmark.no_events_found", dir=str(events_dir))
        return []

    results = []
    for event_path in event_files:
        result = await inject_event(pool, event_path, corpus_dir)
        results.append(result)

    total_items = sum(r["items_inserted"] for r in results)
    log.info(
        "benchmark.injection_complete",
        events=len(results),
        total_items=total_items,
    )
    return results
