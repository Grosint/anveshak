"""Backfill ARQ job: geocode existing extracted_entities.

Processes GPE/LOC/FAC entities not yet in geocoded_locations table.
Runs in batches for memory safety. Idempotent — safe to replay.
"""

from __future__ import annotations

import structlog

from .geocoding import geocode_entities, normalize_entity_text
from .geocoding_cache import geocode_cache_set
from .geocoding_db import upsert_geocoded_location

log = structlog.get_logger(__name__)

_BATCH_SIZE = 500

SQL_BACKFILL_ENTITIES = """
    SELECT DISTINCT LOWER(ee.entity_text) AS entity_text, ee.entity_type
    FROM extracted_entities ee
    WHERE ee.entity_type IN ('GPE', 'LOC', 'FAC')
      AND NOT EXISTS (
          SELECT 1 FROM geocoded_locations gl
          WHERE gl.entity_text_normalized = LOWER(ee.entity_text)
            AND gl.entity_type = ee.entity_type
      )
    ORDER BY entity_text
    LIMIT $1 OFFSET $2
"""

SQL_UPSERT_UNRESOLVED = """
    INSERT INTO geocoded_locations (
        entity_text_normalized, entity_type,
        latitude, longitude, geocode_confidence, geocode_source,
        geocoded_at, labels
    ) VALUES ($1, $2, 0.0, 0.0, 0.0, 'unresolved', NOW(), '{}'::jsonb)
    ON CONFLICT (entity_text_normalized, entity_type) DO NOTHING
"""


async def backfill_geocoding(ctx: dict) -> None:
    """Process existing extracted_entities that lack geocoded_locations entries.

    Runs in batches of _BATCH_SIZE. Enqueue again if more rows remain.
    """
    db_pool = ctx["db_pool"]
    redis = ctx.get("redis")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(SQL_BACKFILL_ENTITIES, _BATCH_SIZE, 0)

    if not rows:
        log.info("geocoding_backfill.complete", message="no ungeolocated entities remaining")
        return

    texts = [r["entity_text"] for r in rows]
    types = [r["entity_type"] for r in rows]

    results = geocode_entities(texts, types)

    # Build lookup: normalized → geocode result
    result_by_normalized: dict[str, dict] = {}
    for entry in results:
        key = f"{entry['entity_text_normalized']}:{entry['entity_type']}"
        result_by_normalized[key] = entry

    stored = 0
    for entry in results:
        try:
            await upsert_geocoded_location(
                db_pool,
                entity_text_normalized=entry["entity_text_normalized"],
                entity_type=entry["entity_type"],
                latitude=entry["latitude"],
                longitude=entry["longitude"],
                geocode_confidence=entry["geocode_confidence"],
                geocode_source=entry["geocode_source"],
            )
            if redis:
                await geocode_cache_set(
                    redis,
                    entry["entity_text_normalized"],
                    entry["entity_type"],
                    lat=entry["latitude"],
                    lon=entry["longitude"],
                    source=entry["geocode_source"],
                    confidence=entry["geocode_confidence"],
                )
            stored += 1
        except Exception:
            log.warning(
                "geocoding_backfill.store_failed",
                entity=entry["entity_text_normalized"],
                exc_info=True,
            )

    # Also insert rows keyed by the ORIGINAL lowered text so the NOT EXISTS
    # check in SQL won't re-fetch alias sources (e.g., "us" → "united states").
    for text, etype in zip(texts, types):
        normalized = normalize_entity_text(text)
        if normalized != text and f"{normalized}:{etype}" in result_by_normalized:
            entry = result_by_normalized[f"{normalized}:{etype}"]
            try:
                await upsert_geocoded_location(
                    db_pool,
                    entity_text_normalized=text,
                    entity_type=etype,
                    latitude=entry["latitude"],
                    longitude=entry["longitude"],
                    geocode_confidence=entry["geocode_confidence"],
                    geocode_source=entry["geocode_source"],
                )
            except Exception:
                pass  # ON CONFLICT handles dupes

    # Mark unresolved entities so SQL NOT EXISTS skips them next batch.
    # Uses lat=0, lon=0, source='unresolved', confidence=0.0.
    geocoded_texts = {e["entity_text_normalized"] for e in results}
    unresolved_count = 0
    for text, etype in zip(texts, types):
        normalized = normalize_entity_text(text)
        if normalized and normalized not in geocoded_texts:
            try:
                async with db_pool.acquire() as conn:
                    await conn.execute(SQL_UPSERT_UNRESOLVED, text, etype)
                    if normalized != text:
                        await conn.execute(SQL_UPSERT_UNRESOLVED, normalized, etype)
                unresolved_count += 1
            except Exception:
                log.warning(
                    "geocoding_backfill.unresolved_upsert_failed",
                    entity_text=text,
                    entity_type=etype,
                    exc_info=True,
                )

    log.info(
        "geocoding_backfill.batch_done",
        fetched=len(rows),
        geocoded=stored,
        unresolved=unresolved_count,
    )

    # If we got a full batch, there may be more — enqueue another run
    if len(rows) >= _BATCH_SIZE:
        try:
            from arq import create_pool

            from .jobs import WorkerSettings

            redis_pool = await create_pool(WorkerSettings.redis_settings)
            await redis_pool.enqueue_job("backfill_geocoding", _queue_name="arq:analyst")
            log.info("geocoding_backfill.continuation_enqueued")
        except Exception:
            log.warning("geocoding_backfill.enqueue_continuation_failed", exc_info=True)
