"""Provenance repository — aggregated intelligence + provenance chain queries.

Issue #7: Provenance API endpoints for UX rewiring.
All SQL is module-level constants. Functions take asyncpg.Connection
and return plain dicts (route layer handles serialization).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg

# ---------------------------------------------------------------------------
# 1. Topic Intelligence — aggregated overview (single call)
# ---------------------------------------------------------------------------

SQL_INTELLIGENCE_SIGNALS = """
    SELECT s.id, s.signal_type, s.description, s.status,
           s.created_at AS fired_at,
           nc.label AS cluster_label,
           nc.independent_source_count AS isc
    FROM signals s
    LEFT JOIN narrative_clusters nc ON nc.id = s.cluster_id
    WHERE s.topic_id = $1
      AND s.status = 'new'
    ORDER BY s.created_at DESC
    LIMIT 20
"""

SQL_INTELLIGENCE_CLUSTERS = """
    SELECT nc.id, nc.label, nc.item_count, nc.independent_source_count AS isc,
           nc.executive_summary, nc.created_at,
           (SELECT COUNT(*) FROM content_items ci
            WHERE ci.narrative_cluster_id = nc.id
              AND ci.captured_at >= NOW() - INTERVAL '24 hours'
           ) AS growth_24h,
           CASE WHEN nc.item_count > 0
                THEN ROUND(
                    (SELECT COUNT(*) FROM content_items ci
                     WHERE ci.narrative_cluster_id = nc.id
                       AND ci.captured_at >= NOW() - INTERVAL '24 hours'
                    )::numeric / nc.item_count, 2)
                ELSE 0
           END AS growth_rate
    FROM narrative_clusters nc
    WHERE nc.topic_id = $1
      AND nc.archived_at IS NULL
    ORDER BY nc.independent_source_count DESC, nc.item_count DESC
    LIMIT $2
"""

SQL_INTELLIGENCE_IDENTIFIERS = """
    SELECT ee.entity_type AS identifier_type,
           ee.entity_text AS identifier_value,
           COUNT(DISTINCT ee.content_item_id) AS mention_count,
           COUNT(DISTINCT ci.source_id) AS source_count
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE ci.topic_id = $1
      AND ee.entity_type IN (
          'PHONE_IN', 'PHONE_INTL', 'UPI', 'EMAIL', 'CRYPTO_BTC', 'CRYPTO_ETH',
          'CRYPTO_TRC20', 'TELEGRAM_HANDLE', 'INSTAGRAM_HANDLE',
          'FACEBOOK_HANDLE', 'X_HANDLE',
          'URL_DOMAIN', 'GSTIN', 'UDYAM', 'PAN', 'IFSC',
          'BANK_ACCOUNT', 'SEBI_REG', 'AIRCRAFT_ID'
      )
    GROUP BY ee.entity_type, ee.entity_text
    ORDER BY mention_count DESC
    LIMIT $2
"""

SQL_INTELLIGENCE_LOCATIONS = """
    SELECT gl.entity_text_normalized AS location_name,
           gl.latitude, gl.longitude,
           COUNT(DISTINCT ee.content_item_id) AS content_count
    FROM geocoded_locations gl
    JOIN extracted_entities ee
        ON LOWER(ee.entity_text) = LOWER(gl.entity_text_normalized)
        AND ee.entity_type IN ('GPE', 'LOC', 'FAC')
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE ci.topic_id = $1
    GROUP BY gl.entity_text_normalized, gl.latitude, gl.longitude
    ORDER BY content_count DESC
    LIMIT $2
"""

SQL_INTELLIGENCE_SOURCE_HEALTH = """
    SELECT s.id, s.name, s.platform, s.health_status,
           s.credibility_score
    FROM topic_sources ts
    JOIN sources s ON s.id = ts.source_id
    WHERE ts.topic_id = $1
    ORDER BY s.name
"""

SQL_INTELLIGENCE_STATS = """
    SELECT
        (SELECT COUNT(DISTINCT x.id) FROM (
            SELECT ci.id FROM content_items ci WHERE ci.topic_id = $1
            UNION
            SELECT tci.content_item_id FROM topic_content_items tci WHERE tci.topic_id = $1
        ) x) AS total_content,
        (SELECT COUNT(*) FROM narrative_clusters nc
         WHERE nc.topic_id = $1 AND nc.archived_at IS NULL) AS total_clusters,
        (SELECT COUNT(*) FROM signals s
         WHERE s.topic_id = $1 AND s.status = 'new') AS total_signals
"""

# ---------------------------------------------------------------------------
# 2. Identifier Provenance — full chain for one identifier
# ---------------------------------------------------------------------------

SQL_IDENTIFIER_CONTENT_ITEMS = """
    SELECT ci.id, ci.title,
           LEFT(ci.clean_text, 200) AS snippet,
           ci.captured_at,
           s.platform
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    LEFT JOIN sources s ON s.id = ci.source_id
    WHERE ci.topic_id = $1
      AND LOWER(ee.entity_text) = LOWER($2)
    ORDER BY ci.captured_at DESC
    LIMIT 50
"""

SQL_IDENTIFIER_SOURCES = """
    SELECT DISTINCT ON (s.id)
           s.id, s.name, s.platform, s.credibility_score
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    JOIN sources s ON s.id = ci.source_id
    WHERE ci.topic_id = $1
      AND LOWER(ee.entity_text) = LOWER($2)
    ORDER BY s.id
"""

SQL_IDENTIFIER_CLUSTERS = """
    SELECT DISTINCT ON (nc.id)
           nc.id, nc.label, nc.independent_source_count AS isc,
           nc.item_count
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    JOIN narrative_clusters nc ON nc.id = ci.narrative_cluster_id
    WHERE ci.topic_id = $1
      AND LOWER(ee.entity_text) = LOWER($2)
    ORDER BY nc.id
"""

SQL_IDENTIFIER_SIGNALS = """
    SELECT DISTINCT ON (sig.id)
           sig.id, sig.status, sig.created_at AS fired_at
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    JOIN narrative_clusters nc ON nc.id = ci.narrative_cluster_id
    JOIN signals sig ON sig.cluster_id = nc.id
    WHERE ci.topic_id = $1
      AND LOWER(ee.entity_text) = LOWER($2)
    ORDER BY sig.id
"""

SQL_IDENTIFIER_CROSS_TOPIC = """
    SELECT t.name AS topic_name,
           COUNT(DISTINCT ee.content_item_id) AS mention_count
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    JOIN topics t ON t.id = ci.topic_id
    WHERE LOWER(ee.entity_text) = LOWER($1)
      AND ci.topic_id != $2
      AND t.org_id = $3
    GROUP BY t.name
    ORDER BY mention_count DESC
"""

# ---------------------------------------------------------------------------
# 3. Content Provenance — full chain for one content item
# ---------------------------------------------------------------------------

SQL_CONTENT_PROVENANCE = """
    SELECT ci.id, ci.url, ci.clean_text, ci.translated_text,
           ci.language, ci.captured_at, ci.content_hash,
           ci.credibility_score_at_capture,
           ci.topic_id, ci.narrative_cluster_id,
           s.id AS source_id, s.name AS source_name,
           s.platform AS source_platform,
           s.credibility_score AS source_credibility,
           nc.label AS cluster_label,
           nc.independent_source_count AS cluster_isc
    FROM content_items ci
    LEFT JOIN sources s ON s.id = ci.source_id
    LEFT JOIN narrative_clusters nc ON nc.id = ci.narrative_cluster_id
    WHERE ci.id = $1
"""

SQL_CONTENT_IDENTIFIERS = """
    SELECT ee.entity_type, ee.entity_text, ee.confidence
    FROM extracted_entities ee
    WHERE ee.content_item_id = $1
    ORDER BY ee.confidence DESC
"""

SQL_CONTENT_VISION = """
    SELECT vr.deepfake_score, vr.deepfake_model,
           vr.yolo_detections, vr.clip_labels,
           vr.synthetic_probability, vr.processed_at,
           ma.storage_path, ma.asset_type,
           ma.exif_data, ma.phash
    FROM vision_results vr
    JOIN media_assets ma ON ma.id = vr.media_asset_id
    WHERE ma.content_item_id = $1
"""

# ---------------------------------------------------------------------------
# 4. Cluster Provenance — enriched detail for one cluster
# ---------------------------------------------------------------------------

SQL_CLUSTER_HEADER = """
    SELECT nc.id, nc.label, nc.item_count,
           nc.independent_source_count AS isc,
           nc.executive_summary, nc.created_at,
           (SELECT COUNT(*) FROM content_items ci
            WHERE ci.narrative_cluster_id = nc.id
              AND ci.captured_at >= NOW() - INTERVAL '24 hours'
           ) AS growth_24h
    FROM narrative_clusters nc
    WHERE nc.id = $1 AND nc.topic_id = $2
"""

SQL_CLUSTER_SIGNAL = """
    SELECT s.id, s.status, s.created_at AS fired_at,
           s.signal_type, s.description,
           s.created_at AS threshold_crossed_at
    FROM signals s
    WHERE s.cluster_id = $1 AND s.topic_id = $2
    ORDER BY s.created_at DESC
    LIMIT 1
"""

SQL_CLUSTER_CONTENT_TIMELINE = """
    SELECT ci.id, ci.title,
           LEFT(ci.clean_text, 200) AS clean_text,
           ci.captured_at,
           s.id AS source_id, s.name AS source_name, s.platform
    FROM content_items ci
    LEFT JOIN sources s ON s.id = ci.source_id
    WHERE ci.narrative_cluster_id = $1
      AND ci.topic_id = $2
    ORDER BY ci.captured_at ASC
    LIMIT $3
"""

SQL_CLUSTER_IDENTIFIERS_RANKED = """
    SELECT ee.entity_type,
           LOWER(ee.entity_text) AS entity_text,
           COUNT(DISTINCT ee.content_item_id) AS mention_count,
           COUNT(DISTINCT ci.source_id) AS source_count
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE ci.narrative_cluster_id = $1
      AND ci.topic_id = $2
      AND ee.entity_type IN (
          'PHONE_IN', 'PHONE_INTL', 'UPI', 'EMAIL', 'CRYPTO_BTC', 'CRYPTO_ETH',
          'CRYPTO_TRC20', 'TELEGRAM_HANDLE', 'INSTAGRAM_HANDLE',
          'FACEBOOK_HANDLE', 'X_HANDLE',
          'URL_DOMAIN', 'GSTIN', 'UDYAM', 'PAN', 'IFSC',
          'BANK_ACCOUNT', 'SEBI_REG', 'AIRCRAFT_ID'
      )
    GROUP BY ee.entity_type, LOWER(ee.entity_text)
    ORDER BY mention_count DESC
    LIMIT 20
"""

SQL_CLUSTER_SOURCE_SPREAD = """
    SELECT s.id AS source_id, s.name AS source_name, s.platform,
           MIN(ci.captured_at) AS first_seen,
           MAX(ci.captured_at) AS last_seen,
           COUNT(*) AS item_count
    FROM content_items ci
    JOIN sources s ON s.id = ci.source_id
    WHERE ci.narrative_cluster_id = $1
      AND ci.topic_id = $2
    GROUP BY s.id, s.name, s.platform
    ORDER BY first_seen ASC
"""

# ---------------------------------------------------------------------------
# 5. Cluster Flow Graph — source-to-source information propagation
# ---------------------------------------------------------------------------

SQL_CLUSTER_FLOW_NODES = """
    SELECT s.id, s.name, s.platform,
           MIN(ci.captured_at) AS first_seen,
           COUNT(*) AS item_count
    FROM content_items ci
    JOIN sources s ON s.id = ci.source_id
    WHERE ci.narrative_cluster_id = $1
      AND ci.topic_id = $2
    GROUP BY s.id, s.name, s.platform
    ORDER BY first_seen ASC
"""

SQL_CLUSTER_FLOW_SHARED_IDENTIFIERS = """
    SELECT s1.id AS source_a, s2.id AS source_b,
           COUNT(DISTINCT ee1.entity_text) AS shared_count
    FROM content_items ci1
    JOIN sources s1 ON s1.id = ci1.source_id
    JOIN extracted_entities ee1 ON ee1.content_item_id = ci1.id
    JOIN extracted_entities ee2 ON LOWER(ee2.entity_text) = LOWER(ee1.entity_text)
         AND ee2.entity_type = ee1.entity_type
    JOIN content_items ci2 ON ci2.id = ee2.content_item_id
         AND ci2.narrative_cluster_id = $1 AND ci2.topic_id = $2
    JOIN sources s2 ON s2.id = ci2.source_id
    WHERE ci1.narrative_cluster_id = $1
      AND ci1.topic_id = $2
      AND s1.id < s2.id
    GROUP BY s1.id, s2.id
    HAVING COUNT(DISTINCT ee1.entity_text) >= 1
"""

# ---------------------------------------------------------------------------
# 6. Topic Urgency — metrics for dashboard sort
# ---------------------------------------------------------------------------

SQL_TOPIC_URGENCY = """
    SELECT
        (SELECT COUNT(*) FROM signals s
         WHERE s.topic_id = $1 AND s.status = 'new') AS unacked_signal_count,
        (SELECT COUNT(DISTINCT x.id) FROM (
            SELECT ci.id FROM content_items ci
            WHERE ci.topic_id = $1 AND ci.captured_at >= NOW() - INTERVAL '24 hours'
            UNION
            SELECT tci.content_item_id FROM topic_content_items tci
            JOIN content_items ci ON ci.id = tci.content_item_id
            WHERE tci.topic_id = $1 AND ci.captured_at >= NOW() - INTERVAL '24 hours'
        ) x) AS new_content_24h,
        (SELECT COALESCE(
            MIN(CASE s.health_status
                WHEN 'down' THEN 1
                WHEN 'degraded' THEN 2
                WHEN 'healthy' THEN 3
                ELSE 3
            END), 3)
         FROM topic_sources ts
         JOIN sources s ON s.id = ts.source_id
         WHERE ts.topic_id = $1
        ) AS worst_health_rank
"""


# ---------------------------------------------------------------------------
# Repository helpers — pool-based concurrent queries
# ---------------------------------------------------------------------------


async def _pool_fetch(
    pool: asyncpg.Pool, sql: str, *args: Any,
) -> list[asyncpg.Record]:
    """Execute pool.acquire() → conn.fetch() for use in asyncio.gather."""
    async with pool.acquire() as conn:
        return await conn.fetch(sql, *args)


async def _pool_fetchrow(
    pool: asyncpg.Pool, sql: str, *args: Any,
) -> asyncpg.Record | None:
    """Execute pool.acquire() → conn.fetchrow() for use in asyncio.gather."""
    async with pool.acquire() as conn:
        return await conn.fetchrow(sql, *args)


# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------

async def get_topic_intelligence(
    pool: asyncpg.Pool,
    topic_id: str,
    *,
    cluster_limit: int = 10,
    identifier_limit: int = 15,
    location_limit: int = 20,
) -> dict[str, Any]:
    """Aggregated intelligence overview for a topic — single API call.

    All 6 queries run concurrently via asyncio.gather, each acquiring
    its own connection from the pool (asyncpg connections are not safe
    for concurrent operations).
    """
    (signals, clusters, identifiers, locations,
     source_health, stats_row) = await asyncio.gather(
        _pool_fetch(pool, SQL_INTELLIGENCE_SIGNALS, topic_id),
        _pool_fetch(pool, SQL_INTELLIGENCE_CLUSTERS, topic_id, cluster_limit),
        _pool_fetch(pool, SQL_INTELLIGENCE_IDENTIFIERS, topic_id, identifier_limit),
        _pool_fetch(pool, SQL_INTELLIGENCE_LOCATIONS, topic_id, location_limit),
        _pool_fetch(pool, SQL_INTELLIGENCE_SOURCE_HEALTH, topic_id),
        _pool_fetchrow(pool, SQL_INTELLIGENCE_STATS, topic_id),
    )

    stats = dict(stats_row) if stats_row else {
        "total_content": 0, "total_clusters": 0, "total_signals": 0,
    }

    return {
        "signals": [dict(r) for r in signals],
        "clusters": [dict(r) for r in clusters],
        "identifiers": [dict(r) for r in identifiers],
        "locations": [dict(r) for r in locations],
        "source_health": [dict(r) for r in source_health],
        "stats": stats,
    }


async def get_identifier_provenance(
    pool: asyncpg.Pool,
    identifier_value: str,
    topic_id: str,
    org_id: str,
) -> dict[str, Any]:
    """Full provenance chain for one identifier within a topic.

    All 5 queries run concurrently via asyncio.gather, each acquiring
    its own connection from the pool.
    """
    (content_items, sources, clusters, signals_rows,
     cross_topic) = await asyncio.gather(
        _pool_fetch(pool, SQL_IDENTIFIER_CONTENT_ITEMS, topic_id, identifier_value),
        _pool_fetch(pool, SQL_IDENTIFIER_SOURCES, topic_id, identifier_value),
        _pool_fetch(pool, SQL_IDENTIFIER_CLUSTERS, topic_id, identifier_value),
        _pool_fetch(pool, SQL_IDENTIFIER_SIGNALS, topic_id, identifier_value),
        _pool_fetch(pool, SQL_IDENTIFIER_CROSS_TOPIC, identifier_value, topic_id, org_id),
    )

    return {
        "identifier_value": identifier_value,
        "topic_id": topic_id,
        "content_items": [dict(r) for r in content_items],
        "sources": [dict(r) for r in sources],
        "clusters": [dict(r) for r in clusters],
        "signals": [dict(r) for r in signals_rows],
        "cross_topic_appearances": [dict(r) for r in cross_topic],
    }


async def get_cluster_provenance(
    pool: asyncpg.Pool,
    cluster_id: str,
    topic_id: str,
    *,
    content_limit: int = 30,
) -> dict[str, Any] | None:
    """Enriched provenance for one narrative cluster.

    Concurrent queries for header, signal, content timeline,
    identifiers, and source spread.
    """
    (header, signal_row, items, identifiers,
     source_spread) = await asyncio.gather(
        _pool_fetchrow(pool, SQL_CLUSTER_HEADER, cluster_id, topic_id),
        _pool_fetchrow(pool, SQL_CLUSTER_SIGNAL, cluster_id, topic_id),
        _pool_fetch(pool, SQL_CLUSTER_CONTENT_TIMELINE, cluster_id, topic_id, content_limit),
        _pool_fetch(pool, SQL_CLUSTER_IDENTIFIERS_RANKED, cluster_id, topic_id),
        _pool_fetch(pool, SQL_CLUSTER_SOURCE_SPREAD, cluster_id, topic_id),
    )

    if not header:
        return None

    return {
        "id": cluster_id,
        "label": header["label"],
        "item_count": header["item_count"],
        "isc": header["isc"],
        "executive_summary": header["executive_summary"],
        "created_at": str(header["created_at"]) if header["created_at"] else None,
        "growth_24h": header["growth_24h"] or 0,
        "signal": dict(signal_row) if signal_row else None,
        "items": [dict(r) for r in items],
        "identifiers": [dict(r) for r in identifiers],
        "source_spread": [dict(r) for r in source_spread],
    }


async def get_cluster_flow(
    pool: asyncpg.Pool,
    cluster_id: str,
    topic_id: str,
) -> dict[str, Any]:
    """Information flow graph for one cluster — source nodes + temporal edges.

    Nodes = sources contributing to cluster.
    Edges = temporal flow (earlier source → later source) + shared identifiers.
    """
    nodes_rows, shared_rows = await asyncio.gather(
        _pool_fetch(pool, SQL_CLUSTER_FLOW_NODES, cluster_id, topic_id),
        _pool_fetch(pool, SQL_CLUSTER_FLOW_SHARED_IDENTIFIERS, cluster_id, topic_id),
    )

    nodes = [dict(r) for r in nodes_rows]

    # Build temporal edges: source with earlier first_seen → source with later first_seen
    edges: list[dict[str, Any]] = []
    for i, src_a in enumerate(nodes):
        for src_b in nodes[i + 1:]:
            if src_a["first_seen"] and src_b["first_seen"]:
                delta = src_b["first_seen"] - src_a["first_seen"]
                edges.append({
                    "source": src_a["id"],
                    "target": src_b["id"],
                    "edge_type": "temporal",
                    "time_delta_hours": round(
                        delta.total_seconds() / 3600, 1,
                    ),
                })

    # Shared identifier edges (dotted)
    shared_edges = [
        {
            "source": str(r["source_a"]),
            "target": str(r["source_b"]),
            "edge_type": "shared_identifier",
            "shared_count": r["shared_count"],
        }
        for r in shared_rows
    ]

    return {
        "cluster_id": cluster_id,
        "nodes": nodes,
        "temporal_edges": edges,
        "shared_identifier_edges": shared_edges,
    }


async def get_content_provenance(
    conn: asyncpg.Connection,
    content_id: str,
) -> dict[str, Any] | None:
    """Full provenance chain for one content item."""
    row = await conn.fetchrow(SQL_CONTENT_PROVENANCE, content_id)
    if not row:
        return None

    result = dict(row)

    # Source as nested object
    result["source"] = {
        "id": result.pop("source_id", None),
        "name": result.pop("source_name", None),
        "platform": result.pop("source_platform", None),
        "credibility_score": result.pop("source_credibility", None),
    }

    # Cluster as nested object
    result["cluster"] = {
        "label": result.pop("cluster_label", None),
        "isc": result.pop("cluster_isc", None),
    } if result.get("narrative_cluster_id") else None

    # Identifiers
    identifier_rows = await conn.fetch(SQL_CONTENT_IDENTIFIERS, content_id)
    result["identifiers"] = [dict(r) for r in identifier_rows]

    # Vision results
    vision_rows = await conn.fetch(SQL_CONTENT_VISION, content_id)
    vision_results = []
    for vr in vision_rows:
        d = dict(vr)
        # Parse JSONB fields defensively
        for field in ("yolo_detections", "clip_labels", "exif_data"):
            val = d.get(field)
            if isinstance(val, str):
                try:
                    d[field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
        vision_results.append(d)
    result["vision_results"] = vision_results

    return result


async def get_topic_urgency(
    conn: asyncpg.Connection,
    topic_id: str,
) -> dict[str, Any]:
    """Urgency metrics for a single topic."""
    row = await conn.fetchrow(SQL_TOPIC_URGENCY, topic_id)
    if not row:
        return {
            "unacked_signal_count": 0,
            "new_content_24h": 0,
            "worst_source_health": "healthy",
        }

    health_rank = row["worst_health_rank"]
    health_label = {1: "down", 2: "degraded", 3: "healthy"}.get(health_rank, "healthy")

    return {
        "unacked_signal_count": row["unacked_signal_count"],
        "new_content_24h": row["new_content_24h"],
        "worst_source_health": health_label,
    }
