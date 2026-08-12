"""Topic repository — all SQL for the topics domain."""
from __future__ import annotations

import json
from typing import Any, Optional

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_INSERT_TOPIC = """
    INSERT INTO topics (
        id, name, keywords, languages, credibility_min, signal_threshold,
        status, clip_categories, scheduled_report_cron, scheduled_report_type,
        created_at, updated_at, labels, org_id, identifier_signal_threshold
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
"""
# Param order: topic_id, name, keywords, languages, credibility_min,
# signal_threshold, status, clip_categories, scheduled_report_cron,
# scheduled_report_type, created_at, updated_at, labels_json, org_id,
# identifier_signal_threshold

SQL_LIST_TOPICS = """
    SELECT t.id, t.name, t.status, t.signal_threshold, t.credibility_min, t.created_at,
           (SELECT COUNT(DISTINCT x.id) FROM (
               SELECT ci.id FROM content_items ci WHERE ci.topic_id = t.id
               UNION
               SELECT tci.content_item_id FROM topic_content_items tci WHERE tci.topic_id = t.id
           ) x) AS content_count,
           COUNT(DISTINCT sig.id) FILTER (WHERE sig.status = 'new') AS signal_count,
           (SELECT COUNT(DISTINCT x2.id) FROM (
               SELECT ci2.id FROM content_items ci2
               WHERE ci2.topic_id = t.id AND ci2.captured_at >= NOW() - INTERVAL '24 hours'
               UNION
               SELECT tci2.content_item_id FROM topic_content_items tci2
               JOIN content_items ci3 ON ci3.id = tci2.content_item_id
               WHERE tci2.topic_id = t.id AND ci3.captured_at >= NOW() - INTERVAL '24 hours'
           ) x2) AS new_content_24h,
           (SELECT CASE COALESCE(
               MIN(CASE src.health_status
                   WHEN 'down' THEN 1
                   WHEN 'degraded' THEN 2
                   ELSE 3
               END), 3)
               WHEN 1 THEN 'down'
               WHEN 2 THEN 'degraded'
               ELSE 'healthy'
            END
            FROM topic_sources ts2
            JOIN sources src ON src.id = ts2.source_id
            WHERE ts2.topic_id = t.id
           ) AS worst_source_health,
           (SELECT MAX(la.captured_at) FROM (
               SELECT ci4.captured_at FROM content_items ci4 WHERE ci4.topic_id = t.id
               UNION ALL
               SELECT ci5.captured_at FROM topic_content_items tci3
               JOIN content_items ci5 ON ci5.id = tci3.content_item_id
               WHERE tci3.topic_id = t.id
           ) la) AS last_activity
    FROM topics t
    LEFT JOIN signals sig ON sig.topic_id = t.id
    GROUP BY t.id
    ORDER BY t.created_at DESC
"""

SQL_LIST_TOPICS_BY_ORG = """
    SELECT t.id, t.name, t.status, t.signal_threshold, t.credibility_min, t.created_at,
           (SELECT COUNT(DISTINCT x.id) FROM (
               SELECT ci.id FROM content_items ci WHERE ci.topic_id = t.id
               UNION
               SELECT tci.content_item_id FROM topic_content_items tci WHERE tci.topic_id = t.id
           ) x) AS content_count,
           COUNT(DISTINCT sig.id) FILTER (WHERE sig.status = 'new') AS signal_count,
           (SELECT COUNT(DISTINCT x2.id) FROM (
               SELECT ci2.id FROM content_items ci2
               WHERE ci2.topic_id = t.id AND ci2.captured_at >= NOW() - INTERVAL '24 hours'
               UNION
               SELECT tci2.content_item_id FROM topic_content_items tci2
               JOIN content_items ci3 ON ci3.id = tci2.content_item_id
               WHERE tci2.topic_id = t.id AND ci3.captured_at >= NOW() - INTERVAL '24 hours'
           ) x2) AS new_content_24h,
           (SELECT CASE COALESCE(
               MIN(CASE src.health_status
                   WHEN 'down' THEN 1
                   WHEN 'degraded' THEN 2
                   ELSE 3
               END), 3)
               WHEN 1 THEN 'down'
               WHEN 2 THEN 'degraded'
               ELSE 'healthy'
            END
            FROM topic_sources ts2
            JOIN sources src ON src.id = ts2.source_id
            WHERE ts2.topic_id = t.id
           ) AS worst_source_health,
           (SELECT MAX(la.captured_at) FROM (
               SELECT ci4.captured_at FROM content_items ci4 WHERE ci4.topic_id = t.id
               UNION ALL
               SELECT ci5.captured_at FROM topic_content_items tci3
               JOIN content_items ci5 ON ci5.id = tci3.content_item_id
               WHERE tci3.topic_id = t.id
           ) la) AS last_activity
    FROM topics t
    LEFT JOIN signals sig ON sig.topic_id = t.id
    WHERE t.org_id = $1
    GROUP BY t.id
    ORDER BY t.created_at DESC
"""

SQL_GET_TOPIC = """
    SELECT t.*,
           (SELECT COUNT(DISTINCT x.id) FROM (
               SELECT ci.id FROM content_items ci WHERE ci.topic_id = t.id
               UNION
               SELECT tci.content_item_id FROM topic_content_items tci WHERE tci.topic_id = t.id
           ) x) AS content_count,
           COUNT(DISTINCT sig.id) FILTER (WHERE sig.status = 'new') AS signal_count
    FROM topics t
    LEFT JOIN signals sig ON sig.topic_id = t.id
    WHERE t.id = $1
    GROUP BY t.id
"""

SQL_GET_TOPIC_ORG = "SELECT org_id FROM topics WHERE id = $1"

SQL_CHECK_TOPIC_EXISTS = "SELECT id FROM topics WHERE id = $1"

SQL_UPDATE_TOPIC_STATUS = "UPDATE topics SET status=$1, updated_at=$2 WHERE id=$3"

SQL_GET_TOPIC_ENTITIES = """
    SELECT ee.entity_type, ee.entity_text, COUNT(*) as mention_count,
           AVG(ee.confidence) as avg_confidence
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE (ci.topic_id = $1
       OR ci.id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND ci.captured_at >= NOW() - make_interval(days => $2)
    GROUP BY ee.entity_type, ee.entity_text
    ORDER BY mention_count DESC
    LIMIT 100
"""

SQL_GET_TOPIC_CLUSTERS = """
    SELECT nc.id, nc.label, nc.item_count, nc.independent_source_count,
           nc.executive_summary, nc.created_at
    FROM narrative_clusters nc
    WHERE nc.topic_id = $1
      AND nc.archived_at IS NULL
    ORDER BY nc.item_count DESC
"""

SQL_CLUSTER_SOURCES = """
    SELECT DISTINCT ON (src.id)
           src.url_or_handle AS source_name,
           src.platform,
           src.credibility_score
    FROM content_items ci
    JOIN sources src ON src.id = ci.source_id
    WHERE ci.narrative_cluster_id = $1
      AND COALESCE(ci.content_quality, 'good') != 'low_quality'
    ORDER BY src.id, src.credibility_score DESC
"""

# ---------------------------------------------------------------------------
# Cluster search — centroid semantic search + ILIKE fallback + drill-down
# ---------------------------------------------------------------------------

SQL_CLUSTER_CENTROID_SEARCH = """
    SELECT nc.id, nc.label, nc.item_count, nc.independent_source_count,
           nc.executive_summary, nc.created_at,
           1 - (nc.embedding_centroid <=> $1::vector) AS similarity_score
    FROM narrative_clusters nc
    WHERE nc.topic_id = $2
      AND nc.archived_at IS NULL
      AND nc.embedding_centroid IS NOT NULL
      AND 1 - (nc.embedding_centroid <=> $1::vector) >= $3
    ORDER BY nc.embedding_centroid <=> $1::vector
    LIMIT $4
"""

SQL_CLUSTER_LABEL_SEARCH = """
    SELECT nc.id, nc.label, nc.item_count, nc.independent_source_count,
           nc.executive_summary, nc.created_at,
           NULL::float AS similarity_score
    FROM narrative_clusters nc
    WHERE nc.topic_id = $1
      AND nc.archived_at IS NULL
      AND (
          nc.label ILIKE '%' || $2 || '%'
          OR nc.executive_summary ILIKE '%' || $2 || '%'
      )
    ORDER BY nc.item_count DESC
    LIMIT $3
"""

SQL_CLUSTER_CONTENT_BY_RELEVANCE = """
    SELECT ci.id, ci.url, ci.title,
           LEFT(ci.clean_text, 500) AS clean_text,
           LEFT(ci.translated_text, 500) AS translated_text,
           ci.language, ci.captured_at,
           ci.credibility_score_at_capture,
           ci.labels,
           s.name AS source_name, s.platform,
           1 - (ci.embedding <=> $1::vector) AS similarity_score
    FROM content_items ci
    LEFT JOIN sources s ON s.id = ci.source_id
    WHERE ci.narrative_cluster_id = $2
      AND ci.embedding IS NOT NULL
      AND COALESCE(ci.content_quality, 'good') != 'low_quality'
    ORDER BY ci.embedding <=> $1::vector
    LIMIT $3 OFFSET $4
"""

SQL_CLUSTER_CONTENT_BY_TIME = """
    SELECT ci.id, ci.url, ci.title,
           LEFT(ci.clean_text, 500) AS clean_text,
           LEFT(ci.translated_text, 500) AS translated_text,
           ci.language, ci.captured_at,
           ci.credibility_score_at_capture,
           ci.labels,
           s.name AS source_name, s.platform,
           NULL::float AS similarity_score
    FROM content_items ci
    LEFT JOIN sources s ON s.id = ci.source_id
    WHERE ci.narrative_cluster_id = $1
      AND COALESCE(ci.content_quality, 'good') != 'low_quality'
    ORDER BY ci.captured_at DESC
    LIMIT $2 OFFSET $3
"""

SQL_VERIFY_CLUSTER_TOPIC = """
    SELECT topic_id FROM narrative_clusters WHERE id = $1
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
    *,
    org_id: Optional[str] = None,
    identifier_signal_threshold: int = 2,
) -> None:
    await conn.execute(
        SQL_INSERT_TOPIC,
        topic_id, name, keywords, languages,
        credibility_min, signal_threshold, "active",
        clip_categories, scheduled_report_cron, scheduled_report_type,
        now, now, labels_json, org_id, identifier_signal_threshold,
    )


async def list_topics(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_TOPICS)
    return [dict(r) for r in rows]


async def list_topics_by_org(
    conn: asyncpg.Connection,
    org_id: str,
) -> list[dict[str, Any]]:
    """Return topics filtered by organization."""
    rows = await conn.fetch(SQL_LIST_TOPICS_BY_ORG, org_id)
    return [dict(r) for r in rows]


async def verify_topic_access(
    conn: asyncpg.Connection,
    topic_id: str,
    user: dict,
) -> None:
    """Raise 404 if topic doesn't belong to user's org (unless super-admin)."""
    from ..auth.rbac import is_super_admin, get_user_org

    if is_super_admin(user):
        return
    row = await conn.fetchrow(SQL_GET_TOPIC_ORG, topic_id)
    if not row or row["org_id"] != get_user_org(user):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Topic not found")


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


SQL_UPDATE_TOPIC_SCHEDULE = """
    UPDATE topics
    SET scheduled_report_cron = $1,
        scheduled_report_type = $2,
        updated_at = NOW()
    WHERE id = $3
"""


async def update_topic_schedule(
    conn: asyncpg.Connection,
    topic_id: str,
    scheduled_report_cron: str | None,
    scheduled_report_type: str | None,
) -> None:
    """Update or clear scheduled report configuration."""
    await conn.execute(
        SQL_UPDATE_TOPIC_SCHEDULE,
        scheduled_report_cron, scheduled_report_type, topic_id,
    )


_DEFAULT_RELEVANCE_THRESHOLD = 0.35  # must match analyst settings.topic_relevance_threshold


async def get_topic_content(
    conn: asyncpg.Connection,
    topic_id: str,
    limit: int,
    offset: int,
    has_embedding: Optional[bool],
    platform: Optional[str],
    include_low_quality: bool = False,
    sentiment: Optional[str] = None,
    relevance_threshold: Optional[float] = None,
    sort_by: str = "captured_at",
) -> list[dict[str, Any]]:
    if has_embedding is True:
        emb_clause = "AND ci.embedding IS NOT NULL"
    elif has_embedding is False:
        emb_clause = "AND ci.embedding IS NULL"
    else:
        emb_clause = ""

    quality_clause = "" if include_low_quality else "AND COALESCE(ci.content_quality, 'good') != 'low_quality'"

    # Build positional params: $1=topic_id, $2=limit, $3=offset, then dynamic
    params: list[Any] = [topic_id, limit, offset]
    next_param = 4

    if platform:
        platform_clause = f"AND s.platform = ${next_param}"
        params.append(platform)
        next_param += 1
    else:
        platform_clause = ""

    threshold = relevance_threshold if relevance_threshold is not None else _DEFAULT_RELEVANCE_THRESHOLD
    relevance_clause = f"AND (ci.topic_relevance_score IS NULL OR ci.topic_relevance_score >= ${next_param})"
    params.append(threshold)
    next_param += 1

    if sentiment == "positive":
        sentiment_clause = "AND (ci.labels->'sentiment'->>'compound')::float >= 0.05"
    elif sentiment == "negative":
        sentiment_clause = "AND (ci.labels->'sentiment'->>'compound')::float <= -0.05"
    elif sentiment == "neutral":
        sentiment_clause = (
            "AND (ci.labels->'sentiment'->>'compound')::float > -0.05"
            " AND (ci.labels->'sentiment'->>'compound')::float < 0.05"
        )
    else:
        sentiment_clause = ""

    # Determine ORDER BY clause — only two allowed values (not user input)
    if sort_by == "relevance":
        order_clause = "ORDER BY COALESCE(topic_relevance_score, 0) DESC, captured_at DESC"
    else:
        order_clause = "ORDER BY captured_at DESC"

    # Use a CTE to dedup on clean_hash — show newest item per unique clean_hash,
    # with a count of how many duplicates were collapsed.
    sql = f"""
        WITH all_items AS (
            SELECT ci.id,
                   ci.url,
                   ci.title,
                   LEFT(ci.clean_text, 500) AS clean_text,
                   LEFT(ci.translated_text, 500) AS translated_text,
                   ci.language,
                   ci.credibility_score_at_capture,
                   ci.captured_at,
                   ci.clean_hash,
                   ci.labels,
                   ci.topic_relevance_score,
                   s.name AS source_name,
                   s.platform,
                   FALSE AS backfilled
            FROM content_items ci
            LEFT JOIN sources s ON s.id = ci.source_id
            WHERE ci.topic_id = $1
              {quality_clause}
              {emb_clause}
              {platform_clause}
              {relevance_clause}
              {sentiment_clause}

            UNION ALL

            SELECT ci.id,
                   ci.url,
                   ci.title,
                   LEFT(ci.clean_text, 500) AS clean_text,
                   LEFT(ci.translated_text, 500) AS translated_text,
                   ci.language,
                   ci.credibility_score_at_capture,
                   ci.captured_at,
                   ci.clean_hash,
                   ci.labels,
                   ci.topic_relevance_score,
                   s.name AS source_name,
                   s.platform,
                   TRUE AS backfilled
            FROM topic_content_items tci
            JOIN content_items ci ON ci.id = tci.content_item_id
            LEFT JOIN sources s ON s.id = ci.source_id
            WHERE tci.topic_id = $1
              {quality_clause}
              {emb_clause}
              {platform_clause}
              {relevance_clause}
              {sentiment_clause}
        ),
        deduped AS (
            SELECT DISTINCT ON (COALESCE(clean_hash, id))
                   id, url, title, clean_text, translated_text,
                   language, credibility_score_at_capture, captured_at,
                   clean_hash, labels, topic_relevance_score,
                   source_name, platform, backfilled
            FROM all_items
            ORDER BY COALESCE(clean_hash, id), captured_at DESC
        ),
        with_counts AS (
            SELECT d.*,
                   COALESCE(dup.cnt, 1) AS duplicate_count
            FROM deduped d
            LEFT JOIN (
                SELECT COALESCE(clean_hash, id) AS hash_key, COUNT(*) AS cnt
                FROM all_items
                GROUP BY COALESCE(clean_hash, id)
            ) dup ON COALESCE(d.clean_hash, d.id) = dup.hash_key
        )
        SELECT id, url, title, clean_text, translated_text,
               language, credibility_score_at_capture, captured_at,
               source_name, platform, backfilled, duplicate_count, labels,
               topic_relevance_score,
               EXISTS (
                   SELECT 1 FROM media_assets ma
                   JOIN vision_results vr ON vr.media_asset_id = ma.id
                   WHERE ma.content_item_id = with_counts.id
               ) AS has_vision
        FROM with_counts
        {order_clause}
        LIMIT $2 OFFSET $3
    """  # nosec B608 — clauses are internal strings, not user input; platform is parameterized as $4
    rows = await conn.fetch(sql, *params)
    results = []
    for r in rows:
        d = dict(r)
        labels = d.pop("labels", None) or {}
        if isinstance(labels, str):
            labels = json.loads(labels)
        if not isinstance(labels, dict):
            labels = {}
        d["sentiment"] = labels.get("sentiment")
        d["keywords"] = labels.get("keywords", [])
        d["scam_template"] = labels.get("scam_template")
        d["template_confidence"] = labels.get("template_confidence")
        d["has_vision"] = d.get("has_vision", False)
        # Round relevance score to 2 decimals for display
        raw_rel = d.get("topic_relevance_score")
        d["topic_relevance_score"] = round(raw_rel, 2) if raw_rel is not None else None
        results.append(d)
    return results


SQL_SENTIMENT_TREND = """
    SELECT DATE(captured_at) AS date,
           AVG((labels->'sentiment'->>'compound')::float) AS avg_compound,
           COUNT(*) AS item_count
    FROM content_items
    WHERE (topic_id = $1
       OR id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND captured_at >= NOW() - make_interval(days => $2)
      AND labels->'sentiment' IS NOT NULL
    GROUP BY DATE(captured_at)
    ORDER BY date ASC
"""

SQL_TRENDING_KEYWORDS = """
    SELECT kw, COUNT(*) AS frequency
    FROM content_items,
         jsonb_array_elements_text(labels->'keywords') AS kw
    WHERE (topic_id = $1
       OR id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND captured_at >= NOW() - make_interval(days => $2)
      AND labels->'keywords' IS NOT NULL
    GROUP BY kw
    ORDER BY frequency DESC
    LIMIT $3
"""


async def get_sentiment_trend(
    conn: asyncpg.Connection,
    topic_id: str,
    days: int = 30,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_SENTIMENT_TREND, topic_id, days)
    return [
        {
            "date": str(r["date"]),
            "avg_compound": round(float(r["avg_compound"]), 4),
            "item_count": r["item_count"],
        }
        for r in rows
    ]


async def get_trending_keywords(
    conn: asyncpg.Connection,
    topic_id: str,
    days: int = 7,
    limit: int = 15,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_TRENDING_KEYWORDS, topic_id, days, limit)
    return [{"keyword": r["kw"], "frequency": r["frequency"]} for r in rows]


async def get_topic_entities(
    conn: asyncpg.Connection, topic_id: str, days: int = 30
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_GET_TOPIC_ENTITIES, topic_id, days)
    return [dict(r) for r in rows]


async def get_topic_clusters(
    conn: asyncpg.Connection, topic_id: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_GET_TOPIC_CLUSTERS, topic_id)
    clusters = []
    for r in rows:
        c = dict(r)
        # Enrich with source breakdown
        source_rows = await conn.fetch(SQL_CLUSTER_SOURCES, c["id"])
        c["sources"] = [
            {
                "source_name": sr["source_name"],
                "platform": sr["platform"],
                "credibility_score": float(sr["credibility_score"]),
            }
            for sr in source_rows
        ]
        clusters.append(c)
    return clusters


# ---------------------------------------------------------------------------
# Cluster search — centroid semantic search + ILIKE fallback + drill-down
# ---------------------------------------------------------------------------

_MIN_CLUSTER_SIMILARITY = 0.15  # MiniLM-L6 query-to-centroid scores are lower than inter-cluster


def _relevance_tier(score: float | None) -> str:
    """Convert raw cosine similarity to analyst-friendly tier.

    Calibrated for all-MiniLM-L6-v2 (384d) query-to-centroid scores,
    which are significantly lower than document-to-document scores.
    """
    if score is None:
        return "keyword"
    if score >= 0.45:
        return "high"
    if score >= 0.30:
        return "medium"
    return "low"


async def _enrich_clusters(
    conn: asyncpg.Connection,
    rows: list[asyncpg.Record],
) -> list[dict[str, Any]]:
    """Add source breakdown and relevance tier to cluster rows."""
    clusters = []
    for r in rows:
        c = dict(r)
        c["relevance_tier"] = _relevance_tier(c.get("similarity_score"))
        if c.get("similarity_score") is not None:
            c["similarity_score"] = round(float(c["similarity_score"]), 4)
        source_rows = await conn.fetch(SQL_CLUSTER_SOURCES, c["id"])
        c["sources"] = [
            {
                "source_name": sr["source_name"],
                "platform": sr["platform"],
                "credibility_score": float(sr["credibility_score"]),
            }
            for sr in source_rows
        ]
        clusters.append(c)
    return clusters


async def search_clusters_by_centroid(
    conn: asyncpg.Connection,
    query_vec_str: str,
    topic_id: str,
    min_similarity: float = _MIN_CLUSTER_SIMILARITY,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Semantic search: rank clusters by centroid cosine similarity."""
    rows = await conn.fetch(
        SQL_CLUSTER_CENTROID_SEARCH,
        query_vec_str, topic_id, min_similarity, limit,
    )
    return await _enrich_clusters(conn, rows)


async def search_clusters_by_label(
    conn: asyncpg.Connection,
    query_text: str,
    topic_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """ILIKE fallback: search cluster labels and executive summaries."""
    rows = await conn.fetch(
        SQL_CLUSTER_LABEL_SEARCH,
        topic_id, query_text, limit,
    )
    return await _enrich_clusters(conn, rows)


async def get_cluster_content(
    conn: asyncpg.Connection,
    cluster_id: str,
    sort: str = "time",
    query_vec_str: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return content items within a cluster, optionally ranked by query similarity."""
    if sort == "relevance" and query_vec_str:
        rows = await conn.fetch(
            SQL_CLUSTER_CONTENT_BY_RELEVANCE,
            query_vec_str, cluster_id, limit, offset,
        )
    else:
        rows = await conn.fetch(
            SQL_CLUSTER_CONTENT_BY_TIME,
            cluster_id, limit, offset,
        )
    results = []
    for r in rows:
        d = dict(r)
        if d.get("similarity_score") is not None:
            d["similarity_score"] = round(float(d["similarity_score"]), 4)
            d["relevance_tier"] = _relevance_tier(d["similarity_score"])
        # Extract sentiment from labels JSONB
        raw_labels = d.pop("labels", None)
        if raw_labels:
            labels = json.loads(raw_labels) if isinstance(raw_labels, str) else raw_labels
            if isinstance(labels, dict) and "sentiment" in labels:
                d["sentiment"] = labels["sentiment"]
        results.append(d)
    return results


async def verify_cluster_belongs_to_topic(
    conn: asyncpg.Connection,
    cluster_id: str,
    topic_id: str,
) -> bool:
    """Verify cluster exists and belongs to the given topic (multi-tenancy guard)."""
    row = await conn.fetchrow(SQL_VERIFY_CLUSTER_TOPIC, cluster_id)
    return row is not None and row["topic_id"] == topic_id
