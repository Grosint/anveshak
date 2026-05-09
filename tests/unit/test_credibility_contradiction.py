"""Unit tests for contradiction-based credibility drop (criteria 7.2).

pytest.mark.unit -- no external dependencies, no DB, no network.
All DB calls mocked with AsyncMock.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from anveshak.analyst.credibility import run_contradiction_update, clamp_score


_MOD = "anveshak.analyst.credibility"


def _make_source_row(
    source_id: str = "src-1",
    source_name: str = "Unreliable Blog",
    credibility_score: float = 50.0,
    noise_count: int = 8,
    total_count: int = 10,
) -> dict:
    return {
        "source_id": source_id,
        "source_name": source_name,
        "credibility_score": credibility_score,
        "noise_count": noise_count,
        "total_count": total_count,
    }


def _make_pool(source_rows: list[dict]) -> AsyncMock:
    """Build a mock pool that returns source_rows from SQL_CONTRADICTION_SOURCES."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=source_rows)
    conn.execute = AsyncMock()

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

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
class TestContradictionDropsHighNoiseRatio:

    @pytest.mark.asyncio
    async def test_drops_high_noise_ratio(self):
        """8/10 noise ratio (0.8) >= 0.6 threshold → score reduced by 5.0."""
        row = _make_source_row(credibility_score=50.0, noise_count=8, total_count=10)
        pool = _make_pool([row])

        with (
            patch(f"{_MOD}.apply_credibility_drop") as mock_drop,
            patch(f"{_MOD}.settings") as mock_settings,
        ):
            mock_settings.credibility_contradiction_min_items = 5
            mock_settings.credibility_noise_ratio_threshold = 0.6
            mock_settings.credibility_contradiction_drop = 5.0
            mock_settings.credibility_min_auto_drop = 1.0

            updated = await run_contradiction_update(pool)

        assert updated == 1
        mock_drop.assert_awaited_once()
        drop_kwargs = mock_drop.call_args
        # new_score should be 50.0 - 5.0 = 45.0
        assert drop_kwargs.kwargs["new_score"] == 45.0
        assert drop_kwargs.kwargs["old_score"] == 50.0


@pytest.mark.unit
class TestContradictionSkipsBelowRatio:

    @pytest.mark.asyncio
    async def test_skips_below_ratio_threshold(self):
        """4/10 noise ratio (0.4) < 0.6 threshold → skip."""
        row = _make_source_row(noise_count=4, total_count=10)
        pool = _make_pool([row])

        with (
            patch(f"{_MOD}.apply_credibility_drop") as mock_drop,
            patch(f"{_MOD}.settings") as mock_settings,
        ):
            mock_settings.credibility_contradiction_min_items = 5
            mock_settings.credibility_noise_ratio_threshold = 0.6
            mock_settings.credibility_contradiction_drop = 5.0
            mock_settings.credibility_min_auto_drop = 1.0

            updated = await run_contradiction_update(pool)

        assert updated == 0
        mock_drop.assert_not_awaited()


@pytest.mark.unit
class TestContradictionSkipsMinDrop:

    @pytest.mark.asyncio
    async def test_skips_when_drop_below_min(self):
        """old_score 0.5, new would be 0.0 (clamped) → |0.5 - 0.0| = 0.5 > 1.0? No.
        Actually: old_score=0.5, drop=5.0 → new=0.0, |0.5-0.0|=0.5 < min_auto_drop=1.0 → skip.
        """
        row = _make_source_row(
            credibility_score=0.5,
            noise_count=9,
            total_count=10,
        )
        pool = _make_pool([row])

        with (
            patch(f"{_MOD}.apply_credibility_drop") as mock_drop,
            patch(f"{_MOD}.settings") as mock_settings,
        ):
            mock_settings.credibility_contradiction_min_items = 5
            mock_settings.credibility_noise_ratio_threshold = 0.6
            mock_settings.credibility_contradiction_drop = 5.0
            mock_settings.credibility_min_auto_drop = 1.0

            updated = await run_contradiction_update(pool)

        assert updated == 0
        mock_drop.assert_not_awaited()


@pytest.mark.unit
class TestContradictionDivisionByZero:

    @pytest.mark.asyncio
    async def test_division_by_zero_safe(self):
        """total_count=0 → noise_ratio=0.0 → skip (below threshold)."""
        row = _make_source_row(noise_count=0, total_count=0)
        pool = _make_pool([row])

        with (
            patch(f"{_MOD}.apply_credibility_drop") as mock_drop,
            patch(f"{_MOD}.settings") as mock_settings,
        ):
            mock_settings.credibility_contradiction_min_items = 5
            mock_settings.credibility_noise_ratio_threshold = 0.6
            mock_settings.credibility_contradiction_drop = 5.0
            mock_settings.credibility_min_auto_drop = 1.0

            # Must not raise ZeroDivisionError
            updated = await run_contradiction_update(pool)

        assert updated == 0
        mock_drop.assert_not_awaited()


@pytest.mark.unit
class TestContradictionClampsScore:

    @pytest.mark.asyncio
    async def test_clamps_score_to_zero(self):
        """Score 3.0 - drop 5.0 = -2.0 → clamped to 0.0 (never negative)."""
        row = _make_source_row(
            credibility_score=3.0,
            noise_count=9,
            total_count=10,
        )
        pool = _make_pool([row])

        with (
            patch(f"{_MOD}.apply_credibility_drop") as mock_drop,
            patch(f"{_MOD}.settings") as mock_settings,
        ):
            mock_settings.credibility_contradiction_min_items = 5
            mock_settings.credibility_noise_ratio_threshold = 0.6
            mock_settings.credibility_contradiction_drop = 5.0
            mock_settings.credibility_min_auto_drop = 1.0

            updated = await run_contradiction_update(pool)

        assert updated == 1
        mock_drop.assert_awaited_once()
        # new_score should be clamped to 0.0, not -2.0
        assert mock_drop.call_args.kwargs["new_score"] == 0.0


@pytest.mark.unit
class TestContradictionAuditLog:

    @pytest.mark.asyncio
    async def test_audit_log_written(self):
        """apply_credibility_drop called with correct source_id, old, new scores."""
        row = _make_source_row(
            source_id="src-audit",
            credibility_score=60.0,
            noise_count=7,
            total_count=10,
        )
        pool = _make_pool([row])

        with (
            patch(f"{_MOD}.apply_credibility_drop") as mock_drop,
            patch(f"{_MOD}.settings") as mock_settings,
        ):
            mock_settings.credibility_contradiction_min_items = 5
            mock_settings.credibility_noise_ratio_threshold = 0.6
            mock_settings.credibility_contradiction_drop = 5.0
            mock_settings.credibility_min_auto_drop = 1.0

            await run_contradiction_update(pool)

        mock_drop.assert_awaited_once()
        kwargs = mock_drop.call_args.kwargs
        assert kwargs["source_id"] == "src-audit"
        assert kwargs["old_score"] == 60.0
        assert kwargs["new_score"] == 55.0
        assert "reason" in kwargs
        assert "noise ratio" in kwargs["reason"].lower() or "unclustered" in kwargs["reason"].lower()
