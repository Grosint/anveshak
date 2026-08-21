"""Unit tests for Redis geocode cache.

pytest.mark.unit — mocked Redis, no real connection.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _make_redis():
    return AsyncMock()


class TestGeocodeCache:
    """Redis cache for geocoded coordinates — no expiry, fail-open."""

    async def test_cache_hit_returns_dict(self):
        from anveshak.analyst.geocoding_cache import geocode_cache_get

        redis = _make_redis()
        redis.get.return_value = '{"lat": 19.07, "lon": 72.88, "src": "geonamescache", "conf": 0.9}'
        result = await geocode_cache_get(redis, "mumbai", "GPE")
        assert result is not None
        assert result["lat"] == 19.07
        redis.get.assert_awaited_once()

    async def test_cache_miss_returns_none(self):
        from anveshak.analyst.geocoding_cache import geocode_cache_get

        redis = _make_redis()
        redis.get.return_value = None
        result = await geocode_cache_get(redis, "nonexistent", "GPE")
        assert result is None

    async def test_cache_set_no_expiry(self):
        from anveshak.analyst.geocoding_cache import geocode_cache_set

        redis = _make_redis()
        await geocode_cache_set(
            redis,
            "mumbai",
            "GPE",
            lat=19.07,
            lon=72.88,
            source="geonamescache",
            confidence=0.9,
        )
        redis.set.assert_awaited_once()
        # No expiry — coordinates don't change
        call_kwargs = redis.set.call_args
        # Should NOT pass ex or px (no TTL)
        if call_kwargs.kwargs:
            assert "ex" not in call_kwargs.kwargs
            assert "px" not in call_kwargs.kwargs

    async def test_cache_get_fail_open_on_redis_error(self):
        """Redis errors must not crash the pipeline."""
        from anveshak.analyst.geocoding_cache import geocode_cache_get

        redis = _make_redis()
        redis.get.side_effect = ConnectionError("Redis down")
        result = await geocode_cache_get(redis, "mumbai", "GPE")
        assert result is None  # fail-open, not exception

    async def test_cache_set_fail_open_on_redis_error(self):
        from anveshak.analyst.geocoding_cache import geocode_cache_set

        redis = _make_redis()
        redis.set.side_effect = ConnectionError("Redis down")
        # Should not raise
        await geocode_cache_set(
            redis,
            "mumbai",
            "GPE",
            lat=19.07,
            lon=72.88,
            source="geonamescache",
            confidence=0.9,
        )

    async def test_cache_key_format(self):
        from anveshak.analyst.geocoding_cache import _cache_key

        key = _cache_key("mumbai", "GPE")
        assert "geocode:" in key
        assert "mumbai" in key
        assert "GPE" in key

    async def test_cache_invalidate(self):
        from anveshak.analyst.geocoding_cache import geocode_cache_invalidate

        redis = _make_redis()
        await geocode_cache_invalidate(redis, "mumbai", "GPE")
        redis.delete.assert_awaited_once()
