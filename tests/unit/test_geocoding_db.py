"""Unit tests for geocoding DB layer.

pytest.mark.unit — mocked asyncpg, no real DB.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

_MOD = "anveshak.analyst.geocoding_db"


def _make_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


class TestLookupGeocodedLocation:
    """lookup_geocoded_location: returns cached geocode from DB."""

    async def test_found_returns_dict(self):
        from anveshak.analyst.geocoding_db import lookup_geocoded_location

        pool, conn = _make_pool()
        conn.fetchrow.return_value = {
            "id": "abc-123",
            "entity_text_normalized": "mumbai",
            "entity_type": "GPE",
            "latitude": 19.07,
            "longitude": 72.88,
            "geocode_confidence": 0.9,
            "geocode_source": "geonamescache",
        }
        result = await lookup_geocoded_location(pool, "mumbai", "GPE")
        assert result is not None
        assert result["latitude"] == 19.07
        conn.fetchrow.assert_awaited_once()

    async def test_not_found_returns_none(self):
        from anveshak.analyst.geocoding_db import lookup_geocoded_location

        pool, conn = _make_pool()
        conn.fetchrow.return_value = None
        result = await lookup_geocoded_location(pool, "nonexistent", "GPE")
        assert result is None


class TestUpsertGeocodedLocation:
    """upsert_geocoded_location: inserts or updates on conflict."""

    async def test_insert_executes_sql(self):
        from anveshak.analyst.geocoding_db import upsert_geocoded_location

        pool, conn = _make_pool()
        conn.execute.return_value = "INSERT 0 1"
        await upsert_geocoded_location(
            pool,
            entity_text_normalized="mumbai",
            entity_type="GPE",
            latitude=19.07,
            longitude=72.88,
            geocode_confidence=0.9,
            geocode_source="geonamescache",
        )
        conn.execute.assert_awaited_once()
        sql_arg = conn.execute.call_args[0][0]
        assert "ON CONFLICT" in sql_arg
        assert "entity_text_normalized" in sql_arg

    async def test_upsert_sql_has_do_update(self):
        """ON CONFLICT must DO UPDATE (not DO NOTHING) for coordinate corrections."""
        from anveshak.analyst.geocoding_db import SQL_UPSERT_GEOCODED_LOCATION

        assert "DO UPDATE" in SQL_UPSERT_GEOCODED_LOCATION


class TestUpdateGeocodedLocation:
    """update_geocoded_location: analyst override with provenance tracking."""

    async def test_update_returns_true_on_match(self):
        from anveshak.analyst.geocoding_db import update_geocoded_location

        pool, conn = _make_pool()
        conn.execute.return_value = "UPDATE 1"
        result = await update_geocoded_location(
            pool,
            location_id="abc-123",
            latitude=19.08,
            longitude=72.89,
            geocode_source="analyst_override",
        )
        assert result is True

    async def test_update_returns_false_on_no_match(self):
        from anveshak.analyst.geocoding_db import update_geocoded_location

        pool, conn = _make_pool()
        conn.execute.return_value = "UPDATE 0"
        result = await update_geocoded_location(
            pool,
            location_id="nonexistent",
            latitude=19.08,
            longitude=72.89,
            geocode_source="analyst_override",
        )
        assert result is False


class TestBatchLookupGeocodedLocations:
    """batch_lookup: look up multiple entities in one query."""

    async def test_returns_dict_keyed_by_normalized_text(self):
        from anveshak.analyst.geocoding_db import batch_lookup_geocoded_locations

        pool, conn = _make_pool()
        conn.fetch.return_value = [
            {
                "entity_text_normalized": "mumbai",
                "entity_type": "GPE",
                "latitude": 19.07,
                "longitude": 72.88,
                "geocode_confidence": 0.9,
                "geocode_source": "geonamescache",
            },
        ]
        result = await batch_lookup_geocoded_locations(pool, [("mumbai", "GPE"), ("delhi", "GPE")])
        assert "mumbai:GPE" in result
        assert "delhi:GPE" not in result

    async def test_empty_input_returns_empty(self):
        from anveshak.analyst.geocoding_db import batch_lookup_geocoded_locations

        pool, conn = _make_pool()
        result = await batch_lookup_geocoded_locations(pool, [])
        assert result == {}
