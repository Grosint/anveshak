"""Source Assessment repository — all SQL for the assessments domain.

Phase 0: deterministic stats from content_items, extracted_entities,
identifier_occurrences, narrative_clusters, and credibility_audit_log.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg
import structlog
from anveshak.db import DBConnection

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL constants — all parameterized, org-scoped
# $1=topic_id, $2=source_id, $3=time_start, $4=time_end, $5=org_id
# ---------------------------------------------------------------------------

SQL_INSERT_ASSESSMENT = """
    INSERT INTO source_assessments
        (id, topic_id, source_id, org_id, time_window_start, time_window_end,
         stats, content_item_count, source_snapshot,
         created_at, updated_at, labels)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $10, $11)
    ON CONFLICT (topic_id, source_id, time_window_start, time_window_end)
    DO NOTHING
"""

SQL_FETCH_ASSESSMENT = """
    SELECT id, topic_id, source_id, org_id, time_window_start, time_window_end,
           stats, platform_metadata, brief_md, confidence_score,
           source_snapshot, content_item_count, generated_at, generation_error,
           arq_job_id, created_at, labels
    FROM source_assessments
    WHERE id = $1
"""

SQL_LIST_ASSESSMENTS = """
    SELECT id, topic_id, source_id, org_id, time_window_start, time_window_end,
           content_item_count, generated_at, brief_md IS NOT NULL AS has_brief,
           created_at
    FROM source_assessments
    WHERE topic_id = $1 AND source_id = $2
    ORDER BY created_at DESC
"""

SQL_COUNT_SOURCE_CONTENT = """
    SELECT COUNT(*)
    FROM content_items
    WHERE source_id = $2
      AND (topic_id = $1
           OR id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND captured_at BETWEEN $3 AND $4
"""

# --- Stats queries ---

SQL_SOURCE_POST_STATS = """
    SELECT
        COUNT(*) AS total_posts,
        MIN(captured_at) AS first_post,
        MAX(captured_at) AS last_post
    FROM content_items
    WHERE source_id = $2
      AND (topic_id = $1
           OR id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND captured_at BETWEEN $3 AND $4
"""

SQL_SOURCE_ENGAGEMENT = """
    SELECT
        SUM(COALESCE((labels->'engagement'->>'likes')::int, 0)) AS likes,
        SUM(COALESCE((labels->'engagement'->>'comments')::int, 0)) AS comments,
        SUM(COALESCE((labels->'engagement'->>'shares')::int, 0)
          + COALESCE((labels->'engagement'->>'retweets')::int, 0)
          + COALESCE((labels->'engagement'->>'reposts')::int, 0)
          + COALESCE((labels->'engagement'->>'forwards')::int, 0)) AS shares,
        SUM(COALESCE((labels->'engagement'->>'views')::int, 0)) AS views
    FROM content_items
    WHERE source_id = $2
      AND (topic_id = $1
           OR id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND captured_at BETWEEN $3 AND $4
"""

SQL_SOURCE_LANGUAGES = """
    SELECT language, COUNT(*) AS count
    FROM content_items
    WHERE source_id = $2
      AND (topic_id = $1
           OR id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND captured_at BETWEEN $3 AND $4
      AND language IS NOT NULL
    GROUP BY language
    ORDER BY count DESC
"""

SQL_SOURCE_VOLUME_TIMELINE = """
    SELECT DATE(captured_at) AS date, COUNT(*) AS count
    FROM content_items
    WHERE source_id = $2
      AND (topic_id = $1
           OR id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND captured_at BETWEEN $3 AND $4
    GROUP BY DATE(captured_at)
    ORDER BY date
"""

SQL_SOURCE_TOP_ENTITIES = """
    SELECT ee.entity_text, ee.entity_type, COUNT(*) AS count
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE ci.source_id = $2
      AND (ci.topic_id = $1
           OR ci.id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND ci.captured_at BETWEEN $3 AND $4
      AND ee.confidence >= 0.7
    GROUP BY ee.entity_text, ee.entity_type
    ORDER BY count DESC
    LIMIT 20
"""

SQL_SOURCE_IDENTIFIER_OVERLAP = """
    SELECT io.identifier_type, io.identifier_value,
           COUNT(DISTINCT io2.source_id) AS source_count
    FROM identifier_occurrences io
    JOIN content_items ci ON io.content_item_id = ci.id
    JOIN identifier_occurrences io2 ON io2.identifier_type = io.identifier_type
                                   AND io2.identifier_value = io.identifier_value
                                   AND io2.source_id != io.source_id
    WHERE ci.source_id = $2
      AND (ci.topic_id = $1
           OR ci.id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND ci.captured_at BETWEEN $3 AND $4
    GROUP BY io.identifier_type, io.identifier_value
    HAVING COUNT(DISTINCT io2.source_id) >= 1
    ORDER BY source_count DESC
    LIMIT 20
"""

SQL_SOURCE_CLUSTER_PARTICIPATION = """
    SELECT nc.id AS cluster_id,
           nc.label AS label,
           COUNT(*) AS item_count,
           MIN(ci.captured_at) AS first_post_in_cluster
    FROM content_items ci
    JOIN narrative_clusters nc ON ci.narrative_cluster_id = nc.id
    WHERE ci.source_id = $2
      AND (ci.topic_id = $1
           OR ci.id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND ci.captured_at BETWEEN $3 AND $4
      AND ci.narrative_cluster_id IS NOT NULL
    GROUP BY nc.id, nc.label
    ORDER BY item_count DESC
"""

SQL_SOURCE_SENTIMENT = """
    SELECT
        COUNT(*) FILTER (WHERE (labels->'sentiment'->>'compound')::float < -0.05) AS negative,
        COUNT(*) FILTER (WHERE (labels->'sentiment'->>'compound')::float BETWEEN -0.05 AND 0.05) AS neutral,
        COUNT(*) FILTER (WHERE (labels->'sentiment'->>'compound')::float > 0.05) AS positive
    FROM content_items
    WHERE source_id = $2
      AND (topic_id = $1
           OR id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND captured_at BETWEEN $3 AND $4
      AND labels->'sentiment'->>'compound' IS NOT NULL
"""

SQL_SOURCE_CREDIBILITY_TRAJECTORY = """
    SELECT old_score, new_score, reason, created_at
    FROM credibility_audit_log
    WHERE source_id = $1
    ORDER BY created_at DESC
    LIMIT 20
"""

SQL_SOURCE_SNAPSHOT = """
    SELECT s.id, s.name, s.credibility_score
    FROM sources s WHERE s.id = $1
"""


# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------


async def insert_assessment(
    conn: DBConnection,
    *,
    assessment_id: str,
    topic_id: str,
    source_id: str,
    org_id: str,
    time_window_start: datetime,
    time_window_end: datetime,
    stats_json: str,
    content_item_count: int,
    source_snapshot_json: str,
    now: datetime,
    labels_json: str,
) -> None:
    """Insert a new source assessment. ON CONFLICT DO NOTHING for dedup."""
    await conn.execute(
        SQL_INSERT_ASSESSMENT,
        assessment_id,
        topic_id,
        source_id,
        org_id,
        time_window_start,
        time_window_end,
        stats_json,
        content_item_count,
        source_snapshot_json,
        now,
        labels_json,
    )


async def fetch_assessment(conn: DBConnection, assessment_id: str) -> dict[str, Any] | None:
    """Fetch a single assessment by ID."""
    row = await conn.fetchrow(SQL_FETCH_ASSESSMENT, assessment_id)
    return dict(row) if row else None


async def list_assessments(
    conn: DBConnection, topic_id: str, source_id: str
) -> list[dict[str, Any]]:
    """List all assessments for a source in a topic, newest first."""
    rows = await conn.fetch(SQL_LIST_ASSESSMENTS, topic_id, source_id)
    return [dict(r) for r in rows]


async def count_source_content(
    conn: DBConnection,
    topic_id: str,
    source_id: str,
    time_start: datetime,
    time_end: datetime,
) -> int:
    """Count content items for a source within a topic and time window."""
    result = await conn.fetchval(
        SQL_COUNT_SOURCE_CONTENT,
        topic_id,
        source_id,
        time_start,
        time_end,
    )
    return int(result or 0)


async def get_source_snapshot(conn: DBConnection, source_id: str) -> dict[str, Any]:
    """Get current source metadata for snapshot."""
    row = await conn.fetchrow(SQL_SOURCE_SNAPSHOT, source_id)
    if row is None:
        return {}
    return {row["id"]: {"name": row["name"], "credibility_score": row["credibility_score"]}}


async def compute_source_stats(
    conn: DBConnection,
    *,
    topic_id: str,
    source_id: str,
    org_id: str,
    time_start: datetime,
    time_end: datetime,
) -> dict[str, Any]:
    """Compute all deterministic stats for a source in a topic.

    Runs 9 SQL queries. All content queries are org-scoped via topic ownership.
    """
    params = (topic_id, source_id, time_start, time_end)

    # Post stats
    post_row = await conn.fetchrow(SQL_SOURCE_POST_STATS, *params)
    total_posts = int(post_row["total_posts"]) if post_row else 0
    first_post = post_row["first_post"] if post_row else None
    last_post = post_row["last_post"] if post_row else None

    # Calculate avg posts per day
    if first_post and last_post and first_post != last_post:
        days = max((last_post - first_post).total_seconds() / 86400, 1)
        avg_per_day = round(total_posts / days, 2)
    else:
        avg_per_day = float(total_posts)

    # Engagement
    eng_row = await conn.fetchrow(SQL_SOURCE_ENGAGEMENT, *params)
    engagement = {
        "likes": int(eng_row["likes"] or 0) if eng_row else 0,
        "comments": int(eng_row["comments"] or 0) if eng_row else 0,
        "shares": int(eng_row["shares"] or 0) if eng_row else 0,
        "views": int(eng_row["views"] or 0) if eng_row else 0,
    }

    # Language breakdown
    lang_rows = await conn.fetch(SQL_SOURCE_LANGUAGES, *params)
    total_lang = sum(r["count"] for r in lang_rows) or 1
    language_breakdown = [
        {
            "language": r["language"],
            "count": r["count"],
            "pct": round(r["count"] / total_lang * 100, 1),
        }
        for r in lang_rows
    ]

    # Volume timeline
    vol_rows = await conn.fetch(SQL_SOURCE_VOLUME_TIMELINE, *params)
    volume_timeline = [{"date": str(r["date"]), "count": r["count"]} for r in vol_rows]

    # Top entities
    ent_rows = await conn.fetch(SQL_SOURCE_TOP_ENTITIES, *params)
    top_entities = [
        {"entity_text": r["entity_text"], "entity_type": r["entity_type"], "count": r["count"]}
        for r in ent_rows
    ]

    # Identifier overlap (Engine C)
    try:
        id_rows = await conn.fetch(SQL_SOURCE_IDENTIFIER_OVERLAP, *params)
        identifier_overlap = [
            {
                "identifier_type": r["identifier_type"],
                "identifier_value": r["identifier_value"],
                "source_count": r["source_count"],
            }
            for r in id_rows
        ]
    except asyncpg.PostgresError as exc:
        # identifier_occurrences table may not exist in all deployments
        log.info("assessment.identifier_overlap_skipped", reason=type(exc).__name__, error=str(exc))
        identifier_overlap = []

    # Cluster participation
    cluster_rows = await conn.fetch(SQL_SOURCE_CLUSTER_PARTICIPATION, *params)
    cluster_participation = [
        {
            "cluster_id": r["cluster_id"],
            "label": r["label"] or "Unlabeled",
            "item_count": r["item_count"],
        }
        for r in cluster_rows
    ]

    # Sentiment distribution
    sent_row = await conn.fetchrow(SQL_SOURCE_SENTIMENT, *params)
    sentiment_distribution = {
        "negative": int(sent_row["negative"] or 0) if sent_row else 0,
        "neutral": int(sent_row["neutral"] or 0) if sent_row else 0,
        "positive": int(sent_row["positive"] or 0) if sent_row else 0,
    }

    # Credibility trajectory (source-scoped, not topic-scoped)
    cred_rows = await conn.fetch(SQL_SOURCE_CREDIBILITY_TRAJECTORY, source_id)
    credibility_trajectory = [
        {
            "old_score": r["old_score"],
            "new_score": r["new_score"],
            "reason": r["reason"],
            "date": str(r["created_at"]),
        }
        for r in cred_rows
    ]

    return {
        "total_posts": total_posts,
        "first_post": first_post.isoformat() if first_post else None,
        "last_post": last_post.isoformat() if last_post else None,
        "avg_posts_per_day": avg_per_day,
        "engagement": engagement,
        "language_breakdown": language_breakdown,
        "volume_timeline": volume_timeline,
        "top_entities": top_entities,
        "identifier_overlap": identifier_overlap,
        "cluster_participation": cluster_participation,
        "sentiment_distribution": sentiment_distribution,
        "credibility_trajectory": credibility_trajectory,
    }
