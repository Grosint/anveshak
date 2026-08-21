"""Social service backfill/catchup — detect and log missed polling windows.

Persists last_poll_at to Redis so restarts can detect gaps.
Currently logs warnings for missed windows — future work can add
adapter-specific catchup queries for platforms that support time-based search.

AGENTS.md: DB is authoritative for long-lived state, but Redis is fine for
transient operational state like poll timestamps (if lost, worst case is
one extra poll cycle worth of duplicate detection via content_hash).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Optional

import structlog

log = structlog.get_logger(__name__)

_REDIS_KEY = "anveshak:social:last_poll_at"


async def save_last_poll_at(redis, timestamp: datetime) -> None:
    """Persist the last successful poll timestamp to Redis."""
    await redis.set(_REDIS_KEY, timestamp.isoformat())


async def get_last_poll_at(redis) -> Optional[datetime]:
    """Read the last poll timestamp from Redis. Returns None on first boot."""
    val = await redis.get(_REDIS_KEY)
    if val is None:
        return None
    try:
        ts_str = val.decode() if isinstance(val, bytes) else val
        return datetime.fromisoformat(ts_str)
    except (ValueError, AttributeError):
        return None


def detect_poll_gap(
    last_poll_at: Optional[datetime],
    poll_interval_s: int,
) -> Optional[timedelta]:
    """Detect if there's a significant gap since last poll.

    Returns the gap duration if last_poll_at is more than poll_interval_s old,
    or None if no gap (recent poll or first boot).
    """
    if last_poll_at is None:
        return None

    now = datetime.now(UTC)
    elapsed = now - last_poll_at

    if elapsed.total_seconds() > poll_interval_s:
        log.warning(
            "social.poll_gap_detected",
            last_poll_at=last_poll_at.isoformat(),
            gap_seconds=int(elapsed.total_seconds()),
            gap_human=str(elapsed),
            hint="Content from this window may have been missed. "
            "Deduplication via content_hash prevents duplicates on next poll.",
        )
        return elapsed

    return None
