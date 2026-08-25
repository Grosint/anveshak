"""Unit tests for the scheduler liveness heartbeat.

pytest.mark.unit -- no Redis, no network. The Redis client is a mock recording
psetex calls.

The two schedulers are not ARQ workers, so nothing wrote a health key for them
and their container healthcheck was `kill -0 1`. See docs/venv_rebuild_plan.md,
the open finding on the two scheduler healthchecks.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from anveshak.heartbeat import (
    HEARTBEAT_INTERVAL_S,
    HEARTBEAT_TTL_S,
    beat,
    health_key,
    sleep_with_heartbeat,
)

pytestmark = pytest.mark.unit


class TestHealthKey:
    def test_key_matches_the_shell_probe_convention(self):
        """arq_health.sh appends :health-check to whatever compose passes it."""
        assert health_key("scrape-web") == "anveshak:scheduler:scrape-web:health-check"

    def test_key_is_not_in_the_arq_namespace(self):
        """`arq:<name>:health-check` would collide with a real queue of that name."""
        assert not health_key("scrape-web").startswith("arq:")


class TestBeat:
    async def test_beat_sets_a_ttl(self):
        """Presence of the key is the signal, so it must expire on its own."""
        redis = AsyncMock()

        await beat(redis, "scrape-web")

        key, ttl_ms, _value = redis.psetex.call_args.args
        assert key == "anveshak:scheduler:scrape-web:health-check"
        assert ttl_ms == HEARTBEAT_TTL_S * 1000

    async def test_ttl_outlives_a_slow_cycle_body(self):
        """A cycle that runs long must not be reported dead on its own cost."""
        assert HEARTBEAT_TTL_S > HEARTBEAT_INTERVAL_S * 2


class TestSleepWithHeartbeat:
    async def test_key_is_refreshed_while_sleeping(self, monkeypatch):
        """A 900s cycle sleep cannot be the detection window."""
        slept: list[float] = []

        async def _fake_sleep(duration):
            slept.append(duration)

        monkeypatch.setattr("anveshak.heartbeat.asyncio.sleep", _fake_sleep)
        redis = AsyncMock()

        await sleep_with_heartbeat(redis, "scrape-web", 900)

        assert sum(slept) == 900
        assert all(d <= HEARTBEAT_INTERVAL_S for d in slept)
        # One beat per slice, plus one on waking.
        assert redis.psetex.await_count == len(slept) + 1

    async def test_short_sleep_still_beats(self, monkeypatch):
        """A poll interval below one heartbeat interval must not skip the key."""

        async def _fake_sleep(duration):
            return None

        monkeypatch.setattr("anveshak.heartbeat.asyncio.sleep", _fake_sleep)
        redis = AsyncMock()

        await sleep_with_heartbeat(redis, "scrape-social", 5)

        assert redis.psetex.await_count == 2

    async def test_zero_duration_beats_once(self, monkeypatch):
        """The key must be fresh on re-entering the cycle body regardless."""

        async def _fake_sleep(duration):
            return None

        monkeypatch.setattr("anveshak.heartbeat.asyncio.sleep", _fake_sleep)
        redis = AsyncMock()

        await sleep_with_heartbeat(redis, "scrape-web", 0)

        assert redis.psetex.await_count == 1
