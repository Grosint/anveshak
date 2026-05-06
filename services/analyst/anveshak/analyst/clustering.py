"""Incremental clustering pipeline (Phase 2, criteria 2.1–2.10).

Responsibilities:
  - Assign NEW items to existing cluster centroids (O(new × clusters))
  - Run HDBSCAN only on truly unassigned items
  - Full re-cluster when no existing clusters (fresh topics)
  - Compute embedding centroid per cluster
  - Count distinct platforms (independent_source_count)
  - Upsert rows into narrative_clusters table

Performance:
  - Current items per cycle: O(new_items × existing_clusters) — NOT O(N²)
  - Full re-cluster fallback: O(N²) — only for fresh topics or staleness trigger
"""
from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import NamedTuple

import asyncpg
import numpy as np
import structlog
from hdbscan import HDBSCAN

from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL — module-level constants
# ---------------------------------------------------------------------------

SQL_TOPIC_EMBEDDINGS = """
    SELECT ci.id AS content_item_id,
           ci.embedding::text AS embedding_text,
           s.platform
    FROM content_items ci
    JOIN sources s ON ci.source_id = s.id
    WHERE ci.topic_id = $1
      AND ci.embedding IS NOT NULL
      AND (ci.topic_relevance_score IS NULL OR ci.topic_relevance_score >= $2)
    ORDER BY ci.captured_at ASC
"""

SQL_TOPIC_EMBEDDINGS_WINDOWED = """
    SELECT ci.id AS content_item_id,
           ci.embedding::text AS embedding_text,
           s.platform
    FROM content_items ci
    JOIN sources s ON ci.source_id = s.id
    WHERE ci.topic_id = $1
      AND ci.embedding IS NOT NULL
      AND (ci.topic_relevance_score IS NULL OR ci.topic_relevance_score >= $2)
      AND ci.captured_at >= NOW() - MAKE_INTERVAL(days => $3)
    ORDER BY ci.captured_at ASC
"""

# Load only items not yet assigned to any cluster
SQL_UNCLUSTERED_EMBEDDINGS_WINDOWED = """
    SELECT ci.id AS content_item_id,
           ci.embedding::text AS embedding_text,
           s.platform
    FROM content_items ci
    JOIN sources s ON ci.source_id = s.id
    WHERE ci.topic_id = $1
      AND ci.embedding IS NOT NULL
      AND ci.narrative_cluster_id IS NULL
      AND (ci.topic_relevance_score IS NULL OR ci.topic_relevance_score >= $2)
      AND ci.captured_at >= NOW() - MAKE_INTERVAL(days => $3)
    ORDER BY ci.captured_at ASC
"""

SQL_UNCLUSTERED_EMBEDDINGS = """
    SELECT ci.id AS content_item_id,
           ci.embedding::text AS embedding_text,
           s.platform
    FROM content_items ci
    JOIN sources s ON ci.source_id = s.id
    WHERE ci.topic_id = $1
      AND ci.embedding IS NOT NULL
      AND ci.narrative_cluster_id IS NULL
      AND (ci.topic_relevance_score IS NULL OR ci.topic_relevance_score >= $2)
    ORDER BY ci.captured_at ASC
"""

# Load existing cluster centroids for incremental assignment
SQL_CLUSTER_CENTROIDS = """
    SELECT id AS cluster_id,
           embedding_centroid::text AS centroid_text,
           independent_source_count,
           item_count
    FROM narrative_clusters
    WHERE topic_id = $1 AND archived_at IS NULL
"""

# Get platforms already in a cluster (for ISC update after assignment)
SQL_CLUSTER_PLATFORMS = """
    SELECT DISTINCT s.platform
    FROM content_items ci
    JOIN sources s ON ci.source_id = s.id
    WHERE ci.narrative_cluster_id = $1
"""

SQL_UPSERT_CLUSTER = """
    INSERT INTO narrative_clusters (
        id, topic_id, label, item_count, embedding_centroid,
        independent_source_count, created_at, updated_at, labels
    )
    VALUES ($1, $2, $3, $4, $5::vector, $6, $7, $7,
            '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT (id) DO UPDATE
        SET item_count              = EXCLUDED.item_count,
            embedding_centroid      = EXCLUDED.embedding_centroid,
            independent_source_count = EXCLUDED.independent_source_count,
            updated_at              = EXCLUDED.updated_at
"""

SQL_LINK_ITEMS_TO_CLUSTER = """
    UPDATE content_items
    SET narrative_cluster_id = $1, updated_at = $2
    WHERE id = ANY($3::text[])
"""

SQL_UPDATE_CLUSTER_STATS = """
    UPDATE narrative_clusters
    SET item_count = $2,
        independent_source_count = $3,
        embedding_centroid = $4::vector,
        updated_at = $5
    WHERE id = $1
"""

SQL_TOPIC_CLUSTER_COUNT = """
    SELECT COUNT(*) FROM narrative_clusters WHERE topic_id = $1
"""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class EmbeddingRow(NamedTuple):
    content_item_id: str
    vector: np.ndarray
    platform: str


class ClusterCentroid(NamedTuple):
    cluster_id: str
    vector: np.ndarray
    isc: int
    item_count: int


class ClusterData(NamedTuple):
    content_item_ids: list[str]
    platforms: list[str]
    centroid: np.ndarray


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_pgvector(text: str) -> np.ndarray:
    """Parse pgvector '[x1,x2,...]' text representation to numpy array."""
    return np.fromstring(text.strip("[]"), sep=",", dtype=np.float32)


def _vec_to_pgvector(arr: np.ndarray) -> str:
    """Format numpy array as pgvector literal string."""
    return "[" + ",".join(f"{x:.8f}" for x in arr.tolist()) + "]"


def _effective_min_cluster_size(item_count: int) -> int:
    """Adaptive min_cluster_size based on available items.

    - 50+ items → production default (3)
    - 10-49 items → 2
    - <10 items → 2 (minimum)
    """
    return max(2, min(settings.hdbscan_min_cluster_size, item_count // 5))


# ---------------------------------------------------------------------------
# Load functions
# ---------------------------------------------------------------------------

async def load_embeddings(
    topic_id: str,
    pool: asyncpg.Pool,
    window_days: int = 0,
    relevance_threshold: float = 0.0,
) -> list[EmbeddingRow]:
    """Fetch ALL content_item embeddings for a topic (criteria 2.2)."""
    async with pool.acquire() as conn:
        if window_days > 0:
            rows = await conn.fetch(
                SQL_TOPIC_EMBEDDINGS_WINDOWED, topic_id, relevance_threshold, window_days,
            )
        else:
            rows = await conn.fetch(SQL_TOPIC_EMBEDDINGS, topic_id, relevance_threshold)
    return _parse_embedding_rows(rows)


async def load_unclustered_embeddings(
    topic_id: str,
    pool: asyncpg.Pool,
    window_days: int = 0,
    relevance_threshold: float = 0.0,
) -> list[EmbeddingRow]:
    """Fetch only items NOT yet assigned to a cluster."""
    async with pool.acquire() as conn:
        if window_days > 0:
            rows = await conn.fetch(
                SQL_UNCLUSTERED_EMBEDDINGS_WINDOWED, topic_id, relevance_threshold, window_days,
            )
        else:
            rows = await conn.fetch(SQL_UNCLUSTERED_EMBEDDINGS, topic_id, relevance_threshold)
    return _parse_embedding_rows(rows)


async def load_cluster_centroids(
    topic_id: str,
    pool: asyncpg.Pool,
) -> list[ClusterCentroid]:
    """Load existing cluster centroids for a topic."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(SQL_CLUSTER_CENTROIDS, topic_id)

    result = []
    for row in rows:
        try:
            vec = _parse_pgvector(row["centroid_text"])
            result.append(ClusterCentroid(
                cluster_id=row["cluster_id"],
                vector=vec,
                isc=row["independent_source_count"],
                item_count=row["item_count"],
            ))
        except Exception as exc:
            log.warning(
                "clustering.bad_centroid",
                cluster_id=row["cluster_id"],
                error=str(exc),
            )
    return result


def _parse_embedding_rows(rows: list) -> list[EmbeddingRow]:
    """Parse DB rows into EmbeddingRow list."""
    result = []
    for row in rows:
        try:
            vec = _parse_pgvector(row["embedding_text"])
            result.append(EmbeddingRow(
                content_item_id=row["content_item_id"],
                vector=vec,
                platform=row["platform"],
            ))
        except Exception as exc:
            log.warning(
                "clustering.bad_embedding",
                content_item_id=row["content_item_id"],
                error=str(exc),
            )
    return result


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def run_hdbscan(rows: list[EmbeddingRow]) -> dict[int, list[int]]:
    """Run HDBSCAN; return mapping of cluster_label → row indices.

    Uses adaptive min_cluster_size based on item count.
    Noise points (label == -1) are excluded (criteria 2.3).
    """
    effective_min = _effective_min_cluster_size(len(rows))

    if len(rows) < effective_min:
        log.info(
            "clustering.insufficient_items",
            count=len(rows),
            min_required=effective_min,
        )
        return {}

    matrix = np.vstack([r.vector for r in rows]).astype(np.float64)
    # Precompute cosine distance matrix. Embeddings are L2-normalized so
    # cosine_distance = 1 - dot(a, b). Using precomputed because hdbscan 0.8.x
    # does not support metric="cosine" directly.
    cosine_sim = matrix @ matrix.T
    np.clip(cosine_sim, -1.0, 1.0, out=cosine_sim)
    distance_matrix = 1.0 - cosine_sim

    clusterer = HDBSCAN(
        min_cluster_size=effective_min,
        min_samples=settings.hdbscan_min_samples,
        metric="precomputed",
    )
    labels = clusterer.fit_predict(distance_matrix)

    groups: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        if label == -1:
            continue  # noise — not a cluster
        groups.setdefault(label, []).append(idx)

    return groups


def assign_to_nearest_cluster(
    new_rows: list[EmbeddingRow],
    centroids: list[ClusterCentroid],
    threshold: float,
) -> tuple[dict[str, list[EmbeddingRow]], list[EmbeddingRow]]:
    """Assign new items to nearest existing cluster if similarity >= threshold.

    Returns:
        assigned: {cluster_id: [items to add]}
        unassigned: items that didn't match any cluster
    """
    assigned: dict[str, list[EmbeddingRow]] = {}
    unassigned: list[EmbeddingRow] = []

    for row in new_rows:
        best_sim = -1.0
        best_cluster_id: str | None = None

        for centroid in centroids:
            sim = float(np.dot(row.vector, centroid.vector))
            if sim > best_sim:
                best_sim = sim
                best_cluster_id = centroid.cluster_id

        if best_sim >= threshold and best_cluster_id:
            assigned.setdefault(best_cluster_id, []).append(row)
        else:
            unassigned.append(row)

    return assigned, unassigned


def compute_centroid(vectors: list[np.ndarray]) -> np.ndarray:
    """Mean of embedding vectors, L2-normalised (criteria 2.4)."""
    centroid = np.mean(np.vstack(vectors), axis=0)
    norm = np.linalg.norm(centroid)
    if norm > 0:
        centroid = centroid / norm
    return centroid.astype(np.float32)


def count_independent_sources(platforms: list[str]) -> int:
    """Count distinct platform values in a cluster (criteria 2.5).

    Pure function — unit-testable without DB.
    """
    return len(set(platforms))


def build_cluster_data(
    rows: list[EmbeddingRow],
    indices: list[int],
) -> ClusterData:
    """Assemble ClusterData from HDBSCAN row indices."""
    content_item_ids = [rows[i].content_item_id for i in indices]
    platforms = [rows[i].platform for i in indices]
    vectors = [rows[i].vector for i in indices]
    centroid = compute_centroid(vectors)
    return ClusterData(
        content_item_ids=content_item_ids,
        platforms=platforms,
        centroid=centroid,
    )


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------

async def upsert_cluster(
    conn: asyncpg.Connection,
    topic_id: str,
    cluster_id: str,
    cluster_data: ClusterData,
    label: str,
    now: datetime,
    duplicate_ids: set[str] | None = None,
) -> None:
    """Persist a narrative cluster and link its content items (criteria 2.4, 2.5).

    When duplicate_ids is provided, items in that set are excluded from
    independent_source_count to prevent near-duplicate inflation.
    item_count remains the total for transparency.
    """
    centroid_str = _vec_to_pgvector(cluster_data.centroid)

    if duplicate_ids:
        filtered_platforms = [
            p for cid, p in zip(cluster_data.content_item_ids, cluster_data.platforms)
            if cid not in duplicate_ids
        ]
        isc = count_independent_sources(filtered_platforms) if filtered_platforms else count_independent_sources(cluster_data.platforms)
    else:
        isc = count_independent_sources(cluster_data.platforms)

    await conn.execute(
        SQL_UPSERT_CLUSTER,
        cluster_id,
        topic_id,
        label,
        len(cluster_data.content_item_ids),
        centroid_str,
        isc,
        now,
    )

    await conn.execute(
        SQL_LINK_ITEMS_TO_CLUSTER,
        cluster_id,
        now,
        cluster_data.content_item_ids,
    )

    log.info(
        "clustering.cluster_upserted",
        cluster_id=cluster_id,
        topic_id=topic_id,
        item_count=len(cluster_data.content_item_ids),
        independent_source_count=isc,
    )


async def update_cluster_with_assignments(
    pool: asyncpg.Pool,
    cluster_id: str,
    new_items: list[EmbeddingRow],
    existing_centroid: np.ndarray,
    existing_item_count: int,
) -> int:
    """Add new items to an existing cluster, update centroid and ISC.

    Returns updated ISC.
    """
    now = datetime.now(UTC)
    new_item_ids = [r.content_item_id for r in new_items]

    async with pool.acquire() as conn:
        # Assign items to cluster
        await conn.execute(SQL_LINK_ITEMS_TO_CLUSTER, cluster_id, now, new_item_ids)

        # Recompute centroid as weighted average of old + new
        new_vectors = [r.vector for r in new_items]
        all_vectors = [existing_centroid * existing_item_count] + new_vectors
        # Weighted: old centroid counts for existing_item_count items
        raw = (existing_centroid * existing_item_count + np.sum(new_vectors, axis=0)) / (existing_item_count + len(new_items))
        norm = np.linalg.norm(raw)
        updated_centroid = (raw / norm if norm > 0 else raw).astype(np.float32)

        # Get all distinct platforms now in this cluster
        platform_rows = await conn.fetch(SQL_CLUSTER_PLATFORMS, cluster_id)
        all_platforms = [r["platform"] for r in platform_rows]
        updated_isc = count_independent_sources(all_platforms)

        updated_count = existing_item_count + len(new_items)
        centroid_str = _vec_to_pgvector(updated_centroid)

        await conn.execute(
            SQL_UPDATE_CLUSTER_STATS,
            cluster_id,
            updated_count,
            updated_isc,
            centroid_str,
            now,
        )

    log.info(
        "clustering.incremental_assigned",
        cluster_id=cluster_id,
        new_items=len(new_items),
        updated_isc=updated_isc,
        updated_count=updated_count,
    )
    return updated_isc


# ---------------------------------------------------------------------------
# Top-level orchestrator (called from ARQ job / scheduler)
# ---------------------------------------------------------------------------

SQL_GET_TOPIC_RELEVANCE_THRESHOLD = """
    SELECT topic_relevance_threshold FROM topics WHERE id = $1
"""


async def run_clustering(topic_id: str, pool: asyncpg.Pool) -> list[str]:
    """Incremental clustering for a topic.

    Flow:
      1. Load unclustered items only (narrative_cluster_id IS NULL)
      2. If existing clusters exist → try assigning to nearest centroid
      3. Run HDBSCAN only on truly unassigned items
      4. If no existing clusters → full HDBSCAN on all unclustered items
      5. Returns list of cluster_ids created or updated

    Criteria 2.1–2.5, 2.9.
    """
    from .relevance import resolve_threshold
    async with pool.acquire() as conn:
        per_topic = await conn.fetchval(SQL_GET_TOPIC_RELEVANCE_THRESHOLD, topic_id)
    threshold = resolve_threshold(per_topic)

    # Step 1: Load only unclustered items
    new_rows = await load_unclustered_embeddings(
        topic_id, pool,
        window_days=settings.clustering_window_days,
        relevance_threshold=threshold,
    )

    if not new_rows:
        return []

    # Step 2: Load existing cluster centroids
    centroids = await load_cluster_centroids(topic_id, pool)
    cluster_ids: list[str] = []

    if centroids:
        # --- Incremental path: assign to existing clusters first ---
        assigned, unassigned = assign_to_nearest_cluster(
            new_rows, centroids, settings.cluster_assign_threshold,
        )

        # Update each cluster with newly assigned items
        centroid_map = {c.cluster_id: c for c in centroids}
        for cluster_id, items in assigned.items():
            c = centroid_map[cluster_id]
            await update_cluster_with_assignments(
                pool, cluster_id, items, c.vector, c.item_count,
            )
            cluster_ids.append(cluster_id)

        if assigned:
            log.info(
                "clustering.incremental_complete",
                topic_id=topic_id,
                assigned_items=sum(len(v) for v in assigned.values()),
                clusters_updated=len(assigned),
                unassigned_items=len(unassigned),
            )

        # Run HDBSCAN only on items that didn't match any centroid
        if unassigned:
            effective_min = _effective_min_cluster_size(len(unassigned))
            if len(unassigned) >= effective_min:
                new_cluster_ids = await _hdbscan_and_persist(
                    topic_id, pool, unassigned,
                )
                cluster_ids.extend(new_cluster_ids)
            else:
                log.info(
                    "clustering.unassigned_below_threshold",
                    topic_id=topic_id,
                    unassigned=len(unassigned),
                    min_required=effective_min,
                )
    else:
        # --- Fresh topic: full HDBSCAN on all unclustered items ---
        new_cluster_ids = await _hdbscan_and_persist(
            topic_id, pool, new_rows,
        )
        cluster_ids.extend(new_cluster_ids)

    if cluster_ids:
        log.info(
            "clustering.topic_done",
            topic_id=topic_id,
            clusters=len(cluster_ids),
        )

    return cluster_ids


async def _hdbscan_and_persist(
    topic_id: str,
    pool: asyncpg.Pool,
    rows: list[EmbeddingRow],
) -> list[str]:
    """Run HDBSCAN on a set of items and persist the resulting clusters."""
    groups = run_hdbscan(rows)
    if not groups:
        log.info("clustering.no_clusters_formed", topic_id=topic_id, item_count=len(rows))
        return []

    now = datetime.now(UTC)
    cluster_ids: list[str] = []

    async with pool.acquire() as conn:
        existing_count = await conn.fetchval(SQL_TOPIC_CLUSTER_COUNT, topic_id)

        from .dedup import get_duplicate_ids_for_cluster
        all_item_ids = [r.content_item_id for r in rows]
        duplicate_ids = await get_duplicate_ids_for_cluster(all_item_ids, conn)

        async with conn.transaction():
            for hdbscan_label, indices in groups.items():
                cluster_data = build_cluster_data(rows, indices)
                cluster_id = str(uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{topic_id}:{hdbscan_label}",
                ))
                fallback_label = f"Cluster {existing_count + hdbscan_label + 1}"

                await upsert_cluster(
                    conn=conn,
                    topic_id=topic_id,
                    cluster_id=cluster_id,
                    cluster_data=cluster_data,
                    label=fallback_label,
                    now=now,
                    duplicate_ids=duplicate_ids,
                )
                cluster_ids.append(cluster_id)

    return cluster_ids
