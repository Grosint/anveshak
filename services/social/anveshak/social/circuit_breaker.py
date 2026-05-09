"""Circuit breaker for social adapters — Redis-backed, per-adapter.

States:
  CLOSED   — normal operation. Failures tracked via Redis INCR.
  OPEN     — consecutive failures >= threshold. All calls blocked.
  HALF_OPEN — cooldown expired. One probe call allowed.

On success in HALF_OPEN → CLOSED (counter + opened_at deleted).
On failure in HALF_OPEN → stays OPEN (counter re-incremented).

Redis keys per adapter:
  anveshak:social:failures:{adapter_id}   — consecutive failure count (int)
  anveshak:social:opened_at:{adapter_id}  — monotonic timestamp when circuit opened
"""
from __future__ import annotations

import time

import structlog
from arq import ArqRedis

log = structlog.get_logger(__name__)


class AdapterCircuitBreaker:
    """Per-adapter circuit breaker backed by Redis."""

    def __init__(
        self,
        redis: ArqRedis,
        adapter_id: str,
        threshold: int = 5,
        cooldown_s: int = 900,
    ) -> None:
        self._redis = redis
        self._adapter_id = adapter_id
        self._threshold = threshold
        self._cooldown_s = cooldown_s
        self._failure_key = f"anveshak:social:failures:{adapter_id}"
        self._opened_key = f"anveshak:social:opened_at:{adapter_id}"

    async def record_failure(self) -> None:
        """Record a consecutive failure. Opens circuit if threshold reached."""
        count = await self._redis.incr(self._failure_key)
        if count >= self._threshold:
            await self._redis.set(self._opened_key, str(time.monotonic()))
            log.warning(
                "social.circuit_breaker.opened",
                adapter_id=self._adapter_id,
                failures=count,
                cooldown_s=self._cooldown_s,
            )

    async def record_success(self) -> None:
        """Record a success. Resets counter and closes circuit."""
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
            log.debug(
                "social.circuit_breaker.blocked",
                adapter_id=self._adapter_id,
            )
            return False
        return True
