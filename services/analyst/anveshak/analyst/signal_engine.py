"""Signal engine — threshold-based intelligence notifications (Phase 2, criteria 2.11–2.20).

Responsibilities:
  - Poll narrative_clusters for threshold breaches
  - Deduplicate signals within a 24h window (criteria 2.13)
  - Insert into signals table
  - Push WebSocket notifications via injected broadcast function
  - Status flow: new → acknowledged → dismissed only (criteria 2.14)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, UTC
from typing import Awaitable, Callable

import asyncpg
import structlog

from .metrics import analyst_signals_fired_total
from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL — module-level constants
# ---------------------------------------------------------------------------

# Clusters that exceed topic threshold and have not already fired a signal
# within the dedup window (criteria 2.11, 2.12, 2.13).
SQL_BREACHING_CLUSTERS = """
    SELECT
        nc.id           AS cluster_id,
        nc.topic_id,
        nc.label,
        nc.independent_source_count,
        t.signal_threshold
    FROM narrative_clusters nc
    JOIN topics t ON t.id = nc.topic_id
    WHERE nc.independent_source_count >= t.signal_threshold
      AND t.status = 'active'
      AND nc.archived_at IS NULL
"""

SQL_DUPLICATE_SIGNAL_CHECK = """
    SELECT id FROM signals
    WHERE cluster_id  = $1
      AND signal_type = $2
      AND created_at  > NOW() - INTERVAL '24 hours'
    LIMIT 1
"""

SQL_INSERT_SIGNAL = """
    INSERT INTO signals (
        id, topic_id, cluster_id, signal_type, description, evidence,
        status, created_at, updated_at, labels
    )
    VALUES ($1, $2, $3, $4, $5, $6::jsonb, 'new', $7, $7,
            '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
    RETURNING id
"""

SQL_MISSED_SIGNALS = """
    SELECT id, topic_id, cluster_id, signal_type, description, status,
           created_at
    FROM signals
    WHERE created_at > $1
      AND status = 'new'
    ORDER BY created_at ASC
"""

_SIGNAL_TYPE_MULTI_SOURCE = "multi_source_convergence"
_SIGNAL_TYPE_CROSS_TOPIC = "cross_topic_convergence"
_SIGNAL_TYPE_SENTIMENT_SHIFT = "sentiment_shift"

SQL_ACTIVE_TOPICS = "SELECT id FROM topics WHERE status = 'active'"

SQL_SENTIMENT_BASELINE = """
    SELECT AVG((labels->'sentiment'->>'compound')::float) AS baseline_avg
    FROM content_items
    WHERE topic_id = $1
      AND captured_at >= NOW() - make_interval(days => $2)
      AND labels->'sentiment' IS NOT NULL
"""

SQL_SENTIMENT_RECENT = """
    SELECT AVG((labels->'sentiment'->>'compound')::float) AS recent_avg
    FROM content_items
    WHERE topic_id = $1
      AND captured_at >= NOW() - make_interval(hours => $2)
      AND labels->'sentiment' IS NOT NULL
"""

SQL_DUPLICATE_TOPIC_SIGNAL_CHECK = """
    SELECT id FROM signals
    WHERE topic_id = $1
      AND signal_type = $2
      AND created_at > NOW() - INTERVAL '24 hours'
    LIMIT 1
"""


# ---------------------------------------------------------------------------
# Core functions (all pure / injectable — unit-testable)
# ---------------------------------------------------------------------------

def build_signal_payload(
    signal_id: str,
    topic_id: str,
    cluster_id: str,
    independent_source_count: int,
    label: str,
) -> dict:
    """Build the WebSocket push message (criteria 2.19).

    Schema: {"type": "signal", "signal_id": ..., "topic_id": ..., "severity": ...}
    Severity: HIGH when isc >= 3, MEDIUM otherwise.
    """
    severity = "HIGH" if independent_source_count >= 3 else "MEDIUM"
    return {
        "type": "signal",
        "signal_id": signal_id,
        "topic_id": topic_id,
        "cluster_id": cluster_id,
        "cluster_label": label,
        "severity": severity,
        "independent_source_count": independent_source_count,
    }


async def is_duplicate_signal(
    conn: asyncpg.Connection,
    cluster_id: str,
    signal_type: str,
) -> bool:
    """Return True if an identical signal was fired within the last 24h (criteria 2.13)."""
    row = await conn.fetchrow(SQL_DUPLICATE_SIGNAL_CHECK, cluster_id, signal_type)
    return row is not None


async def fire_signal(
    conn: asyncpg.Connection,
    topic_id: str,
    cluster_id: str,
    cluster_label: str,
    independent_source_count: int,
    now: datetime,
) -> str | None:
    """Insert a new signal row. Returns signal_id, or None if deduplicated.

    Criteria 2.12, 2.13.
    """
    signal_type = _SIGNAL_TYPE_MULTI_SOURCE

    if await is_duplicate_signal(conn, cluster_id, signal_type):
        log.debug(
            "signal_engine.dedup_skipped",
            cluster_id=cluster_id,
            signal_type=signal_type,
        )
        return None

    signal_id = str(uuid.uuid4())
    description = (
        f"Cluster '{cluster_label}' confirmed by "
        f"{independent_source_count} independent source platforms"
    )
    evidence = json.dumps({
        "cluster_id": cluster_id,
        "independent_source_count": independent_source_count,
    })

    await conn.execute(
        SQL_INSERT_SIGNAL,
        signal_id,
        topic_id,
        cluster_id,
        signal_type,
        description,
        evidence,
        now,
    )

    analyst_signals_fired_total.labels(severity="HIGH").inc()
    log.info(
        "signal_engine.signal_fired",
        signal_id=signal_id,
        topic_id=topic_id,
        cluster_id=cluster_id,
        independent_source_count=independent_source_count,
    )
    return signal_id


# ---------------------------------------------------------------------------
# Check cycle (one pass — called by polling loop)
# ---------------------------------------------------------------------------

BroadcastFn = Callable[[dict], Awaitable[None]]


async def check_signals(
    pool: asyncpg.Pool,
    broadcast: BroadcastFn,
) -> int:
    """One signal-check pass. Returns count of signals fired.

    Criteria 2.11–2.18.
    """
    fired = 0

    async with pool.acquire() as conn:
        clusters = await conn.fetch(SQL_BREACHING_CLUSTERS)

        for row in clusters:
            cluster_id: str = row["cluster_id"]
            topic_id: str = row["topic_id"]
            label: str = row["label"] or f"Cluster {cluster_id[:8]}"
            isc: int = row["independent_source_count"]
            now = datetime.now(UTC)

            signal_id = await fire_signal(
                conn=conn,
                topic_id=topic_id,
                cluster_id=cluster_id,
                cluster_label=label,
                independent_source_count=isc,
                now=now,
            )

            if signal_id:
                payload = build_signal_payload(signal_id, topic_id, cluster_id, isc, label)
                try:
                    await broadcast(payload)
                except Exception as exc:
                    log.warning(
                        "signal_engine.broadcast_failed",
                        signal_id=signal_id,
                        error=str(exc),
                    )
                fired += 1

    return fired


# ---------------------------------------------------------------------------
# Sentiment shift detection
# ---------------------------------------------------------------------------


async def check_sentiment_shifts(
    pool: asyncpg.Pool,
    broadcast: BroadcastFn,
) -> int:
    """Check all active topics for sentiment shifts. Returns count of signals fired."""
    fired = 0
    async with pool.acquire() as conn:
        topics = await conn.fetch(SQL_ACTIVE_TOPICS)
        for topic_row in topics:
            topic_id: str = topic_row["id"]

            # Dedup: skip if sentiment_shift already fired for this topic in 24h
            existing = await conn.fetchrow(
                SQL_DUPLICATE_TOPIC_SIGNAL_CHECK,
                topic_id, _SIGNAL_TYPE_SENTIMENT_SHIFT,
            )
            if existing:
                continue

            baseline = await conn.fetchrow(
                SQL_SENTIMENT_BASELINE,
                topic_id, settings.sentiment_shift_baseline_days,
            )
            recent = await conn.fetchrow(
                SQL_SENTIMENT_RECENT,
                topic_id, settings.sentiment_shift_window_hours,
            )

            if not baseline or not recent:
                continue
            baseline_avg = baseline["baseline_avg"]
            recent_avg = recent["recent_avg"]
            if baseline_avg is None or recent_avg is None:
                continue

            drop = baseline_avg - recent_avg
            if drop < settings.sentiment_shift_threshold:
                continue

            signal_id = str(uuid.uuid4())
            now = datetime.now(UTC)
            description = (
                f"Sentiment dropped {drop:.2f} in last "
                f"{settings.sentiment_shift_window_hours}h "
                f"(baseline: {baseline_avg:.2f}, recent: {recent_avg:.2f})"
            )
            evidence = json.dumps({
                "baseline_avg": round(baseline_avg, 4),
                "recent_avg": round(recent_avg, 4),
                "drop": round(drop, 4),
                "window_hours": settings.sentiment_shift_window_hours,
                "baseline_days": settings.sentiment_shift_baseline_days,
            })

            await conn.execute(
                SQL_INSERT_SIGNAL,
                signal_id, topic_id, None,
                _SIGNAL_TYPE_SENTIMENT_SHIFT,
                description, evidence, now,
            )
            analyst_signals_fired_total.labels(severity="MEDIUM").inc()

            payload = {
                "type": "signal",
                "signal_id": signal_id,
                "topic_id": topic_id,
                "cluster_id": None,
                "cluster_label": None,
                "severity": "MEDIUM",
                "signal_type": _SIGNAL_TYPE_SENTIMENT_SHIFT,
                "description": description,
            }
            try:
                await broadcast(payload)
            except Exception as exc:
                log.warning(
                    "signal_engine.sentiment_broadcast_failed",
                    signal_id=signal_id,
                    error=str(exc),
                )
            fired += 1

    return fired


# ---------------------------------------------------------------------------
# Polling loop (long-running — called from main.py)
# ---------------------------------------------------------------------------

async def signal_engine_loop(pool: asyncpg.Pool, broadcast: BroadcastFn) -> None:
    """Infinite loop: check signals every settings.signal_check_interval_s seconds.

    Criteria 2.11. Designed to run as an asyncio task.
    """
    import asyncio

    log.info(
        "signal_engine.started",
        interval_s=settings.signal_check_interval_s,
    )
    while True:
        try:
            fired = await check_signals(pool, broadcast)
            sentiment_fired = await check_sentiment_shifts(pool, broadcast)
            total = fired + sentiment_fired
            if total:
                log.info(
                    "signal_engine.cycle_complete",
                    signals_fired=fired,
                    sentiment_signals=sentiment_fired,
                )
        except Exception as exc:
            log.error("signal_engine.cycle_error", error=str(exc))

        await asyncio.sleep(settings.signal_check_interval_s)


# ---------------------------------------------------------------------------
# Missed-signal replay (criteria 2.20)
# ---------------------------------------------------------------------------

async def fetch_missed_signals(
    conn: asyncpg.Connection,
    since: datetime,
) -> list[dict]:
    """Return signals created after `since` for replay on WebSocket reconnect."""
    rows = await conn.fetch(SQL_MISSED_SIGNALS, since)
    return [dict(r) for r in rows]
