"""Unit tests for BlueskyQuotaGuard — daily call cap enforcement.

Mirrors the XSpendGuard test suite. All tests use mock Redis (pytest.mark.unit).
Bluesky's free API has a 7200 calls/day limit — the guard prevents exceeding it.
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


def make_mock_redis(eval_returns: list[int]) -> MagicMock:
    """Build a mock ArqRedis that returns successive values from eval (Lua script).

    The Lua script returns new_count on success, -1 on cap exceeded.
    """
    redis = MagicMock()
    redis.eval = AsyncMock(side_effect=eval_returns)
    redis.get = AsyncMock(return_value=None)
    return redis


class TestBlueskyQuotaGuardUnderCap:
    @pytest.mark.asyncio
    async def test_first_call_returns_true(self):
        from anveshak.social.adapters.bluesky import BlueskyQuotaGuard

        redis = make_mock_redis([1])
        guard = BlueskyQuotaGuard(redis, cap=7200)
        result = await guard.check_and_increment()
        assert result is True

    @pytest.mark.asyncio
    async def test_first_call_uses_eval(self):
        """Must use Lua eval (atomic) instead of bare INCR."""
        from anveshak.social.adapters.bluesky import BlueskyQuotaGuard

        redis = make_mock_redis([1])
        guard = BlueskyQuotaGuard(redis, cap=7200)
        await guard.check_and_increment()
        redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_subsequent_call_also_uses_eval(self):
        """Each call goes through Lua script."""
        from anveshak.social.adapters.bluesky import BlueskyQuotaGuard

        redis = make_mock_redis([1, 2])
        guard = BlueskyQuotaGuard(redis, cap=7200)
        await guard.check_and_increment()
        await guard.check_and_increment()
        assert redis.eval.call_count == 2

    @pytest.mark.asyncio
    async def test_at_cap_minus_one_allowed(self):
        """Call exactly at cap is permitted (cap=100, count=100 is OK)."""
        from anveshak.social.adapters.bluesky import BlueskyQuotaGuard

        redis = make_mock_redis([100])
        guard = BlueskyQuotaGuard(redis, cap=100)
        result = await guard.check_and_increment()
        assert result is True


class TestBlueskyQuotaGuardAtCap:
    @pytest.mark.asyncio
    async def test_over_cap_blocked(self):
        """Lua script returns -1 when over cap → check_and_increment returns False."""
        from anveshak.social.adapters.bluesky import BlueskyQuotaGuard

        redis = make_mock_redis([-1])
        guard = BlueskyQuotaGuard(redis, cap=100)
        result = await guard.check_and_increment()
        assert result is False

    @pytest.mark.asyncio
    async def test_zero_cap_always_blocked(self):
        """Cap of 0 blocks every call."""
        from anveshak.social.adapters.bluesky import BlueskyQuotaGuard

        redis = make_mock_redis([-1])
        guard = BlueskyQuotaGuard(redis, cap=0)
        result = await guard.check_and_increment()
        assert result is False


class TestBlueskyQuotaGuardDailyReset:
    def test_daily_key_format(self):
        """Key includes date in YYYY-MM-DD format."""
        from anveshak.social.adapters.bluesky import _daily_key

        key = _daily_key()
        assert re.match(r"anveshak:bluesky:daily_calls:\d{4}-\d{2}-\d{2}$", key)

    def test_seconds_until_day_end_positive(self):
        """TTL calculation always returns a positive value."""
        from anveshak.social.adapters.bluesky import _seconds_until_day_end

        ttl = _seconds_until_day_end()
        assert ttl >= 1
        assert ttl <= 86400


class TestBlueskyQuotaGuardCurrentCount:
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_key(self):
        from anveshak.social.adapters.bluesky import BlueskyQuotaGuard

        redis = make_mock_redis([])
        redis.get = AsyncMock(return_value=None)
        guard = BlueskyQuotaGuard(redis, cap=7200)
        count = await guard.current_count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_returns_count_without_incrementing(self):
        from anveshak.social.adapters.bluesky import BlueskyQuotaGuard

        redis = make_mock_redis([])
        redis.get = AsyncMock(return_value=b"42")
        guard = BlueskyQuotaGuard(redis, cap=7200)
        count = await guard.current_count()
        assert count == 42
        redis.eval.assert_not_awaited()
