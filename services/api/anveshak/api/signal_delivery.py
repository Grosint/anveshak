"""Signal delivery loop — Phase 2, criterion 2.18.

The analyst service writes Signal rows to the DB via its own signal_engine_loop.
The API service owns the WebSocket sessions (_sessions dict in routes/signals.py).
This module bridges the two: it polls for undelivered signals and pushes them to
connected analyst sessions via broadcast_signal.

Design:
- Polls signals WHERE delivered_at IS NULL every SIGNAL_DELIVERY_POLL_S seconds.
- Sets delivered_at=NOW() only after broadcast_signal completes without exception.
- If broadcast fails for a signal (no connected sessions), delivered_at is still
  set — the client will receive the signal via the missed-signal replay mechanism
  (criterion 2.20) on reconnect.
- Runs as an asyncio background task inside the API lifespan.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, UTC

import asyncpg
import structlog

log = structlog.get_logger(__name__)

# Seconds between delivery polls — short enough to satisfy the ≤10s criterion 2.29
SIGNAL_DELIVERY_POLL_S = 5

SQL_UNDELIVERED_SIGNALS = """
    SELECT id, topic_id, cluster_id, signal_type, description,
           evidence, created_at
    FROM signals
    WHERE delivered_at IS NULL
    ORDER BY created_at ASC
    LIMIT 50
"""

SQL_MARK_DELIVERED = """
    UPDATE signals SET delivered_at = $1 WHERE id = $2
"""


def _build_ws_payload(row: asyncpg.Record) -> dict:
    """Build the WebSocket push message from a signals row (criterion 2.19 schema)."""
    evidence: dict = {}
    if row["evidence"]:
        raw = row["evidence"]
        if isinstance(raw, str):
            try:
                evidence = json.loads(raw)
            except (ValueError, TypeError):
                pass
        elif isinstance(raw, dict):
            evidence = raw

    isc = evidence.get("independent_source_count", 0)
    severity = "HIGH" if isc >= 3 else "MEDIUM"

    return {
        "type": "signal",
        "signal_id": row["id"],
        "topic_id": row["topic_id"],
        "cluster_id": row["cluster_id"],
        "signal_type": row["signal_type"],
        "severity": severity,
        "independent_source_count": isc,
        "description": row["description"],
    }


async def _deliver_one(
    conn: asyncpg.Connection,
    row: asyncpg.Record,
    broadcast: object,  # Callable[[dict], Awaitable[None]]
) -> None:
    """Broadcast a single signal via WebSocket + webhook, then mark delivered."""
    payload = _build_ws_payload(row)
    try:
        await broadcast(payload)
    except Exception as exc:
        # Broadcast errors (no sessions, closed WS) are non-fatal.
        # We still mark delivered — client gets it via replay on reconnect.
        log.debug(
            "signal_delivery.broadcast_noop",
            signal_id=row["id"],
            error=str(exc),
        )

    # Webhook notification — non-blocking, failures never prevent delivery
    try:
        from .notifications import send_webhook
        await send_webhook(payload)
    except Exception as exc:
        log.debug("signal_delivery.webhook_noop", signal_id=row["id"], error=str(exc))

    await conn.execute(SQL_MARK_DELIVERED, datetime.now(UTC), row["id"])
    log.info("signal_delivery.delivered", signal_id=row["id"], topic_id=row["topic_id"])


async def signal_delivery_loop(pool: asyncpg.Pool, broadcast) -> None:
    """Infinite loop: poll for undelivered signals and push to WebSocket sessions.

    Criterion 2.18: signals are pushed to connected sessions within
    SIGNAL_DELIVERY_POLL_S seconds of being written by the analyst service.
    Criterion 2.29: poll interval ≤5s → delivery latency ≤10s (5s poll + network).
    """
    log.info("signal_delivery.started", poll_s=SIGNAL_DELIVERY_POLL_S)

    while True:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(SQL_UNDELIVERED_SIGNALS)
                for row in rows:
                    await _deliver_one(conn, row, broadcast)
        except Exception as exc:
            log.error("signal_delivery.loop_error", error=str(exc))

        await asyncio.sleep(SIGNAL_DELIVERY_POLL_S)
