"""Near-duplicate detection via embedding cosine similarity.

Identifies semantically equivalent content items within a topic and records
pairs in the near_duplicates table.  The clustering pipeline uses these pairs
to exclude duplicates from independent_source_count, preventing false signals.

Design:
  - Pairwise cosine similarity on L2-normalised embeddings = dot product.
  - O(N²) bounded by settings.near_duplicate_batch_size per topic.
  - Canonical pair ordering (a < b) via CHECK constraint on table.
  - Idempotent: ON CONFLICT DO NOTHING.
"""

from __future__ import annotations

from datetime import UTC, datetime

import asyncpg
import numpy as np
import structlog
from anveshak.db import DBConnection

from .clustering import load_embeddings
from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL — module-level constants
# ---------------------------------------------------------------------------

SQL_UPSERT_NEAR_DUPLICATE = """
    INSERT INTO near_duplicates (content_item_a_id, content_item_b_id,
                                 similarity_score, detected_at)
    VALUES ($1, $2, $3, $4)
    ON CONFLICT (content_item_a_id, content_item_b_id) DO NOTHING
"""

SQL_GET_DUPLICATE_IDS = """
    SELECT nd.content_item_b_id
    FROM near_duplicates nd
    WHERE nd.content_item_a_id = ANY($1::text[])
      AND nd.content_item_b_id = ANY($1::text[])
"""


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


async def detect_near_duplicates(
    topic_id: str,
    pool: asyncpg.Pool,
) -> list[tuple[str, str, float]]:
    """Find near-duplicate content item pairs within a topic.

    Returns list of (item_a_id, item_b_id, similarity) with a < b.
    Uses numpy dot product on L2-normalised embeddings (= cosine similarity).
    """
    rows = await load_embeddings(topic_id, pool)
    if len(rows) < 2:
        return []

    # Respect batch size limit to keep O(N²) bounded
    batch = rows[: settings.near_duplicate_batch_size]

    ids = [r.content_item_id for r in batch]
    matrix = np.vstack([r.vector for r in batch])  # (N, 384)

    # Cosine similarity = dot product for L2-normalised vectors
    sim_matrix = matrix @ matrix.T  # (N, N)

    threshold = settings.near_duplicate_similarity_threshold
    pairs: list[tuple[str, str, float]] = []

    n = len(ids)
    for i in range(n):
        for j in range(i + 1, n):
            score = float(sim_matrix[i, j])
            if score >= threshold:
                # Canonical ordering: a < b
                a, b = (ids[i], ids[j]) if ids[i] < ids[j] else (ids[j], ids[i])
                pairs.append((a, b, score))

    log.info(
        "dedup.detected",
        topic_id=topic_id,
        items_checked=n,
        pairs_found=len(pairs),
        threshold=threshold,
    )
    return pairs


async def upsert_near_duplicates(
    pairs: list[tuple[str, str, float]],
    pool: asyncpg.Pool,
) -> int:
    """Persist near-duplicate pairs. Idempotent via ON CONFLICT DO NOTHING."""
    if not pairs:
        return 0

    now = datetime.now(UTC)
    inserted = 0

    async with pool.acquire() as conn:
        async with conn.transaction():
            for a_id, b_id, score in pairs:
                result = await conn.execute(
                    SQL_UPSERT_NEAR_DUPLICATE,
                    a_id,
                    b_id,
                    score,
                    now,
                )
                if result == "INSERT 0 1":
                    inserted += 1

    log.info("dedup.upserted", inserted=inserted, total_pairs=len(pairs))
    return inserted


async def get_duplicate_ids_for_cluster(
    content_item_ids: list[str],
    conn: DBConnection,
) -> set[str]:
    """Return content_item IDs that are the 'b' side of a near-duplicate pair.

    Within the given set of IDs, if (a, b) is a near-duplicate pair and both
    a and b are in the set, then b is marked as duplicate.  The 'a' side
    (lexicographically first) is kept as the canonical representative.
    """
    if not content_item_ids:
        return set()

    rows = await conn.fetch(SQL_GET_DUPLICATE_IDS, content_item_ids)
    return {row["content_item_b_id"] for row in rows}
