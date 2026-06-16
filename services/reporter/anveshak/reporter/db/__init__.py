"""asyncpg-based DB layer for the reporter service."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, UTC
from typing import Any

import asyncpg
import structlog

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------
SQL_FETCH_REPORT = """
    SELECT r.*, COALESCE(
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

SQL_FETCH_TOPIC = "SELECT * FROM topics WHERE id = $1"

SQL_FETCH_RAG_CHUNKS = """
    SELECT id,
           COALESCE(translated_text, clean_text) AS clean_text,
           credibility_score_at_capture,
           url,
           source_id
    FROM content_items
    WHERE (topic_id = $1
       OR id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND embedding IS NOT NULL
      AND credibility_score_at_capture >= $2
      AND (topic_relevance_score IS NULL OR topic_relevance_score >= $5)
    ORDER BY embedding <-> $3
    LIMIT $4
"""

SQL_FETCH_SOURCES_FOR_SNAPSHOT = """
    SELECT id, name, credibility_score
    FROM sources
    WHERE id = ANY($1::text[])
"""

SQL_SET_REPORT_GENERATED = """
    UPDATE reports
    SET content_md = $2,
        confidence_score = $3,
        geojson = $4,
        source_snapshot = $5,
        content_item_count = $6,
        generated_at = $7,
        updated_at = $7
    WHERE id = $1
      AND generated_at IS NULL
"""

SQL_INSERT_SOURCE_WARNING = """
    INSERT INTO report_source_warnings (
        id, report_id, source_id, source_name, warning_type,
        old_score, new_score, created_at, updated_at, labels
    ) VALUES ($1, $2, $3, $4, 'credibility_downgraded', $5, $6, $7, $7, $8)
    ON CONFLICT (report_id, source_id) DO NOTHING
"""

SQL_FETCH_REPORTS_FOR_WARNING_CHECK = """
    SELECT r.id, r.source_snapshot, r.generated_at
    FROM reports r
    WHERE r.generated_at IS NOT NULL
      AND r.generated_at >= NOW() - ($1 || ' days')::interval
"""

SQL_INSERT_REPORT = """
    INSERT INTO reports (
        id, topic_id, report_type, time_window_start, time_window_end,
        credibility_min_filter, created_at, updated_at, labels
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $7, $8)
"""

SQL_UPDATE_JOB_STATUS = """
    UPDATE analysis_jobs
    SET status = $2,
        error = $3,
        updated_at = NOW()
    WHERE id = $1
"""

SQL_SET_REPORT_FAILED = """
    UPDATE reports
    SET generation_error = $2,
        updated_at       = NOW()
    WHERE id = $1
"""

SQL_LIST_TOPIC_REPORTS = """
    SELECT id, topic_id, report_type, generated_at, confidence_score,
           content_item_count, created_at
    FROM reports
    WHERE topic_id = $1
    ORDER BY created_at DESC
"""

SQL_FETCH_TOPIC_LOCATION_ENTITIES = """
    SELECT DISTINCT ee.entity_text
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE (ci.topic_id = $1
       OR ci.id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND ee.entity_type IN ('GPE', 'LOC', 'FACILITY')
      AND ee.confidence >= 0.8
"""

SQL_FETCH_TOPIC_IDENTIFIERS = """
    SELECT identifier_type, identifier_value, source_count, content_item_count,
           first_seen_at, last_seen_at
    FROM identifier_clusters
    WHERE topic_id = $1
    ORDER BY source_count DESC
    LIMIT $2
"""

SQL_FETCH_TOPIC_TEMPLATE_MATCHES = """
    SELECT ci.labels->>'scam_template' AS template_name,
           st.display AS template_display,
           AVG((ci.labels->>'template_confidence')::float) AS confidence,
           st.severity,
           st.legal_sections,
           COUNT(*) AS match_count
    FROM content_items ci
    JOIN scam_templates st ON st.name = ci.labels->>'scam_template'
    WHERE (ci.topic_id = $1
       OR ci.id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND ci.labels->>'scam_template' IS NOT NULL
    GROUP BY ci.labels->>'scam_template', st.display, st.severity, st.legal_sections
    ORDER BY COUNT(*) DESC
"""


# ---------------------------------------------------------------------------
# Pool management
# ---------------------------------------------------------------------------

async def get_pool(postgres_url: str) -> asyncpg.Pool:
    """Create and return an asyncpg connection pool."""
    url = postgres_url.replace("+asyncpg", "")
    pool = await asyncpg.create_pool(url, min_size=2, max_size=5)
    log.info("reporter.db_pool_created")
    return pool


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

async def fetch_report(pool: asyncpg.Pool, report_id: str) -> dict[str, Any] | None:
    """Return full report row including aggregated source_warnings, or None."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(SQL_FETCH_REPORT, report_id)
    if row is None:
        return None
    return dict(row)


async def fetch_topic(pool: asyncpg.Pool, topic_id: str) -> dict[str, Any] | None:
    """Return topic row or None."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(SQL_FETCH_TOPIC, topic_id)
    if row is None:
        return None
    return dict(row)


async def fetch_rag_chunks(
    pool: asyncpg.Pool,
    topic_id: str,
    query_embedding: list[float],
    credibility_min: float,
    top_k: int,
    relevance_threshold: float = 0.0,
) -> list[dict[str, Any]]:
    """Return top-k content chunks ordered by vector similarity.

    SQL: SELECT ... WHERE topic_id=$1 AND embedding IS NOT NULL
         AND credibility_score_at_capture >= $2
         AND topic_relevance_score >= $5
         ORDER BY embedding <-> $3 LIMIT $4
    """
    # asyncpg does not natively encode Python lists as pgvector — must stringify.
    vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            SQL_FETCH_RAG_CHUNKS,
            topic_id,
            credibility_min,
            vec_str,
            top_k,
            relevance_threshold,
        )
    return [dict(r) for r in rows]


async def fetch_sources_for_snapshot(
    pool: asyncpg.Pool,
    source_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Return {source_id: {name, credibility_score}} for the given IDs."""
    if not source_ids:
        return {}
    async with pool.acquire() as conn:
        rows = await conn.fetch(SQL_FETCH_SOURCES_FOR_SNAPSHOT, source_ids)
    return {
        row["id"]: {"name": row["name"], "credibility_score": row["credibility_score"]}
        for row in rows
    }


async def set_report_generated(
    pool: asyncpg.Pool,
    report_id: str,
    content_md: str,
    confidence_score: float,
    geojson: dict[str, Any],
    source_snapshot: dict[str, Any],
    content_item_count: int,
) -> bool:
    """Set generated_at ONCE via WHERE generated_at IS NULL guard.

    Returns True if the row was updated (first time), False if already generated
    (idempotency — second call is a no-op).
    """
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        result = await conn.execute(
            SQL_SET_REPORT_GENERATED,
            report_id,
            content_md,
            confidence_score,
            json.dumps(geojson),
            json.dumps(source_snapshot),
            content_item_count,
            now,
        )
    # asyncpg returns "UPDATE <n>" as a string
    updated = int(result.split()[-1])
    return updated > 0


async def insert_source_warning(
    pool: asyncpg.Pool,
    report_id: str,
    source_id: str,
    source_name: str,
    old_score: float,
    new_score: float,
) -> None:
    """Insert a credibility downgrade warning for a report source."""
    now = datetime.now(UTC)
    warning_id = str(uuid.uuid4())
    labels = json.dumps({"classification": "OPEN", "domain": "report", "owner_org": "anveshak"})
    async with pool.acquire() as conn:
        await conn.execute(
            SQL_INSERT_SOURCE_WARNING,
            warning_id,
            report_id,
            source_id,
            source_name,
            old_score,
            new_score,
            now,
            labels,
        )
    log.info(
        "reporter.source_warning_inserted",
        report_id=report_id,
        source_id=source_id,
        old_score=old_score,
        new_score=new_score,
    )


async def fetch_reports_for_warning_check(
    pool: asyncpg.Pool,
    lookback_days: int,
    batch_size: int = 100,
) -> list[dict[str, Any]]:
    """Return recent generated reports for source-warning sweep.

    Args:
        batch_size: Max reports per batch (default 100). Prevents loading
                    thousands of reports into memory on long-running instances.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(SQL_FETCH_REPORTS_FOR_WARNING_CHECK, str(lookback_days))
    return [dict(r) for r in rows[:batch_size]]


async def create_report_row(
    pool: asyncpg.Pool,
    report_id: str,
    topic_id: str,
    report_type: str,
    time_window_start: datetime,
    time_window_end: datetime,
    credibility_min: float,
) -> None:
    """Insert a new report row with generated_at=NULL (pending generation)."""
    now = datetime.now(UTC)
    labels = json.dumps({"classification": "OPEN", "domain": "report", "owner_org": "anveshak"})
    async with pool.acquire() as conn:
        await conn.execute(
            SQL_INSERT_REPORT,
            report_id,
            topic_id,
            report_type,
            time_window_start,
            time_window_end,
            credibility_min,
            now,
            labels,
        )


async def list_topic_reports(
    pool: asyncpg.Pool,
    topic_id: str,
) -> list[dict[str, Any]]:
    """Return all reports for a topic, newest first."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(SQL_LIST_TOPIC_REPORTS, topic_id)
    return [dict(r) for r in rows]


async def fetch_topic_location_entities(
    pool: asyncpg.Pool,
    topic_id: str,
) -> list[str]:
    """Return distinct location entity names from the analyst NER pipeline.

    Queries extracted_entities for GPE/LOC/FACILITY with confidence >= 0.8.
    These are higher quality than regex extraction since they come from spaCy NER.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(SQL_FETCH_TOPIC_LOCATION_ENTITIES, topic_id)
    return [row["entity_text"] for row in rows]


async def update_job_status(
    pool: asyncpg.Pool,
    job_id: str,
    status: str,
    error: str | None = None,
) -> None:
    """Update analysis_jobs row status."""
    async with pool.acquire() as conn:
        await conn.execute(SQL_UPDATE_JOB_STATUS, job_id, status, error)


async def set_report_failed(
    pool: asyncpg.Pool,
    report_id: str,
    error_message: str,
) -> None:
    """Write a failure reason into reports.generation_error so the API can surface it immediately."""
    async with pool.acquire() as conn:
        await conn.execute(SQL_SET_REPORT_FAILED, report_id, error_message)
    log.warning("reporter.report_failed", report_id=report_id, error=error_message)


async def fetch_topic_identifiers(
    pool: asyncpg.Pool,
    topic_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return top identifiers for a topic from identifier_clusters, sorted by source_count DESC."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(SQL_FETCH_TOPIC_IDENTIFIERS, topic_id, limit)
    return [dict(r) for r in rows]


async def fetch_topic_template_matches(
    pool: asyncpg.Pool,
    topic_id: str,
) -> list[dict[str, Any]]:
    """Return aggregated scam template match data for a topic."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(SQL_FETCH_TOPIC_TEMPLATE_MATCHES, topic_id)
    return [dict(r) for r in rows]
