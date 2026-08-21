"""Topic relevance scoring — filter irrelevant content before clustering.

Computes cosine similarity between a content item's embedding and the topic's
query embedding (topic name + keywords). Items below the threshold are excluded
from clustering but remain in the DB for auditability.

Reuses the same pattern as backfill.py — encode topic keywords, dot-product
against content embeddings. Both vectors are L2-normalized by encode_text(),
so cosine similarity = dot product.
"""

from __future__ import annotations

import asyncpg
import numpy as np
import structlog

from .embeddings import encode_text
from .metrics import analyst_topic_threshold
from .settings import settings

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# SQL for auto-calibration
# ---------------------------------------------------------------------------

SQL_TOPIC_RELEVANCE_PERCENTILE = """
    SELECT t.id AS topic_id,
           t.name AS topic_name,
           t.topic_relevance_threshold AS current_threshold,
           PERCENTILE_CONT($1) WITHIN GROUP (ORDER BY ci.topic_relevance_score) AS target_threshold,
           COUNT(*) AS item_count
    FROM topics t
    JOIN content_items ci ON ci.topic_id = t.id
    WHERE ci.embedding IS NOT NULL
      AND ci.topic_relevance_score IS NOT NULL
      AND ci.created_at > NOW() - INTERVAL '7 days'
    GROUP BY t.id, t.name, t.topic_relevance_threshold
    HAVING COUNT(*) >= $2
"""

SQL_UPDATE_TOPIC_THRESHOLD = """
    UPDATE topics
    SET topic_relevance_threshold = $1,
        updated_at = NOW()
    WHERE id = $2
"""


async def calibrate_topic_thresholds(pool: asyncpg.Pool) -> int:
    """Compute per-topic relevance thresholds from score distributions.

    For each topic with enough scored items (last 7 days), sets
    topic_relevance_threshold to the target percentile of the distribution,
    clamped to [floor, ceiling]. Returns the number of topics updated.
    """
    updated = 0
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            SQL_TOPIC_RELEVANCE_PERCENTILE,
            settings.relevance_calibration_target_pct,
            settings.relevance_calibration_min_items,
        )

        for row in rows:
            raw = float(row["target_threshold"])
            clamped = max(
                settings.relevance_calibration_floor,
                min(settings.relevance_calibration_ceiling, raw),
            )
            # Round to 3 decimal places for clean display
            clamped = round(clamped, 3)

            old = row["current_threshold"]
            topic_id = row["topic_id"]
            topic_name = row["topic_name"]

            # Skip update if threshold hasn't changed meaningfully
            if old is not None and abs(float(old) - clamped) < 0.005:
                analyst_topic_threshold.labels(
                    topic_id=topic_id,
                    topic_name=topic_name,
                ).set(clamped)
                continue

            await conn.execute(SQL_UPDATE_TOPIC_THRESHOLD, clamped, topic_id)
            updated += 1

            log.info(
                "relevance.threshold_calibrated",
                topic_id=topic_id,
                topic_name=topic_name,
                old_threshold=float(old) if old is not None else None,
                new_threshold=clamped,
                raw_percentile=round(raw, 4),
                item_count=row["item_count"],
            )
            analyst_topic_threshold.labels(
                topic_id=topic_id,
                topic_name=topic_name,
            ).set(clamped)

    if not rows:
        log.info(
            "relevance.calibration_skipped",
            reason="no topics with enough scored items",
            min_items=settings.relevance_calibration_min_items,
        )

    return updated


def build_topic_query_text(name: str, keywords: list[str]) -> str:
    """Combine topic name + keywords into a single query string for embedding.

    Same logic as backfill._build_query_text — inlined to avoid circular import.
    """
    parts = [name] + list(keywords)
    return " ".join(parts)


def build_topic_query_embedding(name: str, keywords: list[str]) -> list[float]:
    """Encode topic name + keywords into a single embedding vector."""
    query_text = build_topic_query_text(name, keywords)
    return encode_text(query_text)


def compute_topic_relevance(
    content_embedding: list[float],
    topic_query_embedding: list[float],
) -> float:
    """Cosine similarity between content embedding and topic query embedding.

    Both vectors are L2-normalized by encode_text(), so cosine similarity
    equals the dot product. Returns float in [-1.0, 1.0]; practically
    [0.0, 1.0] for same-language text.
    """
    a = np.asarray(content_embedding, dtype=np.float32)
    b = np.asarray(topic_query_embedding, dtype=np.float32)
    return float(np.dot(a, b))


def resolve_threshold(per_topic: float | None) -> float:
    """Return per-topic override if set, else global default from settings."""
    if per_topic is not None:
        return per_topic
    return settings.topic_relevance_threshold
