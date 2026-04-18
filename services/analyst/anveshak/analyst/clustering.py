"""HDBSCAN clustering pipeline (Phase 2, criteria 2.1–2.10).

Responsibilities:
  - Load embeddings for a topic from content_items
  - Run HDBSCAN → group items into narrative clusters
  - Compute embedding centroid per cluster
  - Count distinct platforms (independent_source_count)
  - Upsert rows into narrative_clusters table
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
      AND ci.captured_at >= NOW() - MAKE_INTERVAL(days => $2)
    ORDER BY ci.captured_at ASC
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


# ---------------------------------------------------------------------------
# Core functions (all unit-testable with injected data)
# ---------------------------------------------------------------------------

async def load_embeddings(
    topic_id: str,
    pool: asyncpg.Pool,
    window_days: int = 0,
) -> list[EmbeddingRow]:
    """Fetch content_item embeddings for a topic (criteria 2.2).

    When window_days > 0, only items captured within that window are loaded.
    """
    async with pool.acquire() as conn:
        if window_days > 0:
            rows = await conn.fetch(SQL_TOPIC_EMBEDDINGS_WINDOWED, topic_id, window_days)
        else:
            rows = await conn.fetch(SQL_TOPIC_EMBEDDINGS, topic_id)

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


def run_hdbscan(rows: list[EmbeddingRow]) -> dict[int, list[int]]:
    """Run HDBSCAN; return mapping of cluster_label → row indices.

    Noise points (label == -1) are excluded (criteria 2.3).
    min_cluster_size and min_samples come from settings (criteria 2.3, hardware rule).
    """
    if len(rows) < settings.hdbscan_min_cluster_size:
        log.info(
            "clustering.insufficient_items",
            count=len(rows),
            min_required=settings.hdbscan_min_cluster_size,
        )
        return {}

    matrix = np.vstack([r.vector for r in rows])
    clusterer = HDBSCAN(
        min_cluster_size=settings.hdbscan_min_cluster_size,
        min_samples=settings.hdbscan_min_samples,
        metric="euclidean",
    )
    labels = clusterer.fit_predict(matrix)

    groups: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        if label == -1:
            continue  # noise — not a cluster
        groups.setdefault(label, []).append(idx)

    return groups


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


# ---------------------------------------------------------------------------
# Top-level orchestrator (called from ARQ job)
# ---------------------------------------------------------------------------

async def run_clustering(topic_id: str, pool: asyncpg.Pool) -> list[str]:
    """Full clustering run for a topic. Returns list of cluster_ids created/updated.

    Criteria 2.1–2.5, 2.9.
    """
    rows = await load_embeddings(topic_id, pool, window_days=settings.clustering_window_days)
    if not rows:
        log.info("clustering.no_embeddings", topic_id=topic_id)
        return []

    groups = run_hdbscan(rows)
    if not groups:
        log.info("clustering.no_clusters_formed", topic_id=topic_id, item_count=len(rows))
        return []

    now = datetime.now(UTC)
    cluster_ids: list[str] = []

    async with pool.acquire() as conn:
        # Determine existing cluster count for stable naming fallback
        existing_count = await conn.fetchval(SQL_TOPIC_CLUSTER_COUNT, topic_id)

        # Load near-duplicate IDs for accurate independent_source_count
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
                    label=fallback_label,  # updated by generate_cluster_label job
                    now=now,
                    duplicate_ids=duplicate_ids,
                )
                cluster_ids.append(cluster_id)

    log.info(
        "clustering.topic_done",
        topic_id=topic_id,
        clusters=len(cluster_ids),
    )
    return cluster_ids
