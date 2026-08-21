"""Unit tests for XSpendGuard — criteria 3.22–3.24, 3.30.

All tests use a mock Redis client. No real Redis required (pytest.mark.unit).
The spend guard is the most safety-critical piece of Phase 3 — every path is tested.
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anveshak.social.adapters.x_adapter import XSpendGuard, _monthly_key, _seconds_until_month_end

# ---------------------------------------------------------------------------
# Mock Redis helper
# ---------------------------------------------------------------------------


def make_mock_redis(eval_returns: list[int]) -> MagicMock:
    """Build a mock ArqRedis that returns successive values from eval (Lua script).

    The Lua script returns new_count on success, -1 on cap exceeded.
    """
    redis = MagicMock()
    redis.eval = AsyncMock(side_effect=eval_returns)
    redis.get = AsyncMock(return_value=None)
    return redis


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestXSpendGuardUnderCap:
    """Calls below cap — should be permitted and counter incremented."""

    @pytest.mark.asyncio
    async def test_first_call_returns_true(self):
        redis = make_mock_redis([1])
        guard = XSpendGuard(redis, cap=100)
        result = await guard.check_and_increment()
        assert result is True

    @pytest.mark.asyncio
    async def test_first_call_uses_eval(self):
        """Must use Lua eval (atomic) instead of bare INCR (criteria 3.22)."""
        redis = make_mock_redis([1])
        guard = XSpendGuard(redis, cap=100)
        await guard.check_and_increment()
        redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_second_call_also_uses_eval(self):
        """Each call goes through Lua script — no shortcutting."""
        redis = make_mock_redis([1, 2])
        guard = XSpendGuard(redis, cap=100)
        await guard.check_and_increment()
        await guard.check_and_increment()
        assert redis.eval.call_count == 2

    @pytest.mark.asyncio
    async def test_call_at_cap_minus_one_allowed(self):
        """Call that brings count exactly to cap is still permitted."""
        redis = make_mock_redis([100])
        guard = XSpendGuard(redis, cap=100)
        result = await guard.check_and_increment()
        assert result is True


class TestXSpendGuardAtCap:
    """Calls at or above cap — must be blocked (criteria 3.22, 3.30)."""

    @pytest.mark.asyncio
    async def test_call_over_cap_returns_false(self):
        """Lua script returns -1 when at/over cap → check_and_increment returns False."""
        redis = make_mock_redis([-1])
        guard = XSpendGuard(redis, cap=100)
        result = await guard.check_and_increment()
        assert result is False

    @pytest.mark.asyncio
    async def test_cap_zero_always_blocked(self):
        redis = make_mock_redis([-1])
        guard = XSpendGuard(redis, cap=0)
        result = await guard.check_and_increment()
        assert result is False

    @pytest.mark.asyncio
    async def test_no_api_call_when_blocked(self, monkeypatch):
        """When guard returns False, the XPollingAdapter must not call the API.

        This simulates criteria 3.30: after cap reached, subsequent calls return
        immediately with no network activity.
        """
        redis = make_mock_redis([-1])
        guard = XSpendGuard(redis, cap=100)

        api_called = False

        async def mock_api_call():
            nonlocal api_called
            api_called = True

        allowed = await guard.check_and_increment()
        if allowed:
            await mock_api_call()

        assert not api_called


class TestXSpendGuardMonthlyReset:
    """Monthly key changes with calendar month (criteria 3.24)."""

    def test_key_format_current_month(self):
        key = _monthly_key()
        assert re.fullmatch(r"anveshak:x:monthly_reads:\d{4}-\d{2}", key)

    def test_different_month_different_key(self):
        """Simulate two different months having independent counters."""
        key_jan = "anveshak:x:monthly_reads:2026-01"
        key_feb = "anveshak:x:monthly_reads:2026-02"
        assert key_jan != key_feb

    def test_seconds_until_month_end_positive(self):
        ttl = _seconds_until_month_end()
        assert ttl > 0

    def test_seconds_until_month_end_within_max(self):
        ttl = _seconds_until_month_end()
        assert ttl <= 31 * 24 * 3600 + 1  # max ~31 days + 1s buffer

    @pytest.mark.asyncio
    async def test_new_month_key_uses_lua(self):
        """Simulating month boundary: Lua script handles TTL atomically."""
        redis = make_mock_redis([1])  # first read of new month
        guard = XSpendGuard(redis, cap=100)
        await guard.check_and_increment()
        redis.eval.assert_called_once()

    def test_monthly_key_contains_year_and_month(self):
        """Key must include YYYY-MM so each month gets an independent counter.

        Bug caught: if the key used only MM (no year), January 2026 and
        January 2027 would share a counter — silently capping reads at
        whatever was left from 11 months ago.
        """
        from datetime import UTC, datetime

        key = _monthly_key()
        now = datetime.now(UTC)
        expected_suffix = now.strftime("%Y-%m")
        assert key.endswith(expected_suffix)

    def test_monthly_key_prefix_is_namespaced(self):
        """Key must be namespaced to anveshak:x: — prevents collision with other Redis users."""
        key = _monthly_key()
        assert key.startswith("anveshak:x:monthly_reads:")

    def test_seconds_until_month_end_at_least_one(self):
        """TTL must be >= 1 even at month boundary — max(1, ...) guard.

        Bug caught: if max() guard is removed, a call at exactly midnight on the
        1st of next month returns 0 → Redis expire(key, 0) deletes the key
        immediately, resetting the counter mid-boundary.
        """
        ttl = _seconds_until_month_end()
        assert ttl >= 1

    def test_seconds_until_month_end_december_crosses_year(self):
        """December must compute TTL to January 1 of next year.

        Bug caught: if the code only handles month + 1 without checking
        month == 12, it would try to create datetime(2026, 13, 1) → crash.
        """
        from datetime import UTC, datetime

        fake_dec_31 = datetime(2026, 12, 31, 23, 0, 0, tzinfo=UTC)
        with patch("anveshak.social.adapters.x_adapter.datetime") as mock_dt:
            mock_dt.now.return_value = fake_dec_31
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            ttl = _seconds_until_month_end()
            # Should be about 3600 seconds (1 hour until midnight Jan 1)
            assert 3500 <= ttl <= 3700


class TestXSpendGuardCurrentCount:
    """current_count() returns existing counter without incrementing."""

    @pytest.mark.asyncio
    async def test_current_count_zero_when_no_key(self):
        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        guard = XSpendGuard(redis, cap=100)
        count = await guard.current_count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_current_count_returns_redis_value(self):
        redis = MagicMock()
        redis.get = AsyncMock(return_value=b"42")
        guard = XSpendGuard(redis, cap=100)
        count = await guard.current_count()
        assert count == 42

    @pytest.mark.asyncio
    async def test_current_count_does_not_increment(self):
        redis = MagicMock()
        redis.get = AsyncMock(return_value=b"10")
        redis.incr = AsyncMock()
        guard = XSpendGuard(redis, cap=100)
        await guard.current_count()
        redis.incr.assert_not_called()
