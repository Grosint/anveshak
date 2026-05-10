"""Circuit breaker for Ollama LLM calls — Redis-backed.

Prevents thundering herd during Ollama outages. Same 3-state pattern
as social/circuit_breaker.py (learned/circuit-breaker-sql-filter.md).

States:
  CLOSED    — normal operation. Failures tracked via Redis INCR.
  OPEN      — consecutive failures >= threshold. All calls blocked.
  HALF_OPEN — cooldown expired. One probe call allowed.

Redis keys:
  anveshak:reporter:ollama:failures   — consecutive failure count
  anveshak:reporter:ollama:opened_at  — monotonic timestamp when opened
"""
from __future__ import annotations

import time

import structlog

log = structlog.get_logger(__name__)


class OllamaCircuitBreaker:
    """Circuit breaker for Ollama LLM calls."""

    def __init__(
        self,
        redis,
        threshold: int = 5,
        cooldown_s: int = 120,
    ) -> None:
        self._redis = redis
        self._threshold = threshold
        self._cooldown_s = cooldown_s
        self._failure_key = "anveshak:reporter:ollama:failures"
        self._opened_key = "anveshak:reporter:ollama:opened_at"

    async def record_failure(self) -> None:
        """Record a consecutive failure. Opens circuit if threshold reached."""
        count = await self._redis.incr(self._failure_key)
        if count >= self._threshold:
            await self._redis.set(self._opened_key, str(time.monotonic()))
            log.warning(
                "reporter.circuit_breaker.opened",
                failures=count,
                cooldown_s=self._cooldown_s,
            )

    async def record_success(self) -> None:
        """Record success. Resets counter and closes circuit."""
        await self._redis.delete(self._failure_key)
        await self._redis.delete(self._opened_key)

    async def get_state(self) -> str:
        """Return current state: CLOSED, OPEN, or HALF_OPEN."""
        count_raw = await self._redis.get(self._failure_key)
        count = int(count_raw) if count_raw else 0

        if count < self._threshold:
            return "CLOSED"

        opened_raw = await self._redis.get(self._opened_key)
        if not opened_raw:
            return "CLOSED"

        opened_at = float(opened_raw)
        if time.monotonic() - opened_at >= self._cooldown_s:
            return "HALF_OPEN"

        return "OPEN"

    async def allows_call(self) -> bool:
        """Return True if a call is allowed (CLOSED or HALF_OPEN)."""
        state = await self.get_state()
        if state == "OPEN":
            log.debug("reporter.circuit_breaker.blocked")
            return False
        return True
