"""Redis liveness heartbeat for plain asyncio scheduler loops.

ARQ workers refresh `arq:<queue>:health-check` on every tick of their event loop
and expire it after `health_check_interval + 1` seconds, so the key exists only
while the loop is running. `sdk/arq_health.sh` reads that key, which is why a
worker whose loop is frozen by blocking work can no longer report healthy.

The scrape-web and scrape-social schedulers are not ARQ workers: they are bare
`while True` loops that enqueue jobs and sleep. They had no such key, so their
container healthcheck was `kill -0 1`, which proves only that PID 1 exists. This
module gives them the same signal under the same key convention, so the same
shell probe covers them with no change.

The sleep between cycles is `poll_interval_s`, 900s by default, which is far too
long to be a detection window. `sleep_with_heartbeat` therefore refreshes the key
every `HEARTBEAT_INTERVAL_S` while it sleeps rather than once per cycle. A loop
blocked anywhere, in its cycle body or in the sleep, stops refreshing and the key
expires within `HEARTBEAT_TTL_S`.

`HEARTBEAT_TTL_S` is deliberately several intervals wide. A cycle body that runs
long, one enqueue per active topic against a slow database, must not be reported
dead on its own cost; that mistake already cost this repo a flapping worker once.
See docs/venv_rebuild_plan.md item 9.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Protocol

# How often the key is refreshed while a scheduler sleeps between cycles.
HEARTBEAT_INTERVAL_S = 30

# How long the key survives without a refresh. Wider than the interval so a slow
# cycle body does not expire it; a genuinely stopped loop is still visible in
# under two minutes, against the 900s cycle it sits inside.
HEARTBEAT_TTL_S = 120

# Namespace for scheduler keys. `arq:` is owned by ARQ itself, and writing into
# it would collide with a queue of the same name.
KEY_PREFIX = "anveshak:scheduler"


class _Beatable(Protocol):
    """The one Redis method this module needs, so callers can pass any client.

    redis-py declares psetex as a sync method returning ResponseT, a union that
    covers both the sync and async clients, so the awaitable is not visible in
    the annotation. The return is therefore Any and the call site awaits it.
    """

    def psetex(self, name: str, time_ms: int, value: str) -> Any: ...


def health_key(name: str) -> str:
    """Return the Redis key for a scheduler, matching arq_health.sh's convention.

    The script appends `:health-check` to whatever it is given, so a compose
    healthcheck passes `anveshak:scheduler:<name>` and needs no other change.
    """
    return f"{KEY_PREFIX}:{name}:health-check"


async def beat(redis: _Beatable, name: str) -> None:
    """Refresh a scheduler's health key.

    The value is the timestamp of the beat, which is diagnostic only: presence of
    the key is the liveness signal, since a frozen loop cannot refresh a TTL.
    """
    await redis.psetex(health_key(name), HEARTBEAT_TTL_S * 1000, datetime.now(UTC).isoformat())


async def sleep_with_heartbeat(redis: _Beatable, name: str, duration_s: float) -> None:
    """Sleep `duration_s`, refreshing the health key every HEARTBEAT_INTERVAL_S.

    Beats once before sleeping and once on waking, so the key is always fresh
    when the caller re-enters its cycle body.
    """
    remaining = duration_s
    while remaining > 0:
        await beat(redis, name)
        slice_s = min(HEARTBEAT_INTERVAL_S, remaining)
        await asyncio.sleep(slice_s)
        remaining -= slice_s
    await beat(redis, name)
