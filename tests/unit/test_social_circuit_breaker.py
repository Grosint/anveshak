"""Unit tests for social adapter circuit breaker.

States: CLOSED (normal) → OPEN (after N failures) → HALF_OPEN (probe after cooldown) → CLOSED.
Redis-backed failure counter survives restarts.

pytest.mark.unit — mock Redis, no external dependencies.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


def make_mock_redis(**overrides) -> MagicMock:
    """Mock ArqRedis with sensible defaults."""
    redis = MagicMock()
    redis.incr = AsyncMock(return_value=overrides.get("incr_return", 1))
    redis.get = AsyncMock(return_value=overrides.get("get_return", None))
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


class TestCircuitBreakerClosed:
    """CLOSED state — normal operation, failures tracked."""

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self):
        from anveshak.social.circuit_breaker import AdapterCircuitBreaker
        redis = make_mock_redis()
        cb = AdapterCircuitBreaker(redis, "bluesky-v1", threshold=5, cooldown_s=900)
        state = await cb.get_state()
        assert state == "CLOSED"

    @pytest.mark.asyncio
    async def test_record_failure_increments_counter(self):
        from anveshak.social.circuit_breaker import AdapterCircuitBreaker
        redis = make_mock_redis(incr_return=1)
        cb = AdapterCircuitBreaker(redis, "bluesky-v1", threshold=5, cooldown_s=900)
        await cb.record_failure()
        redis.incr.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_success_resets_counter(self):
        from anveshak.social.circuit_breaker import AdapterCircuitBreaker
        redis = make_mock_redis()
        cb = AdapterCircuitBreaker(redis, "bluesky-v1", threshold=5, cooldown_s=900)
        await cb.record_success()
        redis.delete.assert_awaited()  # counter reset


class TestCircuitBreakerOpen:
    """OPEN state — too many failures, all calls blocked."""

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        from anveshak.social.circuit_breaker import AdapterCircuitBreaker
        redis = make_mock_redis(incr_return=5)  # hits threshold
        cb = AdapterCircuitBreaker(redis, "bluesky-v1", threshold=5, cooldown_s=900)
        await cb.record_failure()
        # Should set the open timestamp
        redis.set.assert_awaited()

    @pytest.mark.asyncio
    async def test_is_open_returns_true_when_open(self):
        from anveshak.social.circuit_breaker import AdapterCircuitBreaker
        # Simulate: failure count >= threshold, opened_at is recent
        redis = make_mock_redis()
        redis.get = AsyncMock(side_effect=[
            b"6",  # failure count
            str(time.monotonic()).encode(),  # opened_at (recent)
        ])
        cb = AdapterCircuitBreaker(redis, "bluesky-v1", threshold=5, cooldown_s=900)
        state = await cb.get_state()
        assert state == "OPEN"

    @pytest.mark.asyncio
    async def test_allows_call_returns_false_when_open(self):
        from anveshak.social.circuit_breaker import AdapterCircuitBreaker
        # Count is above threshold, opened recently
        redis = make_mock_redis()
        redis.get = AsyncMock(side_effect=[
            b"6",  # failure count
            str(time.monotonic()).encode(),  # opened_at (recent)
        ])
        cb = AdapterCircuitBreaker(redis, "bluesky-v1", threshold=5, cooldown_s=900)
        allowed = await cb.allows_call()
        assert allowed is False


class TestCircuitBreakerHalfOpen:
    """HALF_OPEN — cooldown expired, allow one probe call."""

    @pytest.mark.asyncio
    async def test_half_open_after_cooldown(self):
        from anveshak.social.circuit_breaker import AdapterCircuitBreaker
        # Count above threshold, but opened_at is old (cooldown expired)
        old_time = time.monotonic() - 1000  # > 900s cooldown
        redis = make_mock_redis()
        redis.get = AsyncMock(side_effect=[
            b"6",  # failure count
            str(old_time).encode(),  # opened_at (expired)
        ])
        cb = AdapterCircuitBreaker(redis, "bluesky-v1", threshold=5, cooldown_s=900)
        allowed = await cb.allows_call()
        assert allowed is True  # probe allowed

    @pytest.mark.asyncio
    async def test_success_after_half_open_closes(self):
        from anveshak.social.circuit_breaker import AdapterCircuitBreaker
        redis = make_mock_redis()
        cb = AdapterCircuitBreaker(redis, "bluesky-v1", threshold=5, cooldown_s=900)
        await cb.record_success()
        # Counter + opened_at should be deleted
        assert redis.delete.await_count >= 1


class TestCircuitBreakerIndependence:
    """Different adapters have independent circuit breakers."""

    @pytest.mark.asyncio
    async def test_different_adapters_independent_keys(self):
        from anveshak.social.circuit_breaker import AdapterCircuitBreaker
        redis = make_mock_redis()
        cb1 = AdapterCircuitBreaker(redis, "bluesky-v1", threshold=5, cooldown_s=900)
        cb2 = AdapterCircuitBreaker(redis, "reddit-v1", threshold=5, cooldown_s=900)
        assert cb1._failure_key != cb2._failure_key
        assert cb1._opened_key != cb2._opened_key
