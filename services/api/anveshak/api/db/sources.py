"""Source repository — all SQL for the sources domain."""
from __future__ import annotations

from typing import Any, Optional

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_INSERT_SOURCE = """
    INSERT INTO sources (id, name, url_or_handle, platform, credibility_score,
                         auto_score_enabled, is_active, created_at, updated_at, labels)
    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
"""

SQL_LIST_SOURCES = """
    SELECT id, name, url_or_handle, platform, credibility_score, is_active,
           health_status, consecutive_failures, health_error, last_checked_at
    FROM sources ORDER BY credibility_score DESC
"""

SQL_GET_SOURCE_SCORE = "SELECT credibility_score FROM sources WHERE id = $1"

SQL_CHECK_SOURCE_EXISTS = "SELECT id FROM sources WHERE id = $1"

SQL_UPDATE_SOURCE_SCORE = (
    "UPDATE sources SET credibility_score=$1, updated_at=$2 WHERE id=$3"
)

SQL_INSERT_CREDIBILITY_AUDIT = """
    INSERT INTO credibility_audit_log
        (id, source_id, old_score, new_score, reason, changed_by, created_at, labels)
    VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
"""

SQL_TOGGLE_SOURCE_ACTIVE = (
    "UPDATE sources SET is_active=$1, updated_at=$2 WHERE id=$3"
)

SQL_COUNT_REPORT_WARNINGS = """
    SELECT COUNT(*)
    FROM report_source_warnings
    WHERE source_id = $1
"""

SQL_GET_AUDIT_LOG = """
    SELECT id, source_id, old_score, new_score, reason, changed_by, created_at
    FROM credibility_audit_log
    WHERE source_id = $1
    ORDER BY created_at DESC
"""

SQL_LIST_SOURCES_BELOW = """
    SELECT id, name, url_or_handle, platform, credibility_score, is_active,
           health_status, consecutive_failures, health_error, last_checked_at
    FROM sources
    WHERE credibility_score < $1
    ORDER BY credibility_score ASC
"""

SQL_UPDATE_SOURCE_HEALTH = """
    UPDATE sources
    SET health_status        = $2,
        consecutive_failures = $3,
        health_error         = $4,
        last_checked_at      = $5,
        updated_at           = $5
    WHERE id = $1
"""

SQL_GET_SOURCE_FOR_HEALTH = """
    SELECT id, url_or_handle, platform, health_status, consecutive_failures
    FROM sources WHERE id = $1
"""

SQL_UPDATE_SOURCE_FIELDS = """
    UPDATE sources
    SET name          = COALESCE($2, name),
        url_or_handle = COALESCE($3, url_or_handle),
        updated_at    = $4
    WHERE id = $1
"""

SQL_DELETE_SOURCE = "DELETE FROM sources WHERE id = $1"

SQL_COUNT_CONTENT_ITEMS_FOR_SOURCE = (
    "SELECT COUNT(*) FROM content_items WHERE source_id = $1"
)

SQL_TOPIC_SOURCES = """
    SELECT
        s.id,
        s.name,
        s.url_or_handle,
        s.platform,
        s.credibility_score,
        s.is_active,
        s.health_status,
        ts.added_at,
        COALESCE(ci_counts.item_count, 0) AS item_count
    FROM topic_sources ts
    JOIN sources s ON s.id = ts.source_id
    LEFT JOIN (
        SELECT source_id, COUNT(*) AS item_count
        FROM content_items
        WHERE topic_id = $1
        GROUP BY source_id
    ) ci_counts ON ci_counts.source_id = s.id
    WHERE ts.topic_id = $1
    ORDER BY item_count DESC
"""

SQL_ADD_TOPIC_SOURCE = """
    INSERT INTO topic_sources (topic_id, source_id)
    VALUES ($1, $2)
    ON CONFLICT DO NOTHING
"""

SQL_REMOVE_TOPIC_SOURCE = """
    DELETE FROM topic_sources
    WHERE topic_id = $1 AND source_id = $2
"""

SQL_CHECK_TOPIC_SOURCE = """
    SELECT 1 FROM topic_sources
    WHERE topic_id = $1 AND source_id = $2
"""

# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------

async def insert_source(
    conn: asyncpg.Connection,
    source_id: str,
    name: str,
    url_or_handle: str,
    platform: str,
    credibility_score: float,
    now: Any,
    labels_json: str,
) -> None:
    await conn.execute(
        SQL_INSERT_SOURCE,
        source_id, name, url_or_handle, platform,
        credibility_score, True, True, now, now, labels_json,
    )


async def list_sources(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_SOURCES)
    return [dict(r) for r in rows]


async def get_source_score(
    conn: asyncpg.Connection, source_id: str
) -> float | None:
    row = await conn.fetchrow(SQL_GET_SOURCE_SCORE, source_id)
    return row["credibility_score"] if row else None


async def source_exists(conn: asyncpg.Connection, source_id: str) -> bool:
    row = await conn.fetchrow(SQL_CHECK_SOURCE_EXISTS, source_id)
    return row is not None


async def update_credibility(
    conn: asyncpg.Connection,
    source_id: str,
    audit_id: str,
    old_score: float,
    new_score: float,
    reason: str,
    changed_by: str,
    now: Any,
    labels_json: str,
) -> None:
    """Atomically update score and write audit log inside caller's transaction."""
    await conn.execute(SQL_UPDATE_SOURCE_SCORE, new_score, now, source_id)
    await conn.execute(
        SQL_INSERT_CREDIBILITY_AUDIT,
        audit_id, source_id, old_score, new_score, reason, changed_by, now, labels_json,
    )


async def toggle_source_active(
    conn: asyncpg.Connection,
    source_id: str,
    is_active: bool,
    now: Any,
) -> None:
    await conn.execute(SQL_TOGGLE_SOURCE_ACTIVE, is_active, now, source_id)


async def count_report_warnings(
    conn: asyncpg.Connection, source_id: str
) -> int:
    result = await conn.fetchval(SQL_COUNT_REPORT_WARNINGS, source_id)
    return int(result or 0)


async def get_audit_log(
    conn: asyncpg.Connection, source_id: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_GET_AUDIT_LOG, source_id)
    return [dict(r) for r in rows]


async def list_sources_below(
    conn: asyncpg.Connection, threshold: float
) -> list[dict[str, Any]]:
    """Return sources with credibility_score < threshold, ascending (worst first)."""
    rows = await conn.fetch(SQL_LIST_SOURCES_BELOW, threshold)
    return [dict(r) for r in rows]


async def update_source_health(
    conn: asyncpg.Connection,
    source_id: str,
    health_status: str,
    consecutive_failures: int,
    health_error: Optional[str],
    now: Any,
) -> None:
    """Write health check result. Called by scraper worker and API check-health endpoint."""
    await conn.execute(
        SQL_UPDATE_SOURCE_HEALTH,
        source_id, health_status, consecutive_failures, health_error, now,
    )


async def get_source_for_health(
    conn: asyncpg.Connection, source_id: str
) -> dict[str, Any] | None:
    row = await conn.fetchrow(SQL_GET_SOURCE_FOR_HEALTH, source_id)
    return dict(row) if row else None


async def update_source_fields(
    conn: asyncpg.Connection,
    source_id: str,
    name: str | None,
    url_or_handle: str | None,
    now: Any,
) -> None:
    """Patch name and/or url_or_handle — None values are left unchanged."""
    await conn.execute(SQL_UPDATE_SOURCE_FIELDS, source_id, name, url_or_handle, now)


async def delete_source(conn: asyncpg.Connection, source_id: str) -> None:
    await conn.execute(SQL_DELETE_SOURCE, source_id)


async def count_content_items_for_source(
    conn: asyncpg.Connection, source_id: str
) -> int:
    result = await conn.fetchval(SQL_COUNT_CONTENT_ITEMS_FOR_SOURCE, source_id)
    return int(result or 0)


async def list_topic_sources(
    conn: asyncpg.Connection, topic_id: str
) -> list[dict[str, Any]]:
    """Return sources assigned to a topic via topic_sources, with item_count."""
    rows = await conn.fetch(SQL_TOPIC_SOURCES, topic_id)
    return [dict(r) for r in rows]


async def add_topic_source(
    conn: asyncpg.Connection, topic_id: str, source_id: str
) -> None:
    """Associate a source with a topic."""
    await conn.execute(SQL_ADD_TOPIC_SOURCE, topic_id, source_id)


async def remove_topic_source(
    conn: asyncpg.Connection, topic_id: str, source_id: str
) -> None:
    """Remove a source association from a topic."""
    await conn.execute(SQL_REMOVE_TOPIC_SOURCE, topic_id, source_id)


async def topic_source_exists(
    conn: asyncpg.Connection, topic_id: str, source_id: str
) -> bool:
    row = await conn.fetchrow(SQL_CHECK_TOPIC_SOURCE, topic_id, source_id)
    return row is not None
