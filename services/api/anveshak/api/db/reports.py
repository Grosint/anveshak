"""Report repository — all SQL for the reports domain."""
from __future__ import annotations

from typing import Any

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_INSERT_REPORT = """
    INSERT INTO reports (
        id, topic_id, report_type, time_window_start, time_window_end,
        credibility_min_filter, tracker_id, created_at, updated_at, labels
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8, $9)
"""

SQL_FETCH_REPORT = """
    SELECT r.*,
        COALESCE(
            json_agg(
                json_build_object(
                    'id', rsw.id,
                    'source_id', rsw.source_id,
                    'source_name', rsw.source_name,
                    'warning_type', rsw.warning_type,
                    'old_score', rsw.old_score,
                    'new_score', rsw.new_score,
                    'created_at', rsw.created_at
                ) ORDER BY rsw.created_at
            ) FILTER (WHERE rsw.id IS NOT NULL),
            '[]'::json
        ) AS source_warnings
    FROM reports r
    LEFT JOIN report_source_warnings rsw ON rsw.report_id = r.id
    WHERE r.id = $1
    GROUP BY r.id
"""

SQL_LIST_TOPIC_REPORTS = """
    SELECT id, topic_id, report_type, generated_at, confidence_score,
           content_item_count, created_at,
           CASE
               WHEN generated_at IS NOT NULL THEN 'complete'
               WHEN generation_error IS NOT NULL THEN 'failed'
               ELSE 'queued'
           END AS generation_status
    FROM reports
    WHERE topic_id = $1
    ORDER BY created_at DESC
"""

SQL_GET_REPORT_GEOJSON = "SELECT generated_at, geojson FROM reports WHERE id = $1"

# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------

async def insert_report(
    conn: asyncpg.Connection,
    report_id: str,
    topic_id: str,
    report_type: str,
    time_start: Any,
    time_end: Any,
    credibility_min: float,
    now: Any,
    labels_json: str,
    *,
    tracker_id: str | None = None,
) -> None:
    await conn.execute(
        SQL_INSERT_REPORT,
        report_id, topic_id, report_type,
        time_start, time_end, credibility_min,
        tracker_id, now, labels_json,
    )


async def fetch_report(
    conn: asyncpg.Connection, report_id: str
) -> dict[str, Any] | None:
    row = await conn.fetchrow(SQL_FETCH_REPORT, report_id)
    return dict(row) if row else None


async def list_topic_reports(
    conn: asyncpg.Connection, topic_id: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_TOPIC_REPORTS, topic_id)
    return [dict(r) for r in rows]


async def get_report_geojson(
    conn: asyncpg.Connection, report_id: str
) -> dict[str, Any] | None:
    row = await conn.fetchrow(SQL_GET_REPORT_GEOJSON, report_id)
    return dict(row) if row else None
