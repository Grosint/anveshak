"""Unit tests for social backfill/catchup on restart.

Tests:
  - Last poll timestamp persisted to Redis
  - Gap detected on startup when last_poll_at is stale
  - No gap warning when last_poll_at is recent
  - Missing last_poll_at (first boot) treated as no gap

pytest.mark.unit — mock Redis, no external dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


class TestPollTimestampPersistence:
    """Last poll timestamps are persisted to Redis."""

    @pytest.mark.asyncio
    async def test_save_last_poll(self):
        """save_last_poll_at stores timestamp in Redis."""
        from anveshak.social.backfill import save_last_poll_at

        redis = MagicMock()
        redis.set = AsyncMock()
        now = datetime.now(UTC)

        await save_last_poll_at(redis, now)
        redis.set.assert_awaited_once()
        key = redis.set.call_args[0][0]
        assert "last_poll_at" in key

    @pytest.mark.asyncio
    async def test_get_last_poll_returns_datetime(self):
        """get_last_poll_at returns datetime from Redis."""
        from anveshak.social.backfill import get_last_poll_at

        redis = MagicMock()
        ts = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
        redis.get = AsyncMock(return_value=ts.isoformat().encode())

        result = await get_last_poll_at(redis)
        assert result == ts

    @pytest.mark.asyncio
    async def test_get_last_poll_returns_none_on_missing(self):
        """First boot — no key in Redis → None."""
        from anveshak.social.backfill import get_last_poll_at

        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)

        result = await get_last_poll_at(redis)
        assert result is None


class TestGapDetection:
    """Detect missed polling window on restart."""

    @pytest.mark.asyncio
    async def test_detects_gap(self):
        """Stale last_poll_at (>2x poll_interval) → gap detected."""
        from anveshak.social.backfill import detect_poll_gap

        old_time = datetime.now(UTC) - timedelta(hours=2)
        gap = detect_poll_gap(old_time, poll_interval_s=900)
        assert gap is not None
        assert gap.total_seconds() > 3600  # at least 1 hour gap

    @pytest.mark.asyncio
    async def test_no_gap_when_recent(self):
        """Recent last_poll_at (<poll_interval) → no gap."""
        from anveshak.social.backfill import detect_poll_gap

        recent_time = datetime.now(UTC) - timedelta(seconds=300)
        gap = detect_poll_gap(recent_time, poll_interval_s=900)
        assert gap is None

    @pytest.mark.asyncio
    async def test_first_boot_no_gap(self):
        """None last_poll_at (first boot) → no gap."""
        from anveshak.social.backfill import detect_poll_gap

        gap = detect_poll_gap(None, poll_interval_s=900)
        assert gap is None
