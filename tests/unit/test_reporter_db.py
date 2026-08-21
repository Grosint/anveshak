"""Unit tests for reporter DB — set_report_generated idempotency guard.

pytest.mark.unit — mocks asyncpg pool/connection.
Tests the 'UPDATE N' string parsing and WHERE generated_at IS NULL guard.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


def _make_pool():
    """Build a mock asyncpg pool with async context manager on acquire()."""
    pool = MagicMock()
    conn = AsyncMock()
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = acm
    return pool, conn


class TestSetReportGenerated:
    """set_report_generated uses WHERE generated_at IS NULL for immutability."""

    @pytest.mark.asyncio
    async def test_set_report_generated_first_call_returns_true(self):
        """First call (row not yet generated) → conn.execute returns 'UPDATE 1' → True."""
        pool, conn = _make_pool()
        conn.execute.return_value = "UPDATE 1"

        from anveshak.reporter.db import set_report_generated

        result = await set_report_generated(
            pool=pool,
            report_id="report-1",
            content_md="# Report",
            confidence_score=0.85,
            geojson={"type": "FeatureCollection", "features": []},
            source_snapshot={"src-1": {"name": "Source A", "credibility_score": 0.9}},
            content_item_count=10,
        )

        assert result is True
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_report_generated_idempotent_returns_false(self):
        """Second call (already generated) → conn.execute returns 'UPDATE 0' → False.

        The SQL WHERE generated_at IS NULL prevents overwriting an immutable report.
        """
        pool, conn = _make_pool()
        conn.execute.return_value = "UPDATE 0"

        from anveshak.reporter.db import set_report_generated

        result = await set_report_generated(
            pool=pool,
            report_id="report-1",
            content_md="# Updated Report",
            confidence_score=0.90,
            geojson={},
            source_snapshot={},
            content_item_count=15,
        )

        assert result is False
        conn.execute.assert_awaited_once()
