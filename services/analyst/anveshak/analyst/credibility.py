"""Source credibility auto-feedback loop (M1 complete — criteria 2.21–2.25, 7.1–7.5).

Three automatic scoring passes, all audit-logged (CLAUDE.md rule 8):

1. Deepfake amplification drop (2.21–2.24, 7.3):
   Sources that shared items with deepfake_score > 0.8 → score reduced.
   Governed by settings.credibility_min_auto_drop.

2. Cross-verification boost (7.1):
   Sources in multi-platform clusters (independent_source_count >= 2)
   whose own credibility_score >= credibility_high_threshold → score boosted.
   Governed by settings.credibility_min_auto_boost.
   Triggered by run_clustering ARQ job (not a timer).

3. Contradiction drop (7.2):
   Sources with a high ratio of unclustered items on topics that have real clusters
   → score reduced.  Governed by settings.credibility_min_auto_drop.
   Runs as a daily ARQ cron job.

All score changes are clamped to [0.0, 100.0] (7.5).
"""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

import asyncpg
import structlog

from .metrics import analyst_credibility_changes_total
from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL — module-level constants
# ---------------------------------------------------------------------------

# Sources that have at least one content item linked to a deepfake result
# with deepfake_score > 0.8 in the last 7 days, grouped by source.
SQL_DEEPFAKE_AMPLIFIERS = """
    SELECT
        s.id          AS source_id,
        s.name        AS source_name,
        s.credibility_score,
        COUNT(vr.id)  AS deepfake_count
    FROM sources s
    JOIN content_items ci ON ci.source_id = s.id
    JOIN media_assets ma ON ma.content_item_id = ci.id
    JOIN vision_results vr ON vr.media_asset_id = ma.id
    WHERE vr.deepfake_score > 0.8
      AND vr.processed_at > NOW() - INTERVAL '7 days'
      AND s.auto_score_enabled = TRUE
      AND s.credibility_score > 0
    GROUP BY s.id, s.name, s.credibility_score
"""

SQL_UPDATE_SOURCE_SCORE = """
    UPDATE sources
    SET credibility_score = $1,
        updated_at        = $2
    WHERE id = $3
"""

SQL_INSERT_AUDIT_LOG = """
    INSERT INTO credibility_audit_log (
        id, source_id, old_score, new_score, reason, changed_by, created_at, labels
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7,
            '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
"""

# Cross-verification (7.1): sources contributing to multi-platform clusters
# whose own score meets the high-credibility threshold.
SQL_CROSS_VERIFY_SOURCES = """
    SELECT DISTINCT ON (s.id)
        s.id              AS source_id,
        s.name            AS source_name,
        s.credibility_score
    FROM content_items ci
    JOIN sources s            ON s.id  = ci.source_id
    JOIN narrative_clusters nc ON nc.id = ci.narrative_cluster_id
    WHERE ci.topic_id     = $1
      AND nc.independent_source_count >= 2
      AND s.credibility_score >= $2
      AND s.credibility_score  < 100.0
      AND s.auto_score_enabled = TRUE
"""

# Contradiction (7.2): sources with a high ratio of unclustered items
# on topics that have real clusters.
SQL_CONTRADICTION_SOURCES = """
    SELECT
        s.id              AS source_id,
        s.name            AS source_name,
        s.credibility_score,
        COUNT(*) FILTER (WHERE ci.narrative_cluster_id IS NULL) AS noise_count,
        COUNT(*)                                                 AS total_count
    FROM content_items ci
    JOIN sources s ON s.id = ci.source_id
    WHERE ci.topic_id IN (
        SELECT DISTINCT topic_id
        FROM narrative_clusters
        WHERE item_count >= $1
    )
      AND s.auto_score_enabled = TRUE
      AND s.credibility_score  > 0
      AND ci.captured_at > NOW() - INTERVAL '7 days'
    GROUP BY s.id, s.name, s.credibility_score
    HAVING COUNT(*) >= $2
"""

_CHANGED_BY = "analyst.auto_credibility"


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def clamp_score(score: float) -> float:
    """Clamp credibility score to [0.0, 100.0]. Pure function (7.5)."""
    return round(max(0.0, min(100.0, score)), 2)


def compute_new_score(old_score: float, deepfake_count: int) -> float:
    """Compute reduced credibility score based on deepfake amplification count.

    Drop = min_auto_drop * deepfake_count, clamped to [0, 100].
    Pure function — unit-testable without DB.
    """
    drop = settings.credibility_min_auto_drop * deepfake_count
    return clamp_score(old_score - drop)


async def apply_credibility_drop(
    conn: asyncpg.Connection,
    source_id: str,
    old_score: float,
    new_score: float,
    reason: str,
    now: datetime,
) -> None:
    """Atomically update score and write audit log in the caller's transaction.

    Caller MUST call this inside an open transaction (criteria 2.24).
    """
    await conn.execute(SQL_UPDATE_SOURCE_SCORE, new_score, now, source_id)
    await conn.execute(
        SQL_INSERT_AUDIT_LOG,
        str(uuid.uuid4()),
        source_id,
        old_score,
        new_score,
        reason,
        _CHANGED_BY,
        now,
    )
    analyst_credibility_changes_total.labels(direction="down").inc()


async def apply_credibility_boost(
    conn: asyncpg.Connection,
    source_id: str,
    old_score: float,
    new_score: float,
    reason: str,
    now: datetime,
) -> None:
    """Atomically boost score and write audit log in the caller's transaction.

    Caller MUST call this inside an open transaction (same pattern as apply_credibility_drop).
    """
    await conn.execute(SQL_UPDATE_SOURCE_SCORE, new_score, now, source_id)
    await conn.execute(
        SQL_INSERT_AUDIT_LOG,
        str(uuid.uuid4()),
        source_id,
        old_score,
        new_score,
        reason,
        _CHANGED_BY,
        now,
    )
    analyst_credibility_changes_total.labels(direction="up").inc()


async def find_deepfake_amplifiers(
    conn: asyncpg.Connection,
) -> list[asyncpg.Record]:
    """Return sources that have amplified high-confidence deepfakes recently."""
    return await conn.fetch(SQL_DEEPFAKE_AMPLIFIERS)


# ---------------------------------------------------------------------------
# Top-level orchestrator (called from ARQ job and credibility_update_loop)
# ---------------------------------------------------------------------------

async def run_credibility_update(pool: asyncpg.Pool) -> int:
    """Run one credibility auto-update pass. Returns number of sources updated.

    Criteria 2.21–2.24.
    """
    updated = 0

    async with pool.acquire() as conn:
        amplifiers = await find_deepfake_amplifiers(conn)

        for row in amplifiers:
            source_id: str = row["source_id"]
            old_score: float = row["credibility_score"]
            deepfake_count: int = row["deepfake_count"]

            new_score = compute_new_score(old_score, deepfake_count)

            if abs(new_score - old_score) < 0.01:
                continue  # score already at minimum or no meaningful change

            reason = (
                f"Auto-reduced: {deepfake_count} deepfake-amplified item(s) "
                f"detected in last 7 days (score > 0.8)"
            )
            now = datetime.now(UTC)

            async with conn.transaction():  # criteria 2.24: single transaction
                await apply_credibility_drop(
                    conn=conn,
                    source_id=source_id,
                    old_score=old_score,
                    new_score=new_score,
                    reason=reason,
                    now=now,
                )

            updated += 1
            log.info(
                "credibility.score_updated",
                source_id=source_id,
                old_score=old_score,
                new_score=new_score,
                deepfake_count=deepfake_count,
            )

    log.info("credibility.update_complete", sources_updated=updated)
    return updated


# ---------------------------------------------------------------------------
# Cross-verification boost (7.1) — called post-clustering, per topic
# ---------------------------------------------------------------------------

async def run_cross_verification_update(pool: asyncpg.Pool, topic_id: str) -> int:
    """Boost credibility of high-credibility sources confirmed by multi-platform clusters.

    Criteria 7.1. Triggered from the run_clustering ARQ job — not a cron.
    Returns number of sources boosted.
    """
    updated = 0

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            SQL_CROSS_VERIFY_SOURCES,
            topic_id,
            settings.credibility_high_threshold,
        )

        for row in rows:
            source_id: str = row["source_id"]
            old_score: float = row["credibility_score"]
            new_score = clamp_score(old_score + settings.credibility_cross_verify_boost)

            if abs(new_score - old_score) < settings.credibility_min_auto_boost:
                continue  # below minimum boost threshold — skip audit log noise

            reason = (
                f"Auto-boosted: source confirmed in multi-platform cluster "
                f"(cross-verification, topic {topic_id})"
            )
            now = datetime.now(UTC)

            async with conn.transaction():
                await apply_credibility_boost(
                    conn=conn,
                    source_id=source_id,
                    old_score=old_score,
                    new_score=new_score,
                    reason=reason,
                    now=now,
                )

            updated += 1
            log.info(
                "credibility.cross_verify_boosted",
                source_id=source_id,
                topic_id=topic_id,
                old_score=old_score,
                new_score=new_score,
            )

    log.info("credibility.cross_verify_complete", topic_id=topic_id, sources_updated=updated)
    return updated


# ---------------------------------------------------------------------------
# Contradiction drop (7.2) — daily global pass
# ---------------------------------------------------------------------------

async def run_contradiction_update(pool: asyncpg.Pool) -> int:
    """Reduce credibility of sources with a high noise-item ratio on clustered topics.

    Criteria 7.2. Noise = content_items where narrative_cluster_id IS NULL on a
    topic that has real clusters. A source whose items are predominantly unclustered
    while other sources cluster successfully is treated as a contradiction signal.
    Returns number of sources penalised.
    """
    updated = 0

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            SQL_CONTRADICTION_SOURCES,
            settings.credibility_contradiction_min_items,
            settings.credibility_contradiction_min_items,
        )

        for row in rows:
            source_id: str = row["source_id"]
            old_score: float = row["credibility_score"]
            noise_count: int = row["noise_count"]
            total_count: int = row["total_count"]

            noise_ratio = noise_count / total_count if total_count > 0 else 0.0

            if noise_ratio < settings.credibility_noise_ratio_threshold:
                continue  # below contradiction threshold

            new_score = clamp_score(old_score - settings.credibility_contradiction_drop)

            if abs(new_score - old_score) < settings.credibility_min_auto_drop:
                continue  # below minimum drop threshold — skip audit log noise

            reason = (
                f"Auto-reduced: {noise_count}/{total_count} items unclustered "
                f"(noise ratio {noise_ratio:.2f} >= threshold "
                f"{settings.credibility_noise_ratio_threshold})"
            )
            now = datetime.now(UTC)

            async with conn.transaction():
                await apply_credibility_drop(
                    conn=conn,
                    source_id=source_id,
                    old_score=old_score,
                    new_score=new_score,
                    reason=reason,
                    now=now,
                )

            updated += 1
            log.info(
                "credibility.contradiction_dropped",
                source_id=source_id,
                old_score=old_score,
                new_score=new_score,
                noise_ratio=noise_ratio,
            )

    log.info("credibility.contradiction_complete", sources_updated=updated)
    return updated
