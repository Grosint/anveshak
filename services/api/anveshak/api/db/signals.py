"""Signal repository — all SQL for the signals domain."""
from __future__ import annotations

from typing import Any

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_LIST_SIGNALS = """
    SELECT s.id, s.topic_id, s.cluster_id, s.signal_type, s.description, s.evidence,
           s.status, s.created_at,
           nc.label AS cluster_label,
           nc.independent_source_count
    FROM signals s
    LEFT JOIN narrative_clusters nc ON nc.id = s.cluster_id
    WHERE s.status = $1
    ORDER BY s.created_at DESC
    LIMIT 50
"""

SQL_ACKNOWLEDGE = """
    UPDATE signals SET status = 'acknowledged', updated_at = $1
    WHERE id = $2 AND status = 'new'
    RETURNING id
"""

SQL_DISMISS = """
    UPDATE signals SET status = 'dismissed', updated_at = $1
    WHERE id = $2 AND status IN ('new', 'acknowledged')
    RETURNING id
"""

SQL_MISSED_SIGNALS = """
    SELECT id, topic_id, cluster_id, signal_type, description, status, created_at
    FROM signals
    WHERE created_at > $1
      AND status = 'new'
    ORDER BY created_at ASC
    LIMIT 100
"""

# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------

async def list_signals(
    conn: asyncpg.Connection, status: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_SIGNALS, status)
    return [dict(r) for r in rows]


async def acknowledge_signal(
    conn: asyncpg.Connection, signal_id: str, now: Any
) -> dict[str, Any] | None:
    row = await conn.fetchrow(SQL_ACKNOWLEDGE, now, signal_id)
    return dict(row) if row else None


async def dismiss_signal(
    conn: asyncpg.Connection, signal_id: str, now: Any
) -> dict[str, Any] | None:
    row = await conn.fetchrow(SQL_DISMISS, now, signal_id)
    return dict(row) if row else None


async def get_missed_signals(
    conn: asyncpg.Connection, since: Any
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_MISSED_SIGNALS, since)
    return [dict(r) for r in rows]
