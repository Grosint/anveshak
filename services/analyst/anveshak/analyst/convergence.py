"""Cross-topic cluster convergence detection (Phase 6 — P2b).

Compares cluster centroids across different topics to detect when the same
narrative emerges independently in multiple monitoring topics.  Fires a
'cross_topic_convergence' signal when centroid cosine similarity exceeds
the configured threshold.

Design:
  - O(C²) on cluster centroids (not items) — bounded by active cluster count
  - Canonical pair ordering: topic_a < topic_b prevents duplicate comparisons
  - Reuses existing signals table and 24h dedup window
  - Gated by cross_topic_check_interval_s (0 = disabled)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, UTC

import asyncpg
import structlog

from .metrics import analyst_signals_fired_total
from .settings import settings
from .signal_engine import is_duplicate_signal, _SIGNAL_TYPE_CROSS_TOPIC, SQL_INSERT_SIGNAL

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL — module-level constants
# ---------------------------------------------------------------------------

SQL_CONVERGENT_CLUSTERS = """
    SELECT nc1.id            AS cluster_a_id,
           nc1.topic_id      AS topic_a_id,
           nc1.label         AS cluster_a_label,
           nc2.id            AS cluster_b_id,
           nc2.topic_id      AS topic_b_id,
           nc2.label         AS cluster_b_label,
           1 - (nc1.embedding_centroid <=> nc2.embedding_centroid) AS similarity
    FROM narrative_clusters nc1
    JOIN narrative_clusters nc2
        ON nc1.topic_id < nc2.topic_id
    JOIN topics t1 ON t1.id = nc1.topic_id
    JOIN topics t2 ON t2.id = nc2.topic_id
    WHERE nc1.embedding_centroid IS NOT NULL
      AND nc2.embedding_centroid IS NOT NULL
      AND nc1.archived_at IS NULL
      AND nc2.archived_at IS NULL
      AND t1.org_id = t2.org_id
      AND 1 - (nc1.embedding_centroid <=> nc2.embedding_centroid) >= $1
    ORDER BY similarity DESC
    LIMIT $2
"""


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

async def check_cross_topic_convergence(pool: asyncpg.Pool) -> int:
    """Detect and signal cross-topic cluster convergence.

    Returns count of signals fired.
    """
    threshold = settings.cross_topic_similarity_threshold
    max_pairs = settings.cross_topic_max_pairs
    fired = 0

    async with pool.acquire() as conn:
        pairs = await conn.fetch(SQL_CONVERGENT_CLUSTERS, threshold, max_pairs)

        for row in pairs:
            now = datetime.now(UTC)
            cluster_a_id: str = row["cluster_a_id"]

            # Dedup: same cluster_a + signal_type within 24h
            if await is_duplicate_signal(conn, cluster_a_id, _SIGNAL_TYPE_CROSS_TOPIC):
                continue

            signal_id = str(uuid.uuid4())
            topic_a_id: str = row["topic_a_id"]
            similarity: float = row["similarity"]
            label_a: str = row["cluster_a_label"] or f"Cluster {cluster_a_id[:8]}"
            label_b: str = row["cluster_b_label"] or f"Cluster {row['cluster_b_id'][:8]}"

            description = (
                f"Cross-topic convergence: '{label_a}' (topic {topic_a_id[:8]}) "
                f"and '{label_b}' (topic {row['topic_b_id'][:8]}) "
                f"share {similarity:.0%} narrative similarity"
            )
            evidence = json.dumps({
                "cluster_a_id": cluster_a_id,
                "cluster_b_id": row["cluster_b_id"],
                "topic_a_id": topic_a_id,
                "topic_b_id": row["topic_b_id"],
                "similarity": round(similarity, 4),
            })

            await conn.execute(
                SQL_INSERT_SIGNAL,
                signal_id,
                topic_a_id,  # signal belongs to topic_a
                cluster_a_id,
                _SIGNAL_TYPE_CROSS_TOPIC,
                description,
                evidence,
                now,
            )

            analyst_signals_fired_total.labels(severity="HIGH").inc()
            log.info(
                "convergence.signal_fired",
                signal_id=signal_id,
                cluster_a=cluster_a_id,
                cluster_b=row["cluster_b_id"],
                similarity=round(similarity, 4),
            )
            fired += 1

    return fired
