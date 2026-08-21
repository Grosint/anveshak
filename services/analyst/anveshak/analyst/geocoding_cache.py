"""Redis cache for geocoded coordinates.

No expiry — coordinates don't change. Fail-open on Redis errors.
Explicit invalidation via geocode_cache_invalidate().
"""

from __future__ import annotations

import json
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_KEY_PREFIX = "anveshak:geocode"


def _cache_key(entity_text_normalized: str, entity_type: str) -> str:
    return f"{_KEY_PREFIX}:{entity_type}:{entity_text_normalized}"


async def geocode_cache_get(
    redis: Any,
    entity_text_normalized: str,
    entity_type: str,
) -> dict[str, Any] | None:
    """Look up geocoded coordinates from Redis cache.

    Returns None on miss or Redis error (fail-open).
    """
    try:
        raw = await redis.get(_cache_key(entity_text_normalized, entity_type))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        log.warning(
            "geocoding_cache.get_failed",
            entity=entity_text_normalized,
            type=entity_type,
        )
        return None


async def geocode_cache_set(
    redis: Any,
    entity_text_normalized: str,
    entity_type: str,
    *,
    lat: float,
    lon: float,
    source: str,
    confidence: float,
) -> None:
    """Store geocoded coordinates in Redis cache.

    No expiry — coordinates don't change. Fail-open on Redis errors.
    """
    payload = json.dumps({"lat": lat, "lon": lon, "src": source, "conf": confidence})
    try:
        await redis.set(
            _cache_key(entity_text_normalized, entity_type),
            payload,
        )
    except Exception:
        log.warning(
            "geocoding_cache.set_failed",
            entity=entity_text_normalized,
            type=entity_type,
        )


async def geocode_cache_invalidate(
    redis: Any,
    entity_text_normalized: str,
    entity_type: str,
) -> None:
    """Explicitly invalidate a cached geocode (e.g., after analyst override)."""
    try:
        await redis.delete(_cache_key(entity_text_normalized, entity_type))
    except Exception:
        log.warning(
            "geocoding_cache.invalidate_failed",
            entity=entity_text_normalized,
            type=entity_type,
        )
