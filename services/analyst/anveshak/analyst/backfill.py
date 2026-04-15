"""Historical topic backfill — Phase 2, criterion 2.9.

When a new topic is created, existing content_items in the corpus that are
semantically similar to the topic's keywords are assigned to it via the
topic_content_items join table.

Design decisions:
- We do NOT copy content_items rows (UNIQUE(content_hash) would prevent it).
- We do NOT change the owning topic_id FK on existing items (would break Phase 1 queries).
- Instead, topic_content_items is a lightweight join table: (topic_id, content_item_id).
  Content routes UNION this table to surface backfilled items alongside owned items.
- Similarity threshold is env-var controlled (BACKFILL_SIMILARITY_THRESHOLD).
- The backfill job is idempotent: ON CONFLICT DO NOTHING.
"""
from __future__ import annotations

from datetime import datetime, UTC

import asyncpg
import structlog

from .embeddings import encode_text
from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL — module-level constants
# ---------------------------------------------------------------------------

SQL_GET_TOPIC_KEYWORDS = """
    SELECT name, keywords FROM topics WHERE id = $1
"""

# pgvector cosine distance: <=> operator.  1 - distance = similarity.
# We exclude items already owned by this topic (topic_id != $1) and items
# already backfilled (LEFT JOIN / WHERE tci.topic_id IS NULL).
SQL_SIMILAR_ITEMS = """
    SELECT ci.id,
           1 - (ci.embedding <=> $2::vector) AS similarity_score
    FROM content_items ci
    LEFT JOIN topic_content_items tci
        ON tci.content_item_id = ci.id AND tci.topic_id = $1
    WHERE ci.topic_id != $1
      AND ci.embedding IS NOT NULL
      AND tci.topic_id IS NULL
      AND 1 - (ci.embedding <=> $2::vector) >= $3
    ORDER BY ci.embedding <=> $2::vector
    LIMIT $4
"""

SQL_UPSERT_TCI = """
    INSERT INTO topic_content_items (topic_id, content_item_id, similarity_score, assigned_at)
    VALUES ($1, $2, $3, $4)
    ON CONFLICT (topic_id, content_item_id) DO NOTHING
"""

_BACKFILL_LIMIT = 500  # max items per backfill run — prevents OOM on large corpora


# ---------------------------------------------------------------------------
# Core functions (unit-testable with injected pool / mocked results)
# ---------------------------------------------------------------------------

def _build_query_text(name: str, keywords: list[str]) -> str:
    """Combine topic name + keywords into a single query string for embedding."""
    parts = [name] + list(keywords)
    return " ".join(parts)


async def backfill_topic(topic_id: str, pool: asyncpg.Pool) -> int:
    """Find semantically similar content_items and add them to topic_content_items.

    Returns count of rows inserted.  Idempotent — safe to re-run.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(SQL_GET_TOPIC_KEYWORDS, topic_id)

    if not row:
        log.warning("backfill.topic_not_found", topic_id=topic_id)
        return 0

    query_text = _build_query_text(row["name"], row["keywords"])
    embedding = encode_text(query_text)
    embedding_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"

    threshold = settings.backfill_similarity_threshold

    async with pool.acquire() as conn:
        similar = await conn.fetch(
            SQL_SIMILAR_ITEMS,
            topic_id,
            embedding_str,
            threshold,
            _BACKFILL_LIMIT,
        )

    if not similar:
        log.info("backfill.no_matches", topic_id=topic_id, threshold=threshold)
        return 0

    now = datetime.now(UTC)
    inserted = 0

    async with pool.acquire() as conn:
        async with conn.transaction():
            for item in similar:
                await conn.execute(
                    SQL_UPSERT_TCI,
                    topic_id,
                    item["id"],
                    float(item["similarity_score"]),
                    now,
                )
                inserted += 1

    log.info(
        "backfill.complete",
        topic_id=topic_id,
        inserted=inserted,
        threshold=threshold,
    )
    return inserted
