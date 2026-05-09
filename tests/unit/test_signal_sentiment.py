"""Unit tests for sentiment shift signal detection (criteria 2.15-2.18).

pytest.mark.unit -- no external dependencies, no DB, no network.
All DB calls mocked with AsyncMock.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anveshak.analyst.signal_engine import check_sentiment_shifts


_MOD = "anveshak.analyst.signal_engine"


def _make_pool(
    topic_ids: list[str],
    baseline_avg: float | None = 0.5,
    recent_avg: float | None = 0.1,
    existing_signal: bool = False,
) -> AsyncMock:
    """Build a mock pool that returns configured sentiment data."""
    conn = AsyncMock()

    # SQL_ACTIVE_TOPICS → list of topic rows
    topic_rows = [{"id": tid} for tid in topic_ids]

    # Track call sequence for conn.fetch / conn.fetchrow
    # fetch is called once (SQL_ACTIVE_TOPICS)
    conn.fetch = AsyncMock(return_value=topic_rows)

    # fetchrow is called multiple times per topic:
    # 1. SQL_DUPLICATE_TOPIC_SIGNAL_CHECK → existing signal or None
    # 2. SQL_SENTIMENT_BASELINE → {"baseline_avg": ...}
    # 3. SQL_SENTIMENT_RECENT → {"recent_avg": ...}
    dedup_result = {"id": "existing-sig"} if existing_signal else None
    baseline_result = {"baseline_avg": baseline_avg}
    recent_result = {"recent_avg": recent_avg}

    conn.fetchrow = AsyncMock(
        side_effect=[dedup_result, baseline_result, recent_result] * len(topic_ids)
    )
    conn.execute = AsyncMock()

    acq = AsyncMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__ = AsyncMock(return_value=False)

    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=acq)
    return pool


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSentimentShiftFires:

    @pytest.mark.asyncio
    async def test_fires_when_drop_exceeds_threshold(self):
        """baseline 0.5, recent 0.1 → drop 0.4 > threshold 0.3 → signal fired."""
        pool = _make_pool(["topic-1"], baseline_avg=0.5, recent_avg=0.1)
        broadcast = AsyncMock()

        with patch(f"{_MOD}.settings") as mock_settings:
            mock_settings.sentiment_shift_threshold = 0.3
            mock_settings.sentiment_shift_baseline_days = 7
            mock_settings.sentiment_shift_window_hours = 24

            fired = await check_sentiment_shifts(pool, broadcast)

        assert fired == 1
        broadcast.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_fire_below_threshold(self):
        """drop 0.2 < threshold 0.3 → no signal."""
        pool = _make_pool(["topic-1"], baseline_avg=0.5, recent_avg=0.3)
        broadcast = AsyncMock()

        with patch(f"{_MOD}.settings") as mock_settings:
            mock_settings.sentiment_shift_threshold = 0.3
            mock_settings.sentiment_shift_baseline_days = 7
            mock_settings.sentiment_shift_window_hours = 24

            fired = await check_sentiment_shifts(pool, broadcast)

        assert fired == 0
        broadcast.assert_not_awaited()


@pytest.mark.unit
class TestSentimentShiftNoneHandling:

    @pytest.mark.asyncio
    async def test_skips_when_baseline_none(self):
        """No content in baseline window → baseline_avg=None → skip gracefully."""
        pool = _make_pool(["topic-1"], baseline_avg=None, recent_avg=0.1)
        broadcast = AsyncMock()

        with patch(f"{_MOD}.settings") as mock_settings:
            mock_settings.sentiment_shift_threshold = 0.3
            mock_settings.sentiment_shift_baseline_days = 7
            mock_settings.sentiment_shift_window_hours = 24

            fired = await check_sentiment_shifts(pool, broadcast)

        assert fired == 0
        broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_when_recent_none(self):
        """No content in recent window → recent_avg=None → skip."""
        pool = _make_pool(["topic-1"], baseline_avg=0.5, recent_avg=None)
        broadcast = AsyncMock()

        with patch(f"{_MOD}.settings") as mock_settings:
            mock_settings.sentiment_shift_threshold = 0.3
            mock_settings.sentiment_shift_baseline_days = 7
            mock_settings.sentiment_shift_window_hours = 24

            fired = await check_sentiment_shifts(pool, broadcast)

        assert fired == 0
        broadcast.assert_not_awaited()


@pytest.mark.unit
class TestSentimentShiftDedup:

    @pytest.mark.asyncio
    async def test_dedup_skips_existing(self):
        """Existing sentiment signal in 24h → skip even though drop is large."""
        pool = _make_pool(
            ["topic-1"],
            baseline_avg=0.5,
            recent_avg=0.0,
            existing_signal=True,
        )
        broadcast = AsyncMock()

        with patch(f"{_MOD}.settings") as mock_settings:
            mock_settings.sentiment_shift_threshold = 0.3
            mock_settings.sentiment_shift_baseline_days = 7
            mock_settings.sentiment_shift_window_hours = 24

            fired = await check_sentiment_shifts(pool, broadcast)

        assert fired == 0
        broadcast.assert_not_awaited()


@pytest.mark.unit
class TestSentimentShiftBroadcast:

    @pytest.mark.asyncio
    async def test_broadcasts_payload_structure(self):
        """Broadcast called with correct payload keys."""
        pool = _make_pool(["topic-1"], baseline_avg=0.6, recent_avg=0.1)
        broadcast = AsyncMock()

        with patch(f"{_MOD}.settings") as mock_settings:
            mock_settings.sentiment_shift_threshold = 0.3
            mock_settings.sentiment_shift_baseline_days = 7
            mock_settings.sentiment_shift_window_hours = 24

            await check_sentiment_shifts(pool, broadcast)

        broadcast.assert_awaited_once()
        payload = broadcast.call_args.args[0]
        assert payload["type"] == "signal"
        assert payload["topic_id"] == "topic-1"
        assert payload["severity"] == "MEDIUM"
        assert payload["signal_type"] == "sentiment_shift"
        assert "signal_id" in payload
        assert "description" in payload
