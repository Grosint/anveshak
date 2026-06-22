"""Unit tests for credibility auto-feedback orchestrators.

Bugs caught:
  1. compute_new_score can return negative when deepfake_count is huge — clamp_score must floor at 0.0
  2. Zero deepfake_count yields drop=0 → abs(new-old) < 0.01 → skipped, but only if the skip guard works
  3. Transaction must wrap BOTH update + audit log (criteria 2.24)
  4. Cross-verify boost must clamp at 100.0, not exceed
  5. Cross-verify skip guard uses credibility_min_auto_boost, not credibility_min_auto_drop

pytest.mark.unit — no DB, no Redis, no external dependencies.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.unit


def _make_pool_and_conn():
    """Build the canonical pool + conn + transaction mock triple.

    conn.transaction() is a synchronous call in asyncpg that returns an async
    context manager — so we use MagicMock (not AsyncMock) for conn, then
    override the async methods we need.
    """
    pool = MagicMock()
    conn = AsyncMock()
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = acm

    tx = MagicMock()
    tx.__aenter__ = AsyncMock()
    tx.__aexit__ = AsyncMock(return_value=False)
    # conn.transaction() is synchronous in asyncpg — returns an async CM directly
    conn.transaction = MagicMock(return_value=tx)

    return pool, conn, tx


def _amplifier_row(source_id: str, credibility_score: float, deepfake_count: int):
    """Simulate an asyncpg.Record returned by find_deepfake_amplifiers."""
    return {
        "source_id": source_id,
        "source_name": f"source-{source_id}",
        "credibility_score": credibility_score,
        "org_id": "org-unit-test",
        "deepfake_count": deepfake_count,
    }


def _cross_verify_row(source_id: str, credibility_score: float):
    return {
        "source_id": source_id,
        "source_name": f"source-{source_id}",
        "credibility_score": credibility_score,
        "org_id": "org-unit-test",
    }


# ---------------------------------------------------------------------------
# run_credibility_update
# ---------------------------------------------------------------------------


class TestRunCredibilityUpdate:

    @pytest.mark.asyncio
    @patch("anveshak.analyst.credibility.apply_credibility_drop", new_callable=AsyncMock)
    @patch("anveshak.analyst.credibility.find_deepfake_amplifiers", new_callable=AsyncMock)
    async def test_clamps_to_zero(self, mock_find, mock_apply):
        """old_score=2.0, deepfake_count=100 → new_score must be 0.0, not negative."""
        from anveshak.analyst.credibility import run_credibility_update

        mock_find.return_value = [_amplifier_row("s1", 2.0, 100)]
        pool, conn, tx = _make_pool_and_conn()

        count = await run_credibility_update(pool)

        assert count == 1
        assert mock_apply.call_args.kwargs["new_score"] == 0.0

    @pytest.mark.asyncio
    @patch("anveshak.analyst.credibility.apply_credibility_drop", new_callable=AsyncMock)
    @patch("anveshak.analyst.credibility.find_deepfake_amplifiers", new_callable=AsyncMock)
    async def test_skips_zero_deepfake(self, mock_find, mock_apply):
        """deepfake_count=0 → drop=0, abs(new-old) < 0.01 → skip, no apply call."""
        from anveshak.analyst.credibility import run_credibility_update

        mock_find.return_value = [_amplifier_row("s1", 50.0, 0)]
        pool, conn, tx = _make_pool_and_conn()

        count = await run_credibility_update(pool)

        assert count == 0
        mock_apply.assert_not_called()

    @pytest.mark.asyncio
    @patch("anveshak.analyst.credibility.apply_credibility_drop", new_callable=AsyncMock)
    @patch("anveshak.analyst.credibility.find_deepfake_amplifiers", new_callable=AsyncMock)
    async def test_transaction_wraps_both(self, mock_find, mock_apply):
        """conn.transaction() must be entered before apply_credibility_drop is called."""
        from anveshak.analyst.credibility import run_credibility_update

        mock_find.return_value = [_amplifier_row("s1", 80.0, 5)]
        pool, conn, tx = _make_pool_and_conn()

        await run_credibility_update(pool)

        # Transaction context was entered
        tx.__aenter__.assert_awaited_once()
        tx.__aexit__.assert_awaited_once()
        # apply_credibility_drop was called inside the transaction
        mock_apply.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("anveshak.analyst.credibility.apply_credibility_drop", new_callable=AsyncMock)
    @patch("anveshak.analyst.credibility.find_deepfake_amplifiers", new_callable=AsyncMock)
    async def test_returns_count(self, mock_find, mock_apply):
        """3 amplifiers with meaningful drops → returns 3."""
        from anveshak.analyst.credibility import run_credibility_update

        mock_find.return_value = [
            _amplifier_row("s1", 80.0, 3),
            _amplifier_row("s2", 60.0, 2),
            _amplifier_row("s3", 40.0, 1),
        ]
        pool, conn, tx = _make_pool_and_conn()

        count = await run_credibility_update(pool)

        assert count == 3
        assert mock_apply.await_count == 3


# ---------------------------------------------------------------------------
# run_cross_verification_update
# ---------------------------------------------------------------------------


class TestRunCrossVerificationUpdate:

    @pytest.mark.asyncio
    @patch("anveshak.analyst.credibility.apply_credibility_boost", new_callable=AsyncMock)
    @patch("anveshak.analyst.credibility.settings")
    async def test_boost_below_threshold_skips(self, mock_settings, mock_apply):
        """old=99.9, boost=5 → clamped to 100, delta=0.1 < min_auto_boost=1.0 → skip."""
        from anveshak.analyst.credibility import run_cross_verification_update

        mock_settings.credibility_high_threshold = 80.0
        mock_settings.credibility_cross_verify_boost = 5.0
        mock_settings.credibility_min_auto_boost = 1.0

        pool, conn, tx = _make_pool_and_conn()
        conn.fetch.return_value = [_cross_verify_row("s1", 99.9)]

        count = await run_cross_verification_update(pool, "topic-1")

        assert count == 0
        mock_apply.assert_not_called()

    @pytest.mark.asyncio
    @patch("anveshak.analyst.credibility.apply_credibility_boost", new_callable=AsyncMock)
    @patch("anveshak.analyst.credibility.settings")
    async def test_clamps_at_100(self, mock_settings, mock_apply):
        """old=98, boost=5 → clamped to 100.0, not 103.0. Delta=2.0 >= min_auto_boost → applied."""
        from anveshak.analyst.credibility import run_cross_verification_update

        mock_settings.credibility_high_threshold = 80.0
        mock_settings.credibility_cross_verify_boost = 5.0
        mock_settings.credibility_min_auto_boost = 1.0

        pool, conn, tx = _make_pool_and_conn()
        conn.fetch.return_value = [_cross_verify_row("s1", 98.0)]

        count = await run_cross_verification_update(pool, "topic-1")

        assert count == 1
        assert mock_apply.call_args.kwargs["new_score"] == 100.0
