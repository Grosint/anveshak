"""Topic repository — all SQL for the topics domain."""
from __future__ import annotations

from typing import Any, Optional

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_INSERT_TOPIC = """
    INSERT INTO topics (
        id, name, keywords, languages, credibility_min, signal_threshold,
        status, clip_categories, scheduled_report_cron, scheduled_report_type,
        created_at, updated_at, labels
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
"""

SQL_LIST_TOPICS = """
    SELECT t.id, t.name, t.status, t.signal_threshold, t.credibility_min, t.created_at,
           COUNT(DISTINCT ci.id) AS content_count,
           COUNT(DISTINCT sig.id) FILTER (WHERE sig.status = 'new') AS signal_count
    FROM topics t
    LEFT JOIN content_items ci ON ci.topic_id = t.id
    LEFT JOIN signals sig ON sig.topic_id = t.id
    GROUP BY t.id
    ORDER BY t.created_at DESC
"""

SQL_GET_TOPIC = "SELECT * FROM topics WHERE id = $1"

SQL_CHECK_TOPIC_EXISTS = "SELECT id FROM topics WHERE id = $1"

SQL_UPDATE_TOPIC_STATUS = "UPDATE topics SET status=$1, updated_at=$2 WHERE id=$3"

SQL_GET_TOPIC_ENTITIES = """
    SELECT ee.entity_type, ee.entity_text, COUNT(*) as mention_count,
           AVG(ee.confidence) as avg_confidence
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE ci.topic_id = $1
    GROUP BY ee.entity_type, ee.entity_text
    ORDER BY mention_count DESC
    LIMIT 100
"""

SQL_GET_TOPIC_CLUSTERS = """
    SELECT id, label, item_count, independent_source_count, created_at
    FROM narrative_clusters
    WHERE topic_id = $1
    ORDER BY item_count DESC
"""

_CONTENT_SELECT = """
    SELECT ci.id,
           ci.url,
           LEFT(ci.clean_text, 500) AS clean_text,
           ci.language,
           ci.credibility_score_at_capture,
           ci.captured_at,
           s.name AS source_name,
           s.platform,
           {backfilled} AS backfilled
    FROM {from_clause}
    WHERE {where_topic}
      {emb_clause}
      {platform_clause}
"""


# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------

async def insert_topic(
    conn: asyncpg.Connection,
    topic_id: str,
    name: str,
    keywords: list[str],
    languages: list[str],
    credibility_min: float,
    signal_threshold: int,
    clip_categories: list[str],
    scheduled_report_cron: Optional[str],
    scheduled_report_type: Optional[str],
    now: Any,
    labels_json: str,
) -> None:
    await conn.execute(
        SQL_INSERT_TOPIC,
        topic_id, name, keywords, languages,
        credibility_min, signal_threshold, "active",
        clip_categories, scheduled_report_cron, scheduled_report_type,
        now, now, labels_json,
    )


async def list_topics(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_TOPICS)
    return [dict(r) for r in rows]


async def get_topic(conn: asyncpg.Connection, topic_id: str) -> dict[str, Any] | None:
    row = await conn.fetchrow(SQL_GET_TOPIC, topic_id)
    return dict(row) if row else None


async def topic_exists(conn: asyncpg.Connection, topic_id: str) -> bool:
    row = await conn.fetchrow(SQL_CHECK_TOPIC_EXISTS, topic_id)
    return row is not None


async def update_topic_status(
    conn: asyncpg.Connection,
    topic_id: str,
    status: str,
    now: Any,
) -> None:
    await conn.execute(SQL_UPDATE_TOPIC_STATUS, status, now, topic_id)


async def get_topic_content(
    conn: asyncpg.Connection,
    topic_id: str,
    limit: int,
    offset: int,
    has_embedding: Optional[bool],
    platform: Optional[str],
) -> list[dict[str, Any]]:
    if has_embedding is True:
        emb_clause = "AND ci.embedding IS NOT NULL"
    elif has_embedding is False:
        emb_clause = "AND ci.embedding IS NULL"
    else:
        emb_clause = ""

    platform_clause = "AND s.platform = $4" if platform else ""
    params: list[Any] = [topic_id, limit, offset]
    if platform:
        params.append(platform)

    sql = f"""
        SELECT ci.id,
               ci.url,
               LEFT(ci.clean_text, 500) AS clean_text,
               ci.language,
               ci.credibility_score_at_capture,
               ci.captured_at,
               s.name AS source_name,
               s.platform,
               FALSE AS backfilled
        FROM content_items ci
        LEFT JOIN sources s ON s.id = ci.source_id
        WHERE ci.topic_id = $1
          {emb_clause}
          {platform_clause}

        UNION ALL

        SELECT ci.id,
               ci.url,
               LEFT(ci.clean_text, 500) AS clean_text,
               ci.language,
               ci.credibility_score_at_capture,
               ci.captured_at,
               s.name AS source_name,
               s.platform,
               TRUE AS backfilled
        FROM topic_content_items tci
        JOIN content_items ci ON ci.id = tci.content_item_id
        LEFT JOIN sources s ON s.id = ci.source_id
        WHERE tci.topic_id = $1
          {emb_clause}
          {platform_clause}

        ORDER BY captured_at DESC
        LIMIT $2 OFFSET $3
    """  # nosec B608 — emb_clause/platform_clause are internal boolean strings, not user input; user-controlled platform value is parameterized as $4
    rows = await conn.fetch(sql, *params)
    return [dict(r) for r in rows]


async def get_topic_entities(
    conn: asyncpg.Connection, topic_id: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_GET_TOPIC_ENTITIES, topic_id)
    return [dict(r) for r in rows]


async def get_topic_clusters(
    conn: asyncpg.Connection, topic_id: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_GET_TOPIC_CLUSTERS, topic_id)
    return [dict(r) for r in rows]
