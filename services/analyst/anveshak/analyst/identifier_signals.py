"""Engine C Step 4a — Identifier Convergence Signals.

Fire signals when identifier clusters cross per-topic source thresholds.
Integrates with existing signal engine: same signals table, same WebSocket
delivery, same status flow (new -> acknowledged -> dismissed).

Signals table cluster_id FK references narrative_clusters — identifier
cluster references go in evidence JSONB instead.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable

import asyncpg
import structlog
from anveshak.db import DBConnection

from .metrics import analyst_signals_fired_total

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIGNAL_TYPE_IDENTIFIER_CONVERGENCE = "identifier_convergence"

# ---------------------------------------------------------------------------
# SQL — module-level constants
# ---------------------------------------------------------------------------

SQL_BREACHING_IDENTIFIER_CLUSTERS = """
    SELECT
        ic.id                       AS identifier_cluster_id,
        ic.topic_id,
        ic.identifier_type,
        ic.identifier_value,
        ic.source_count,
        ic.content_item_count,
        t.identifier_signal_threshold
    FROM identifier_clusters ic
    JOIN topics t ON t.id = ic.topic_id
    WHERE ic.source_count >= t.identifier_signal_threshold
      AND t.status = 'active'
"""

SQL_DUPLICATE_IDENTIFIER_SIGNAL_CHECK = """
    SELECT id FROM signals
    WHERE signal_type = 'identifier_convergence'
      AND evidence->>'identifier_cluster_id' = $1
      AND created_at > NOW() - INTERVAL '24 hours'
    LIMIT 1
"""

SQL_IDENTIFIER_CLUSTER_SOURCES = """
    SELECT DISTINCT s.name, s.platform
    FROM identifier_cluster_items ici
    JOIN sources s ON s.id = ici.source_id
    WHERE ici.identifier_cluster_id = $1
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


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def compute_identifier_severity(source_count: int) -> str:
    """Map source_count to severity: CRITICAL >= 5, HIGH >= 3, MEDIUM otherwise."""
    if source_count >= 5:
        return "CRITICAL"
    if source_count >= 3:
        return "HIGH"
    return "MEDIUM"


def build_identifier_evidence(
    *,
    identifier_cluster_id: str,
    identifier_type: str,
    identifier_value: str,
    source_count: int,
    sources: list[str],
    content_item_count: int,
) -> dict:
    """Build evidence JSONB for identifier convergence signal."""
    return {
        "identifier_cluster_id": identifier_cluster_id,
        "identifier_type": identifier_type,
        "identifier_value": identifier_value,
        "source_count": source_count,
        "sources": sources,
        "content_item_count": content_item_count,
    }


def build_identifier_description(
    *,
    identifier_type: str,
    identifier_value: str,
    source_count: int,
) -> str:
    """Build human-readable signal description."""
    return (
        f"Identifier {identifier_type} '{identifier_value}' found across "
        f"{source_count} independent sources"
    )


def build_identifier_signal_payload(
    *,
    signal_id: str,
    topic_id: str,
    identifier_cluster_id: str,
    identifier_type: str,
    identifier_value: str,
    source_count: int,
) -> dict:
    """Build WebSocket push message for identifier convergence signal."""
    return {
        "type": "signal",
        "signal_type": SIGNAL_TYPE_IDENTIFIER_CONVERGENCE,
        "signal_id": signal_id,
        "topic_id": topic_id,
        "identifier_cluster_id": identifier_cluster_id,
        "identifier_type": identifier_type,
        "identifier_value": identifier_value,
        "source_count": source_count,
        "severity": compute_identifier_severity(source_count),
    }


# ---------------------------------------------------------------------------
# Async DB functions
# ---------------------------------------------------------------------------


async def is_duplicate_identifier_signal(
    conn: DBConnection,
    identifier_cluster_id: str,
) -> bool:
    """Return True if identifier_convergence signal fired for this cluster in last 24h."""
    row = await conn.fetchrow(
        SQL_DUPLICATE_IDENTIFIER_SIGNAL_CHECK,
        identifier_cluster_id,
    )
    return row is not None


async def fire_identifier_signal(
    conn: DBConnection,
    *,
    topic_id: str,
    identifier_cluster_id: str,
    identifier_type: str,
    identifier_value: str,
    source_count: int,
    sources: list[str],
    content_item_count: int,
    now: datetime,
) -> str | None:
    """Insert identifier_convergence signal. Returns signal_id or None if deduplicated."""
    if await is_duplicate_identifier_signal(conn, identifier_cluster_id):
        log.debug(
            "identifier_signals.dedup_skipped",
            identifier_cluster_id=identifier_cluster_id,
        )
        return None

    signal_id = str(uuid.uuid4())
    description = build_identifier_description(
        identifier_type=identifier_type,
        identifier_value=identifier_value,
        source_count=source_count,
    )
    evidence = json.dumps(
        build_identifier_evidence(
            identifier_cluster_id=identifier_cluster_id,
            identifier_type=identifier_type,
            identifier_value=identifier_value,
            source_count=source_count,
            sources=sources,
            content_item_count=content_item_count,
        )
    )

    severity = compute_identifier_severity(source_count)

    await conn.execute(
        SQL_INSERT_SIGNAL,
        signal_id,
        topic_id,
        None,  # cluster_id is NULL — FK is for narrative_clusters only
        SIGNAL_TYPE_IDENTIFIER_CONVERGENCE,
        description,
        evidence,
        now,
    )

    analyst_signals_fired_total.labels(severity=severity).inc()
    log.info(
        "identifier_signals.signal_fired",
        signal_id=signal_id,
        topic_id=topic_id,
        identifier_cluster_id=identifier_cluster_id,
        identifier_type=identifier_type,
        source_count=source_count,
        severity=severity,
    )
    return signal_id


# ---------------------------------------------------------------------------
# Check cycle
# ---------------------------------------------------------------------------

BroadcastFn = Callable[[dict], Awaitable[None]]


async def check_identifier_signals(
    pool: asyncpg.Pool,
    broadcast: BroadcastFn,
) -> int:
    """One check pass: query breaching identifier clusters, fire signals.

    Returns count of signals fired.
    """
    fired = 0

    async with pool.acquire() as conn:
        clusters = await conn.fetch(SQL_BREACHING_IDENTIFIER_CLUSTERS)

        for row in clusters:
            cluster_id: str = row["identifier_cluster_id"]
            topic_id: str = row["topic_id"]
            id_type: str = row["identifier_type"]
            id_value: str = row["identifier_value"]
            source_count: int = row["source_count"]
            content_item_count: int = row["content_item_count"]

            # Fetch source names for evidence
            source_rows = await conn.fetch(
                SQL_IDENTIFIER_CLUSTER_SOURCES,
                cluster_id,
            )
            sources = [f"{r['platform']}:{r['name']}" for r in source_rows]

            now = datetime.now(timezone.utc)

            signal_id = await fire_identifier_signal(
                conn,
                topic_id=topic_id,
                identifier_cluster_id=cluster_id,
                identifier_type=id_type,
                identifier_value=id_value,
                source_count=source_count,
                sources=sources,
                content_item_count=content_item_count,
                now=now,
            )

            if signal_id:
                payload = build_identifier_signal_payload(
                    signal_id=signal_id,
                    topic_id=topic_id,
                    identifier_cluster_id=cluster_id,
                    identifier_type=id_type,
                    identifier_value=id_value,
                    source_count=source_count,
                )
                try:
                    await broadcast(payload)
                except Exception as exc:
                    log.warning(
                        "identifier_signals.broadcast_failed",
                        signal_id=signal_id,
                        error=str(exc),
                    )
                fired += 1

    return fired
