"""Unit tests for hostility shift signal detection (criteria 2.15-2.18, #30).

Updated rather than replaced when the signal was rebased off the English
VADER lexicon onto the multilingual hostility measure. The dedup behaviour,
the None handling and the broadcast payload shape are unchanged; the
direction flipped, because hostility rising is escalation where a sentiment
score falling was only a proxy for it.

pytest.mark.unit -- no external dependencies, no DB, no network.
All DB calls mocked with AsyncMock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anveshak.analyst.signal_engine import check_hostility_shifts

_MOD = "anveshak.analyst.signal_engine"


def _make_pool(
    topic_ids: list[str],
    baseline_avg: float | None = 0.1,
    recent_avg: float | None = 0.5,
    existing_signal: bool = False,
) -> AsyncMock:
    """Build a mock pool that returns configured hostility data."""
    conn = AsyncMock()

    # SQL_ACTIVE_TOPICS → list of topic rows
    topic_rows = [{"id": tid} for tid in topic_ids]

    # Track call sequence for conn.fetch / conn.fetchrow
    # fetch is called once (SQL_ACTIVE_TOPICS)
    conn.fetch = AsyncMock(return_value=topic_rows)

    # fetchrow is called multiple times per topic:
    # 1. SQL_DUPLICATE_TOPIC_SIGNAL_CHECK → existing signal or None
    # 2. SQL_HOSTILITY_BASELINE → {"baseline_avg": ..., "sample_count": ...}
    # 3. SQL_HOSTILITY_RECENT → {"recent_avg": ..., "sample_count": ...}
    dedup_result = {"id": "existing-sig"} if existing_signal else None
    baseline_result = {"baseline_avg": baseline_avg, "sample_count": 20}
    recent_result = {"recent_avg": recent_avg, "sample_count": 8}

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
class TestHostilityShiftFires:
    @pytest.mark.asyncio
    async def test_fires_when_rise_exceeds_threshold(self):
        """baseline 0.1, recent 0.5 → rise 0.4 > threshold 0.3 → signal fired."""
        pool = _make_pool(["topic-1"], baseline_avg=0.1, recent_avg=0.5)
        broadcast = AsyncMock()

        with patch(f"{_MOD}.settings") as mock_settings:
            mock_settings.hostility_shift_threshold = 0.3
            mock_settings.hostility_shift_baseline_days = 7
            mock_settings.hostility_shift_window_hours = 24

            fired = await check_hostility_shifts(pool, broadcast)

        assert fired == 1
        broadcast.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_fire_below_threshold(self):
        """rise 0.2 < threshold 0.3 → no signal."""
        pool = _make_pool(["topic-1"], baseline_avg=0.3, recent_avg=0.5)
        broadcast = AsyncMock()

        with patch(f"{_MOD}.settings") as mock_settings:
            mock_settings.hostility_shift_threshold = 0.3
            mock_settings.hostility_shift_baseline_days = 7
            mock_settings.hostility_shift_window_hours = 24

            fired = await check_hostility_shifts(pool, broadcast)

        assert fired == 0
        broadcast.assert_not_awaited()


@pytest.mark.unit
class TestHostilityShiftNoneHandling:
    @pytest.mark.asyncio
    async def test_skips_when_baseline_none(self):
        """Nothing scored in the baseline window → skip gracefully.

        Not an error: stance and hostility only run on clusters above their
        size threshold, so a quiet topic legitimately has nothing to compare.
        """
        pool = _make_pool(["topic-1"], baseline_avg=None, recent_avg=0.5)
        broadcast = AsyncMock()

        with patch(f"{_MOD}.settings") as mock_settings:
            mock_settings.hostility_shift_threshold = 0.3
            mock_settings.hostility_shift_baseline_days = 7
            mock_settings.hostility_shift_window_hours = 24

            fired = await check_hostility_shifts(pool, broadcast)

        assert fired == 0
        broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_when_recent_none(self):
        """Nothing scored in the recent window → skip."""
        pool = _make_pool(["topic-1"], baseline_avg=0.1, recent_avg=None)
        broadcast = AsyncMock()

        with patch(f"{_MOD}.settings") as mock_settings:
            mock_settings.hostility_shift_threshold = 0.3
            mock_settings.hostility_shift_baseline_days = 7
            mock_settings.hostility_shift_window_hours = 24

            fired = await check_hostility_shifts(pool, broadcast)

        assert fired == 0
        broadcast.assert_not_awaited()


@pytest.mark.unit
class TestHostilityShiftDedup:
    @pytest.mark.asyncio
    async def test_dedup_skips_existing(self):
        """Existing hostility signal in 24h → skip even though the rise is large."""
        pool = _make_pool(
            ["topic-1"],
            baseline_avg=0.0,
            recent_avg=0.9,
            existing_signal=True,
        )
        broadcast = AsyncMock()

        with patch(f"{_MOD}.settings") as mock_settings:
            mock_settings.hostility_shift_threshold = 0.3
            mock_settings.hostility_shift_baseline_days = 7
            mock_settings.hostility_shift_window_hours = 24

            fired = await check_hostility_shifts(pool, broadcast)

        assert fired == 0
        broadcast.assert_not_awaited()


@pytest.mark.unit
class TestHostilityShiftBroadcast:
    @pytest.mark.asyncio
    async def test_broadcasts_payload_structure(self):
        """Broadcast called with correct payload keys."""
        pool = _make_pool(["topic-1"], baseline_avg=0.1, recent_avg=0.6)
        broadcast = AsyncMock()

        with patch(f"{_MOD}.settings") as mock_settings:
            mock_settings.hostility_shift_threshold = 0.3
            mock_settings.hostility_shift_baseline_days = 7
            mock_settings.hostility_shift_window_hours = 24

            await check_hostility_shifts(pool, broadcast)

        broadcast.assert_awaited_once()
        payload = broadcast.call_args.args[0]
        assert payload["type"] == "signal"
        assert payload["topic_id"] == "topic-1"
        assert payload["severity"] == "MEDIUM"
        assert payload["signal_type"] == "hostility_shift"
        assert "signal_id" in payload
        assert "description" in payload
