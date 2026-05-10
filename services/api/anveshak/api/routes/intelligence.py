"""Intelligence endpoints — entity co-occurrence, topic similarity, source discovery.

CPU-feasible intelligence features built on existing NER output and embeddings.
"""
from __future__ import annotations

from typing import Any

import asyncpg
import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from ..auth.rbac import require_role
from ..db.pool import get_db
from ..db import audit as audit_db

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["intelligence"])


# ---------------------------------------------------------------------------
# SQL queries
# ---------------------------------------------------------------------------

SQL_ENTITY_COOCCURRENCE = """
    SELECT e1.entity_text AS entity_a,
           e1.entity_type AS type_a,
           e2.entity_text AS entity_b,
           e2.entity_type AS type_b,
           COUNT(DISTINCT e1.content_item_id) AS co_occurrence_count
    FROM extracted_entities e1
    JOIN extracted_entities e2
        ON e1.content_item_id = e2.content_item_id
        AND e1.id < e2.id
    JOIN content_items ci ON e1.content_item_id = ci.id
    WHERE ci.topic_id = $1
      AND e1.entity_type IN ('PERSON', 'ORG', 'GPE', 'LOC', 'FACILITY')
      AND e2.entity_type IN ('PERSON', 'ORG', 'GPE', 'LOC', 'FACILITY')
    GROUP BY e1.entity_text, e1.entity_type, e2.entity_text, e2.entity_type
    HAVING COUNT(DISTINCT e1.content_item_id) >= $2
    ORDER BY co_occurrence_count DESC
    LIMIT $3
"""

SQL_TOPIC_SIMILARITY = """
    WITH topic_centroid AS (
        SELECT AVG(nc.embedding_centroid) AS centroid
        FROM narrative_clusters nc
        WHERE nc.topic_id = $1
          AND nc.embedding_centroid IS NOT NULL
    ),
    other_topics AS (
        SELECT t.id, t.name, t.status,
               AVG(nc2.embedding_centroid) AS centroid
        FROM topics t
        JOIN narrative_clusters nc2 ON nc2.topic_id = t.id
        WHERE t.id != $1
          AND t.status = 'active'
          AND nc2.embedding_centroid IS NOT NULL
        GROUP BY t.id, t.name, t.status
    )
    SELECT ot.id, ot.name, ot.status,
           1 - (ot.centroid <=> tc.centroid) AS similarity
    FROM other_topics ot, topic_centroid tc
    WHERE tc.centroid IS NOT NULL
    ORDER BY ot.centroid <=> tc.centroid
    LIMIT $2
"""

SQL_OUTBOUND_LINKS = r"""
    SELECT DISTINCT ci.url AS source_url,
           unnest(
               regexp_matches(ci.clean_text, 'https?://[^\s<>"'']+', 'g')
           ) AS outbound_url
    FROM content_items ci
    WHERE ci.topic_id = $1
      AND ci.clean_text ~ 'https?://'
    LIMIT 500
"""

SQL_EXISTING_SOURCE_URLS = """
    SELECT url_or_handle FROM sources WHERE is_active = TRUE
"""

SQL_CLUSTER_DUPLICATES = """
    SELECT nc1.id AS cluster_a_id,
           nc1.label AS cluster_a_label,
           nc1.item_count AS cluster_a_items,
           nc2.id AS cluster_b_id,
           nc2.label AS cluster_b_label,
           nc2.item_count AS cluster_b_items,
           1 - (nc1.embedding_centroid <=> nc2.embedding_centroid) AS similarity
    FROM narrative_clusters nc1
    JOIN narrative_clusters nc2
        ON nc1.topic_id = nc2.topic_id
        AND nc1.id < nc2.id
    WHERE nc1.topic_id = $1
      AND nc1.embedding_centroid IS NOT NULL
      AND nc2.embedding_centroid IS NOT NULL
      AND 1 - (nc1.embedding_centroid <=> nc2.embedding_centroid) >= $2
    ORDER BY similarity DESC
    LIMIT $3
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/topics/{topic_id}/entity-graph")
async def get_entity_cooccurrence(
    topic_id: str,
    min_count: int = Query(2, ge=1, description="Minimum co-occurrence count"),
    limit: int = Query(100, ge=1, le=500, description="Max edges to return"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Entity co-occurrence graph — who appears with whom.

    Returns edges (entity pairs) with co-occurrence frequency.
    Useful for identifying relationships between actors, organizations, and locations.
    """
    rows = await db.fetch(SQL_ENTITY_COOCCURRENCE, topic_id, min_count, limit)
    edges = [dict(r) for r in rows]

    # Extract unique nodes
    nodes: dict[str, str] = {}
    for edge in edges:
        nodes[edge["entity_a"]] = edge["type_a"]
        nodes[edge["entity_b"]] = edge["type_b"]

    return {
        "topic_id": topic_id,
        "nodes": [{"entity": k, "type": v} for k, v in nodes.items()],
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


@router.get("/topics/{topic_id}/similar")
async def get_similar_topics(
    topic_id: str,
    limit: int = Query(5, ge=1, le=20, description="Max similar topics"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> list[dict[str, Any]]:
    """Find topics with similar narrative clusters by centroid distance.

    Uses pgvector cosine similarity on cluster embedding centroids.
    """
    rows = await db.fetch(SQL_TOPIC_SIMILARITY, topic_id, limit)
    return [dict(r) for r in rows]


@router.get("/topics/{topic_id}/discover-sources")
async def discover_sources(
    topic_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Extract outbound URLs from scraped content and suggest new sources.

    Finds URLs mentioned in content that are not already registered as sources.
    """
    # Fetch outbound links from content
    link_rows = await db.fetch(SQL_OUTBOUND_LINKS, topic_id)
    outbound_urls = set()
    for row in link_rows:
        url = row["outbound_url"]
        # Extract domain from URL
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            if parsed.netloc:
                outbound_urls.add(parsed.netloc)
        except Exception:
            pass

    # Fetch existing source domains
    existing_rows = await db.fetch(SQL_EXISTING_SOURCE_URLS)
    existing_domains = set()
    for row in existing_rows:
        from urllib.parse import urlparse
        try:
            parsed = urlparse(row["url_or_handle"])
            if parsed.netloc:
                existing_domains.add(parsed.netloc)
        except Exception:
            existing_domains.add(row["url_or_handle"])

    # Suggested = outbound - existing
    suggestions = sorted(outbound_urls - existing_domains)

    return {
        "topic_id": topic_id,
        "suggested_domains": suggestions[:50],  # cap at 50 suggestions
        "total_outbound_domains": len(outbound_urls),
        "already_registered": len(outbound_urls & existing_domains),
    }


@router.get("/topics/{topic_id}/cluster-duplicates")
async def get_cluster_duplicates(
    topic_id: str,
    min_similarity: float = Query(0.85, ge=0.5, le=1.0, description="Min cosine similarity"),
    limit: int = Query(20, ge=1, le=100, description="Max pairs"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> list[dict[str, Any]]:
    """Detect near-duplicate clusters by centroid cosine similarity.

    Returns pairs of clusters that may be duplicates, sorted by similarity.
    """
    rows = await db.fetch(SQL_CLUSTER_DUPLICATES, topic_id, min_similarity, limit)
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Cluster merge
# ---------------------------------------------------------------------------

SQL_REASSIGN_CONTENT_ITEMS = """
    UPDATE content_items
    SET narrative_cluster_id = $1, updated_at = NOW()
    WHERE narrative_cluster_id = $2
"""

SQL_UPDATE_CLUSTER_COUNTS = """
    UPDATE narrative_clusters
    SET item_count = (
            SELECT COUNT(*) FROM content_items WHERE narrative_cluster_id = $1
        ),
        independent_source_count = (
            SELECT COUNT(DISTINCT s.platform)
            FROM content_items ci
            JOIN sources s ON ci.source_id = s.id
            WHERE ci.narrative_cluster_id = $1
        ),
        updated_at = NOW()
    WHERE id = $1
"""

SQL_DELETE_CLUSTER = """
    DELETE FROM narrative_clusters WHERE id = $1
"""

SQL_GET_CLUSTER = """
    SELECT id, topic_id, label, item_count FROM narrative_clusters WHERE id = $1
"""


@router.post("/clusters/merge")
async def merge_clusters(
    request: Request,
    keep_id: str = Body(..., description="Cluster ID to keep (absorbs items)"),
    remove_id: str = Body(..., description="Cluster ID to remove (items reassigned)"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Merge two clusters — reassign content items from remove_id to keep_id, delete remove_id.

    Both clusters must belong to the same topic.
    """
    keep = await db.fetchrow(SQL_GET_CLUSTER, keep_id)
    remove = await db.fetchrow(SQL_GET_CLUSTER, remove_id)

    if not keep:
        raise HTTPException(status_code=404, detail=f"Cluster {keep_id} not found")
    if not remove:
        raise HTTPException(status_code=404, detail=f"Cluster {remove_id} not found")
    if keep["topic_id"] != remove["topic_id"]:
        raise HTTPException(status_code=400, detail="Clusters must belong to the same topic")

    async with db.transaction():
        # Reassign content items from remove → keep
        await db.execute(SQL_REASSIGN_CONTENT_ITEMS, keep_id, remove_id)
        # Update counts on the surviving cluster
        await db.execute(SQL_UPDATE_CLUSTER_COUNTS, keep_id)
        # Delete the absorbed cluster
        await db.execute(SQL_DELETE_CLUSTER, remove_id)

    log.info(
        "intelligence.clusters_merged",
        keep_id=keep_id,
        remove_id=remove_id,
        topic_id=keep["topic_id"],
    )
    await audit_db.log_action(
        db, user["sub"], "cluster.merge", "cluster", keep_id,
        {"removed_cluster_id": remove_id, "topic_id": keep["topic_id"]},
        request.client.host if request.client else "",
    )

    return {
        "merged": True,
        "kept_cluster_id": keep_id,
        "removed_cluster_id": remove_id,
        "topic_id": keep["topic_id"],
    }
