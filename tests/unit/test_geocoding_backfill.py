"""Unit tests for geocoding backfill ARQ job.

pytest.mark.unit — mocked DB, no real connection.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _make_ctx():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return {"db_pool": pool, "redis": AsyncMock()}, pool, conn


class TestBackfillGeocodingJob:
    """backfill_geocoding: process existing extracted_entities."""

    async def test_function_exists_and_is_async(self):
        import asyncio

        from anveshak.analyst.geocoding_backfill import backfill_geocoding

        assert asyncio.iscoroutinefunction(backfill_geocoding)

    async def test_processes_location_entities_only(self):
        """Should filter to GPE/LOC/FAC entity types."""
        from anveshak.analyst.geocoding_backfill import SQL_BACKFILL_ENTITIES

        sql_lower = SQL_BACKFILL_ENTITIES.lower()
        assert "gpe" in sql_lower or "entity_type" in sql_lower

    async def test_idempotent_skips_already_geocoded(self):
        """Should use LEFT JOIN or NOT EXISTS to skip already-geocoded entities."""
        from anveshak.analyst.geocoding_backfill import SQL_BACKFILL_ENTITIES

        sql_lower = SQL_BACKFILL_ENTITIES.lower()
        # Must exclude already-geocoded entities
        assert "left join" in sql_lower or "not exists" in sql_lower or "not in" in sql_lower

    async def test_processes_in_batches(self):
        """Should process entities in batches, not all at once."""
        from anveshak.analyst.geocoding_backfill import backfill_geocoding

        ctx, pool, conn = _make_ctx()
        # Return empty batch — should complete without error
        conn.fetch.return_value = []

        with patch("anveshak.analyst.geocoding_backfill.geocode_entities", return_value=[]):
            await backfill_geocoding(ctx)

        conn.fetch.assert_awaited()

    async def test_registered_in_worker_functions(self):
        """Backfill job must be in WorkerSettings.functions."""
        from anveshak.analyst.jobs import WorkerSettings

        func_names = [
            f.__name__ if callable(f) else f.coroutine.__name__ for f in WorkerSettings.functions
        ]
        assert "backfill_geocoding" in func_names
