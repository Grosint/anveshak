"""Signal repository — all SQL for the signals domain."""
from __future__ import annotations

import json
from typing import Any

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_LIST_SIGNALS = """
    SELECT s.id, s.topic_id, s.cluster_id, s.signal_type, s.description, s.evidence,
           s.status, s.created_at,
           nc.label AS cluster_label,
           nc.independent_source_count,
           nc.item_count AS cluster_item_count,
           nc.executive_summary,
           t.name AS topic_name
    FROM signals s
    LEFT JOIN narrative_clusters nc ON nc.id = s.cluster_id
    LEFT JOIN topics t ON t.id = s.topic_id
    WHERE s.status = $1
    ORDER BY s.created_at DESC
    LIMIT 50
"""

SQL_LIST_SIGNALS_BY_TOPIC = """
    SELECT s.id, s.topic_id, s.cluster_id, s.signal_type, s.description, s.evidence,
           s.status, s.created_at,
           nc.label AS cluster_label,
           nc.independent_source_count,
           nc.item_count AS cluster_item_count,
           nc.executive_summary,
           t.name AS topic_name
    FROM signals s
    LEFT JOIN narrative_clusters nc ON nc.id = s.cluster_id
    LEFT JOIN topics t ON t.id = s.topic_id
    WHERE s.status = $1 AND s.topic_id = $2
    ORDER BY s.created_at DESC
    LIMIT 50
"""

SQL_LIST_SIGNALS_SINCE = """
    SELECT s.id, s.topic_id, s.cluster_id, s.signal_type, s.description, s.evidence,
           s.status, s.created_at,
           nc.label AS cluster_label,
           nc.independent_source_count,
           nc.item_count AS cluster_item_count,
           nc.executive_summary,
           t.name AS topic_name
    FROM signals s
    LEFT JOIN narrative_clusters nc ON nc.id = s.cluster_id
    LEFT JOIN topics t ON t.id = s.topic_id
    WHERE s.status = $1
      AND s.created_at >= $2
      AND s.created_at <= $3
    ORDER BY s.created_at DESC
    LIMIT 200
"""

SQL_LIST_SIGNALS_SINCE_BY_TOPIC = """
    SELECT s.id, s.topic_id, s.cluster_id, s.signal_type, s.description, s.evidence,
           s.status, s.created_at,
           nc.label AS cluster_label,
           nc.independent_source_count,
           nc.item_count AS cluster_item_count,
           nc.executive_summary,
           t.name AS topic_name
    FROM signals s
    LEFT JOIN narrative_clusters nc ON nc.id = s.cluster_id
    LEFT JOIN topics t ON t.id = s.topic_id
    WHERE s.status = $1
      AND s.created_at >= $2
      AND s.created_at <= $3
      AND s.topic_id = $4
    ORDER BY s.created_at DESC
    LIMIT 200
"""

SQL_LIST_SIGNALS_BY_ORG = """
    SELECT s.id, s.topic_id, s.cluster_id, s.signal_type, s.description, s.evidence,
           s.status, s.created_at,
           nc.label AS cluster_label,
           nc.independent_source_count,
           nc.item_count AS cluster_item_count,
           nc.executive_summary,
           t.name AS topic_name
    FROM signals s
    LEFT JOIN narrative_clusters nc ON nc.id = s.cluster_id
    LEFT JOIN topics t ON t.id = s.topic_id
    WHERE s.status = $1 AND t.org_id = $2
    ORDER BY s.created_at DESC
    LIMIT 50
"""

# Per-signal enrichment: source breakdown + timeline from cluster items
SQL_SIGNAL_SOURCES = """
    SELECT DISTINCT ON (src.id)
           src.url_or_handle AS source_name,
           src.platform,
           src.credibility_score
    FROM content_items ci
    JOIN sources src ON src.id = ci.source_id
    WHERE ci.narrative_cluster_id = $1
    ORDER BY src.id, src.credibility_score DESC
"""

SQL_SIGNAL_TIMELINE = """
    SELECT MIN(ci.captured_at) AS first_seen,
           MAX(ci.captured_at) AS last_seen
    FROM content_items ci
    WHERE ci.narrative_cluster_id = $1
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

# Signal connection graph: cluster + content items + sources for a signal
SQL_SIGNAL_CONNECTIONS = """
    SELECT
        s.id AS signal_id,
        s.signal_type,
        s.cluster_id,
        s.topic_id,
        nc.label AS cluster_label,
        nc.executive_summary,
        nc.independent_source_count,
        ci.id AS content_item_id,
        ci.title AS content_title,
        LEFT(ci.clean_text, 150) AS content_excerpt,
        ci.url AS content_url,
        ci.captured_at AS content_captured_at,
        src.id AS source_id,
        src.url_or_handle AS source_name,
        src.platform AS source_platform,
        src.credibility_score AS source_credibility
    FROM signals s
    LEFT JOIN narrative_clusters nc ON nc.id = s.cluster_id
    LEFT JOIN content_items ci ON ci.narrative_cluster_id = s.cluster_id
        AND COALESCE(ci.content_quality, 'good') != 'low_quality'
    LEFT JOIN sources src ON src.id = ci.source_id
    WHERE s.id = $1
    ORDER BY ci.captured_at DESC
    LIMIT 30
"""

# Fallback: when signal has no cluster_id, find content items by topic_id
SQL_SIGNAL_CONNECTIONS_BY_TOPIC = """
    SELECT
        s.id AS signal_id,
        s.signal_type,
        s.cluster_id,
        s.topic_id,
        t.name AS topic_name,
        ci.id AS content_item_id,
        ci.title AS content_title,
        LEFT(ci.clean_text, 150) AS content_excerpt,
        ci.url AS content_url,
        ci.captured_at AS content_captured_at,
        src.id AS source_id,
        src.url_or_handle AS source_name,
        src.platform AS source_platform,
        src.credibility_score AS source_credibility
    FROM signals s
    JOIN topics t ON t.id = s.topic_id
    LEFT JOIN content_items ci ON ci.topic_id = s.topic_id
        AND COALESCE(ci.content_quality, 'good') != 'low_quality'
    LEFT JOIN sources src ON src.id = ci.source_id
    WHERE s.id = $1
    ORDER BY ci.captured_at DESC
    LIMIT 30
"""

# Cross-topic convergence: find the other cluster/topic for a convergence signal
SQL_SIGNAL_CROSS_TOPIC = """
    SELECT s2.id AS related_signal_id,
           s2.topic_id AS related_topic_id,
           t.name AS related_topic_name,
           nc.label AS related_cluster_label
    FROM signals s2
    JOIN narrative_clusters nc ON nc.id = s2.cluster_id
    JOIN topics t ON t.id = s2.topic_id
    WHERE s2.signal_type = 'cross_topic_convergence'
      AND s2.cluster_id != (SELECT cluster_id FROM signals WHERE id = $1)
      AND t.org_id = (SELECT t2.org_id FROM signals s3
                      JOIN topics t2 ON t2.id = s3.topic_id
                      WHERE s3.id = $1)
      AND s2.created_at BETWEEN
          (SELECT created_at - INTERVAL '1 hour' FROM signals WHERE id = $1)
          AND
          (SELECT created_at + INTERVAL '1 hour' FROM signals WHERE id = $1)
    LIMIT 5
"""

SQL_MISSED_SIGNALS = """
    SELECT s.id, s.topic_id, s.cluster_id, s.signal_type, s.description,
           s.status, s.created_at
    FROM signals s
    JOIN topics t ON t.id = s.topic_id
    WHERE s.created_at > $1
      AND s.status = 'new'
      AND (t.org_id = $2 OR t.org_id IS NULL)
    ORDER BY s.created_at ASC
    LIMIT 100
"""

# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------

async def _enrich_signal(conn: asyncpg.Connection, signal: dict) -> dict:
    """Add source breakdown and timeline to a signal dict."""
    cluster_id = signal.get("cluster_id")
    if not cluster_id:
        signal["sources"] = []
        signal["first_seen"] = None
        signal["last_seen"] = None
        return signal

    # Fetch source breakdown
    source_rows = await conn.fetch(SQL_SIGNAL_SOURCES, cluster_id)
    signal["sources"] = [
        {
            "source_name": r["source_name"],
            "platform": r["platform"],
            "credibility_score": float(r["credibility_score"]),
        }
        for r in source_rows
    ]

    # Fetch timeline
    timeline = await conn.fetchrow(SQL_SIGNAL_TIMELINE, cluster_id)
    if timeline:
        signal["first_seen"] = timeline["first_seen"].isoformat() if timeline["first_seen"] else None
        signal["last_seen"] = timeline["last_seen"].isoformat() if timeline["last_seen"] else None
    else:
        signal["first_seen"] = None
        signal["last_seen"] = None

    return signal


async def list_signals(
    conn: asyncpg.Connection, status: str, topic_id: str | None = None
) -> list[dict[str, Any]]:
    if topic_id:
        rows = await conn.fetch(SQL_LIST_SIGNALS_BY_TOPIC, status, topic_id)
    else:
        rows = await conn.fetch(SQL_LIST_SIGNALS, status)
    signals = [dict(r) for r in rows]
    return [await _enrich_signal(conn, s) for s in signals]


async def list_signals_by_org(
    conn: asyncpg.Connection, status: str, org_id: str
) -> list[dict[str, Any]]:
    """Return signals filtered by topic's org_id."""
    rows = await conn.fetch(SQL_LIST_SIGNALS_BY_ORG, status, org_id)
    signals = [dict(r) for r in rows]
    return [await _enrich_signal(conn, s) for s in signals]


async def list_signals_filtered(
    conn: asyncpg.Connection, status: str, since: Any, until: Any,
    *, topic_id: str | None = None,
) -> list[dict[str, Any]]:
    if topic_id:
        rows = await conn.fetch(SQL_LIST_SIGNALS_SINCE_BY_TOPIC, status, since, until, topic_id)
    else:
        rows = await conn.fetch(SQL_LIST_SIGNALS_SINCE, status, since, until)
    signals = [dict(r) for r in rows]
    return [await _enrich_signal(conn, s) for s in signals]


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


async def get_signal_connections(
    conn: asyncpg.Connection, signal_id: str
) -> dict[str, Any]:
    """Build graph data (nodes + edges) for a signal's connections."""
    rows = await conn.fetch(SQL_SIGNAL_CONNECTIONS, signal_id)
    if not rows:
        return {"nodes": [], "edges": []}

    first = rows[0]
    has_cluster = bool(first["cluster_id"])

    # If no cluster_id, fall back to topic-based content lookup
    if not has_cluster:
        rows = await conn.fetch(SQL_SIGNAL_CONNECTIONS_BY_TOPIC, signal_id)
        if not rows:
            return {"nodes": [], "edges": []}
        first = rows[0]
        return _build_topic_graph(rows, first)

    return await _build_cluster_graph(rows, first, conn, signal_id)


async def _build_cluster_graph(
    rows: list, first: dict, conn: asyncpg.Connection, signal_id: str
) -> dict[str, Any]:
    """Build graph from cluster-linked signal (original path)."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    signal_node_id = f"signal:{first['signal_id']}"
    nodes[signal_node_id] = {
        "id": signal_node_id,
        "type": "signal",
        "label": first["cluster_label"] or "Signal",
        "data": {"signal_type": first["signal_type"]},
    }

    cluster_node_id = f"cluster:{first['cluster_id']}"
    nodes[cluster_node_id] = {
        "id": cluster_node_id,
        "type": "cluster",
        "label": first["cluster_label"] or "Cluster",
        "data": {
            "summary": first["executive_summary"],
            "isc": first["independent_source_count"],
        },
    }
    edges.append({"source": signal_node_id, "target": cluster_node_id, "type": "triggers"})

    for r in rows:
        if not r["content_item_id"]:
            continue

        ci_id = f"content:{r['content_item_id']}"
        if ci_id not in nodes:
            nodes[ci_id] = {
                "id": ci_id,
                "type": "content",
                "label": r["content_title"] or r["content_excerpt"] or "Content",
                "data": {
                    "url": r["content_url"],
                    "captured_at": r["content_captured_at"].isoformat() if r["content_captured_at"] else None,
                },
            }
            edges.append({"source": cluster_node_id, "target": ci_id, "type": "contains"})

        if r["source_id"]:
            src_id = f"source:{r['source_id']}"
            if src_id not in nodes:
                nodes[src_id] = {
                    "id": src_id,
                    "type": "source",
                    "label": r["source_name"] or "Source",
                    "data": {
                        "platform": r["source_platform"],
                        "credibility": float(r["source_credibility"]) if r["source_credibility"] else None,
                    },
                }
            if not any(e["source"] == ci_id and e["target"] == src_id for e in edges):
                edges.append({"source": ci_id, "target": src_id, "type": "from_source"})

    # Cross-topic convergence links
    cross_rows = await conn.fetch(SQL_SIGNAL_CROSS_TOPIC, signal_id)
    for cr in cross_rows:
        cross_id = f"signal:{cr['related_signal_id']}"
        if cross_id not in nodes:
            nodes[cross_id] = {
                "id": cross_id,
                "type": "cross_signal",
                "label": cr["related_cluster_label"] or cr["related_topic_name"],
                "data": {"topic_name": cr["related_topic_name"]},
            }
        edges.append({"source": signal_node_id, "target": cross_id, "type": "converges_with"})

    return {"nodes": list(nodes.values()), "edges": edges}


def _build_topic_graph(rows: list, first: dict) -> dict[str, Any]:
    """Build graph from topic-linked signal (fallback for NULL cluster_id)."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    signal_node_id = f"signal:{first['signal_id']}"
    nodes[signal_node_id] = {
        "id": signal_node_id,
        "type": "signal",
        "label": "Signal",
        "data": {"signal_type": first["signal_type"]},
    }

    # Topic node (replaces cluster node visually)
    topic_node_id = f"cluster:{first['topic_id']}"
    nodes[topic_node_id] = {
        "id": topic_node_id,
        "type": "cluster",
        "label": first.get("topic_name") or "Topic",
        "data": {"summary": None, "isc": None},
    }
    edges.append({"source": signal_node_id, "target": topic_node_id, "type": "triggers"})

    for r in rows:
        if not r["content_item_id"]:
            continue

        ci_id = f"content:{r['content_item_id']}"
        if ci_id not in nodes:
            nodes[ci_id] = {
                "id": ci_id,
                "type": "content",
                "label": r["content_title"] or r["content_excerpt"] or "Content",
                "data": {
                    "url": r["content_url"],
                    "captured_at": r["content_captured_at"].isoformat() if r["content_captured_at"] else None,
                },
            }
            edges.append({"source": topic_node_id, "target": ci_id, "type": "contains"})

        if r["source_id"]:
            src_id = f"source:{r['source_id']}"
            if src_id not in nodes:
                nodes[src_id] = {
                    "id": src_id,
                    "type": "source",
                    "label": r["source_name"] or "Source",
                    "data": {
                        "platform": r["source_platform"],
                        "credibility": float(r["source_credibility"]) if r["source_credibility"] else None,
                    },
                }
            if not any(e["source"] == ci_id and e["target"] == src_id for e in edges):
                edges.append({"source": ci_id, "target": src_id, "type": "from_source"})

    return {"nodes": list(nodes.values()), "edges": edges}


async def get_missed_signals(
    conn: asyncpg.Connection, since: Any, org_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_MISSED_SIGNALS, since, org_id)
    return [dict(r) for r in rows]
