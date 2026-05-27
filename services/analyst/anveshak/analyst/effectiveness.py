"""Source effectiveness analytics — traces signals to sources and ranks catalog entries.

Weekly ARQ cron job that computes how effective each catalog source has been
at producing intelligence that matters. Updates source_catalog with computed
recommendation_rank and analytics scores.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

import asyncpg
import structlog

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

SQL_APPROVED_CATALOG_ENTRIES = """
    SELECT ca.catalog_entry_id,
           ca.source_id,
           COUNT(DISTINCT ca.topic_id) AS topics_approved_count
    FROM catalog_approvals ca
    GROUP BY ca.catalog_entry_id, ca.source_id
"""

SQL_SIGNAL_CONTRIBUTIONS = """
    SELECT COUNT(DISTINCT s.id) AS signal_count
    FROM signals s
    JOIN narrative_clusters nc ON nc.id = s.cluster_id
    JOIN content_items ci ON ci.narrative_cluster_id = nc.id
    WHERE ci.source_id = $1
"""

SQL_RELEVANCE_HIT_RATE = """
    SELECT CASE
        WHEN COUNT(*) = 0 THEN NULL
        ELSE COUNT(*) FILTER (
            WHERE ci.topic_relevance_score IS NOT NULL
              AND ci.topic_relevance_score >= COALESCE(t.topic_relevance_threshold, 0.35)
        )::REAL / COUNT(*)
    END AS hit_rate
    FROM content_items ci
    LEFT JOIN topics t ON ci.topic_id = t.id
    WHERE ci.source_id = $1
      AND ci.embedding IS NOT NULL
"""

SQL_CLUSTER_PARTICIPATION = """
    SELECT CASE
        WHEN COUNT(*) = 0 THEN NULL
        ELSE COUNT(*) FILTER (WHERE narrative_cluster_id IS NOT NULL)::REAL / COUNT(*)
    END AS cluster_rate
    FROM content_items
    WHERE source_id = $1
"""

SQL_UPDATE_CATALOG_EFFECTIVENESS = """
    UPDATE source_catalog
    SET signal_contribution_count  = $2,
        relevance_hit_rate         = $3,
        cluster_participation_rate = $4,
        topics_approved_count      = $5,
        recommendation_rank        = $6,
        updated_at                 = $7
    WHERE id = $1
"""


# ---------------------------------------------------------------------------
# Pure function — rank computation
# ---------------------------------------------------------------------------


def compute_recommendation_rank(
    topics_approved: int,
    signal_contributions: int,
    relevance_hit_rate: float | None,
) -> str:
    """Determine recommendation rank based on performance tiers.

    | Level            | Criteria                                              |
    |------------------|-------------------------------------------------------|
    | most_recommended | Approved in 2+ topics AND contributed to 3+ signals   |
    | proven           | Approved in 1+ topic AND contributed to 1+ signal     |
    | low_performer    | Approved but < 10% items pass relevance after 2 weeks |
    | curated          | Never approved — pure catalog entry                   |
    """
    if topics_approved == 0:
        return "curated"

    # Check for low performer first (approved but bad relevance)
    if (
        relevance_hit_rate is not None
        and relevance_hit_rate < 0.10
        and signal_contributions == 0
    ):
        return "low_performer"

    if topics_approved >= 2 and signal_contributions >= 3:
        return "most_recommended"

    if topics_approved >= 1 and signal_contributions >= 1:
        return "proven"

    # Approved but no signal contributions yet — still curated
    if signal_contributions == 0 and (relevance_hit_rate is None or relevance_hit_rate >= 0.10):
        return "curated"

    return "curated"


# ---------------------------------------------------------------------------
# ARQ job — weekly effectiveness computation
# ---------------------------------------------------------------------------


async def compute_source_effectiveness(pool: asyncpg.Pool) -> int:
    """Compute effectiveness analytics for all approved catalog entries.

    Traces: signal → cluster → content_items → source → catalog_approval → source_catalog

    Returns count of catalog entries updated.
    """
    async with pool.acquire() as conn:
        # Get all approved catalog entries with their source IDs
        approved = await conn.fetch(SQL_APPROVED_CATALOG_ENTRIES)
        if not approved:
            log.info("effectiveness.no_approved_entries")
            return 0

        now = datetime.now(UTC)
        count = 0

        for entry in approved:
            catalog_entry_id = entry["catalog_entry_id"]
            source_id = entry["source_id"]
            topics_approved = entry["topics_approved_count"]

            # Compute signal contributions
            signal_rows = await conn.fetch(SQL_SIGNAL_CONTRIBUTIONS, source_id)
            signal_count = signal_rows[0]["signal_count"] if signal_rows else 0

            # Compute relevance hit rate
            rel_rows = await conn.fetch(SQL_RELEVANCE_HIT_RATE, source_id)
            relevance_rate = rel_rows[0]["hit_rate"] if rel_rows else None

            # Compute cluster participation rate
            cluster_rows = await conn.fetch(SQL_CLUSTER_PARTICIPATION, source_id)
            cluster_rate = cluster_rows[0]["cluster_rate"] if cluster_rows else None

            # Determine rank
            rank = compute_recommendation_rank(
                topics_approved=topics_approved,
                signal_contributions=signal_count,
                relevance_hit_rate=relevance_rate,
            )

            # Update catalog entry
            await conn.execute(
                SQL_UPDATE_CATALOG_EFFECTIVENESS,
                catalog_entry_id,
                signal_count,
                relevance_rate,
                cluster_rate,
                topics_approved,
                rank,
                now,
            )
            count += 1

            log.debug(
                "effectiveness.entry_updated",
                catalog_entry_id=catalog_entry_id,
                signals=signal_count,
                relevance=relevance_rate,
                cluster=cluster_rate,
                rank=rank,
            )

        log.info(
            "effectiveness.complete",
            entries_updated=count,
        )
        return count
