"""Database operations for geocoded_locations table.

Module-level SQL constants + async functions per project conventions.
"""
from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_LOOKUP_GEOCODED_LOCATION = """
    SELECT id, entity_text_normalized, entity_type,
           latitude, longitude, geocode_confidence, geocode_source
    FROM geocoded_locations
    WHERE entity_text_normalized = $1 AND entity_type = $2
"""

SQL_UPSERT_GEOCODED_LOCATION = """
    INSERT INTO geocoded_locations (
        entity_text_normalized, entity_type,
        latitude, longitude, geocode_confidence, geocode_source,
        geocoded_at, labels
    ) VALUES ($1, $2, $3, $4, $5, $6, NOW(), '{}'::jsonb)
    ON CONFLICT (entity_text_normalized, entity_type) DO UPDATE SET
        latitude = EXCLUDED.latitude,
        longitude = EXCLUDED.longitude,
        geocode_confidence = EXCLUDED.geocode_confidence,
        geocode_source = EXCLUDED.geocode_source,
        geocoded_at = NOW(),
        updated_at = NOW()
    WHERE geocoded_locations.geocode_confidence < EXCLUDED.geocode_confidence
       OR geocoded_locations.geocode_source = 'geonamescache'
"""

SQL_UPDATE_GEOCODED_LOCATION = """
    UPDATE geocoded_locations
    SET latitude = $2, longitude = $3, geocode_source = $4, updated_at = NOW()
    WHERE id = $1::uuid
"""

SQL_BATCH_LOOKUP_GEOCODED_LOCATIONS = """
    SELECT entity_text_normalized, entity_type,
           latitude, longitude, geocode_confidence, geocode_source
    FROM geocoded_locations
    WHERE (entity_text_normalized, entity_type) = ANY($1::record[])
"""


# ---------------------------------------------------------------------------
# Async DB functions
# ---------------------------------------------------------------------------

async def lookup_geocoded_location(
    pool: asyncpg.Pool,
    entity_text_normalized: str,
    entity_type: str,
) -> dict[str, Any] | None:
    """Look up a single geocoded location by normalized text + type."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            SQL_LOOKUP_GEOCODED_LOCATION,
            entity_text_normalized,
            entity_type,
        )
        return dict(row) if row else None


async def upsert_geocoded_location(
    pool: asyncpg.Pool,
    *,
    entity_text_normalized: str,
    entity_type: str,
    latitude: float,
    longitude: float,
    geocode_confidence: float,
    geocode_source: str,
) -> None:
    """Insert or update a geocoded location.

    Only overwrites existing if new confidence is higher or existing
    source is geonamescache (allow custom overlay to override).
    """
    async with pool.acquire() as conn:
        await conn.execute(
            SQL_UPSERT_GEOCODED_LOCATION,
            entity_text_normalized,
            entity_type,
            latitude,
            longitude,
            geocode_confidence,
            geocode_source,
        )


async def update_geocoded_location(
    pool: asyncpg.Pool,
    location_id: str,
    *,
    latitude: float,
    longitude: float,
    geocode_source: str,
) -> bool:
    """Analyst override — update coordinates for a geocoded location.

    Returns True if a row was updated, False if location_id not found.
    """
    async with pool.acquire() as conn:
        result = await conn.execute(
            SQL_UPDATE_GEOCODED_LOCATION,
            location_id,
            latitude,
            longitude,
            geocode_source,
        )
        return result == "UPDATE 1"


async def batch_lookup_geocoded_locations(
    pool: asyncpg.Pool,
    entities: list[tuple[str, str]],
) -> dict[str, dict[str, Any]]:
    """Look up multiple entities at once.

    Returns dict keyed by "normalized_text:entity_type".
    """
    if not entities:
        return {}

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            SQL_BATCH_LOOKUP_GEOCODED_LOCATIONS,
            entities,
        )
        return {
            f"{r['entity_text_normalized']}:{r['entity_type']}": dict(r)
            for r in rows
        }
