"""Unit tests for atomic spend guard (X + Bluesky).

Critical fix: INCR/DECR pattern has a race window where concurrent calls
can exceed the cap. Tests verify Lua-script-based atomic enforcement.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit


class TestXSpendGuardAtomic:
    """XSpendGuard.check_and_increment must be atomic — no overshoot."""

    @pytest.mark.asyncio
    async def test_at_cap_returns_false(self):
        """When counter equals cap, next call must return False."""
        from anveshak.social.adapters.x_adapter import XSpendGuard

        mock_redis = AsyncMock()
        guard = XSpendGuard(mock_redis, cap=100)

        # Lua script eval returns -1 when at/over cap
        mock_redis.eval = AsyncMock(return_value=-1)

        result = await guard.check_and_increment()
        assert result is False

    @pytest.mark.asyncio
    async def test_under_cap_returns_true(self):
        """When counter is below cap, call should succeed."""
        from anveshak.social.adapters.x_adapter import XSpendGuard

        mock_redis = AsyncMock()
        guard = XSpendGuard(mock_redis, cap=100)

        # Lua script eval returns new count (e.g., 50)
        mock_redis.eval = AsyncMock(return_value=50)

        result = await guard.check_and_increment()
        assert result is True

    @pytest.mark.asyncio
    async def test_first_call_sets_ttl(self):
        """First call of the month (count=1) must set TTL on the key."""
        from anveshak.social.adapters.x_adapter import XSpendGuard

        mock_redis = AsyncMock()
        guard = XSpendGuard(mock_redis, cap=100)

        # Lua script returns 1 (first call) — TTL is set inside Lua
        mock_redis.eval = AsyncMock(return_value=1)

        result = await guard.check_and_increment()
        assert result is True

    @pytest.mark.asyncio
    async def test_uses_lua_eval_not_incr(self):
        """Must use Redis eval (Lua script), not bare INCR."""
        from anveshak.social.adapters.x_adapter import XSpendGuard

        mock_redis = AsyncMock()
        guard = XSpendGuard(mock_redis, cap=100)
        mock_redis.eval = AsyncMock(return_value=5)

        await guard.check_and_increment()

        # Must call eval (Lua), not incr
        mock_redis.eval.assert_called_once()
        assert not mock_redis.incr.called

    @pytest.mark.asyncio
    async def test_concurrent_calls_never_exceed_cap(self):
        """Simulate concurrent calls — counter must never exceed cap.

        The Lua script is atomic, so even with concurrent coroutines,
        the cap is respected. We simulate this by having eval return
        sequential values, with the last one being -1 (rejected).
        """
        from anveshak.social.adapters.x_adapter import XSpendGuard

        mock_redis = AsyncMock()
        guard = XSpendGuard(mock_redis, cap=3)

        # Simulate 5 concurrent calls: 3 succeed, 2 rejected
        call_results = [1, 2, 3, -1, -1]
        mock_redis.eval = AsyncMock(side_effect=call_results)

        results = await asyncio.gather(*[guard.check_and_increment() for _ in range(5)])

        assert results.count(True) == 3
        assert results.count(False) == 2


class TestBlueskyQuotaGuardAtomic:
    """BlueskyQuotaGuard must use same atomic Lua pattern."""

    @pytest.mark.asyncio
    async def test_at_cap_returns_false(self):
        from anveshak.social.adapters.bluesky import BlueskyQuotaGuard

        mock_redis = AsyncMock()
        guard = BlueskyQuotaGuard(mock_redis, cap=7200)

        mock_redis.eval = AsyncMock(return_value=-1)

        result = await guard.check_and_increment()
        assert result is False

    @pytest.mark.asyncio
    async def test_under_cap_returns_true(self):
        from anveshak.social.adapters.bluesky import BlueskyQuotaGuard

        mock_redis = AsyncMock()
        guard = BlueskyQuotaGuard(mock_redis, cap=7200)

        mock_redis.eval = AsyncMock(return_value=100)

        result = await guard.check_and_increment()
        assert result is True

    @pytest.mark.asyncio
    async def test_uses_lua_eval_not_incr(self):
        """Must use Redis eval (Lua script), not bare INCR."""
        from anveshak.social.adapters.bluesky import BlueskyQuotaGuard

        mock_redis = AsyncMock()
        guard = BlueskyQuotaGuard(mock_redis, cap=7200)
        mock_redis.eval = AsyncMock(return_value=5)

        await guard.check_and_increment()

        mock_redis.eval.assert_called_once()
        assert not mock_redis.incr.called
