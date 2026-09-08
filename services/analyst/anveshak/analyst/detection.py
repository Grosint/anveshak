"""Candidate Topic detection — issue #26.

A narrative forming inside a Watch Space surfaces to the analyst on its own,
without anyone having configured it. This mirrors the propose-then-approve
pattern discovery.py already uses for sources rather than introducing a
second one: a background job writes rows with status 'pending', and an
analyst accepts or dismisses.

Four gates, all of which must pass:

  independent sources  a narrative nobody else carries is not yet a narrative
  cluster size         too small to read
  novelty              distance from every existing Topic centroid
  persistence          survives at least two clustering runs

Novelty is the gate most easily omitted and the one that matters most.
Without it the inbox fills with rediscoveries of Topics the analyst already
tracks, and the feature reads as broken rather than as absent. Persistence
eliminates the single transient spike.

Ordering is by measurements of propagation only. No concern score sorts
anything here or anywhere else. See ADR 0001.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import asyncpg
import structlog
from anveshak.db import DBConnection

from .settings import settings

log = structlog.get_logger(__name__)

LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

# Clusters inside a Watch Space, with the measurements the gates need.
# contributing_account_count comes from the author handle in labels, which is
# what distinguishes an account from a source: ten posts by one account are
# ten items from one account, not ten independent voices.
SQL_WATCH_SPACE_CLUSTERS = """
    SELECT nc.id                       AS cluster_id,
           nc.topic_id                 AS watch_space_id,
           nc.label,
           nc.item_count,
           nc.independent_source_count,
           nc.embedding_centroid::text AS centroid_text,
           t.org_id,
           (SELECT COUNT(DISTINCT ci.labels->>'author_handle')
              FROM content_items ci
             WHERE ci.narrative_cluster_id = nc.id
               -- Defense in depth. "one cluster, one topic, one org" is not
               -- enforced by any constraint, and topic_content_items carries
               -- no org_id, so the invariant rests on every writer.
               AND ci.org_id = t.org_id
               AND ci.labels->>'author_handle' IS NOT NULL) AS contributing_account_count
    FROM narrative_clusters nc
    JOIN topics t ON t.id = nc.topic_id
    WHERE t.is_watch_space = TRUE
      AND t.status = 'active'
      AND nc.archived_at IS NULL
      AND nc.embedding_centroid IS NOT NULL
      AND nc.item_count >= $1
    -- Bounded: the loop issues two more queries per row, one of them a
    -- pgvector scan, so an unbounded result is an unbounded N+1.
    ORDER BY nc.item_count DESC
    LIMIT $2
"""

# Closest existing Topic to a cluster centroid, within the same organisation.
#
# Watch Spaces are excluded on both sides. A cluster is always inside its own
# Watch Space, so comparing against it would score every candidate as a
# rediscovery of the thing that found it.
SQL_NEAREST_EXISTING_TOPIC = """
    SELECT MAX(1 - (nc.embedding_centroid <=> $1::vector)) AS similarity
    FROM narrative_clusters nc
    JOIN topics t ON t.id = nc.topic_id
    WHERE t.org_id = $2
      AND t.is_watch_space = FALSE
      AND t.status != 'archived'
      AND nc.archived_at IS NULL
      AND nc.embedding_centroid IS NOT NULL
"""

# One row per cluster. A cluster that persists across runs bumps run_count
# rather than producing a second inbox row, which is what makes a dismissal
# survive the next detection pass.
#
# status is a parameter, not a literal. A cluster below the gates is written
# 'recorded' so its persistence history accumulates without it appearing in
# the analyst's inbox, which reads 'pending' only. Writing every cluster as
# 'pending' defeated the novelty and persistence gates entirely.
#
# The conflict branch promotes 'recorded' to 'pending' when the gates come to
# pass, and never touches 'accepted' or 'dismissed': a triage decision is
# final however much the cluster grows.
SQL_UPSERT_CANDIDATE = """
    INSERT INTO candidate_topics (
        id, cluster_id, watch_space_id, org_id, status,
        independent_source_count, item_count, contributing_account_count,
        novelty_score, run_count, evidence, labels, created_at, updated_at
    )
    VALUES ($1, $2, $3, $4, $11, $5, $6, $7, $8, 1, $9::jsonb, $10::jsonb,
            NOW(), NOW())
    ON CONFLICT (cluster_id) DO UPDATE SET
        independent_source_count   = EXCLUDED.independent_source_count,
        item_count                 = EXCLUDED.item_count,
        contributing_account_count = EXCLUDED.contributing_account_count,
        novelty_score              = EXCLUDED.novelty_score,
        run_count                  = candidate_topics.run_count + 1,
        evidence                   = EXCLUDED.evidence,
        updated_at                 = NOW(),
        status = CASE
            WHEN candidate_topics.status IN ('accepted', 'dismissed')
                THEN candidate_topics.status
            ELSE EXCLUDED.status
        END
    RETURNING id, run_count, status
"""

# Run count so far, used by the persistence gate before the upsert.
SQL_EXISTING_CANDIDATE = """
    SELECT ct.id, ct.run_count, ct.status
    FROM candidate_topics ct
    JOIN topics t ON t.id = ct.watch_space_id
    WHERE ct.cluster_id = $1
      AND t.org_id = $2
"""

# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateResult:
    """Outcome of the four promotion gates for one cluster."""

    cluster_id: str
    passed: bool
    failed_gates: list[str] = field(default_factory=list)
    measurements: dict[str, Any] = field(default_factory=dict)


def evaluate_gates(
    *,
    cluster_id: str,
    independent_source_count: int,
    item_count: int,
    novelty_score: float,
    run_count: int,
) -> GateResult:
    """Apply all four gates and report every one that failed.

    Every gate is evaluated rather than short-circuiting, because an analyst
    debugging an empty inbox needs to know which gates blocked a cluster, not
    just the first one.

    novelty_score is 1 - similarity to the closest existing Topic centroid, so
    a higher score means more novel.
    """
    failed: list[str] = []

    if independent_source_count < settings.promotion_min_independent_sources:
        failed.append("independent_sources")
    if item_count < settings.promotion_min_item_count:
        failed.append("item_count")
    if novelty_score < (1.0 - settings.promotion_max_similarity_to_existing):
        failed.append("novelty")
    if run_count < settings.promotion_min_runs:
        failed.append("persistence")

    return GateResult(
        cluster_id=cluster_id,
        passed=not failed,
        failed_gates=failed,
        measurements={
            "independent_source_count": independent_source_count,
            "item_count": item_count,
            "novelty_score": round(novelty_score, 4),
            "run_count": run_count,
            "thresholds": {
                "min_independent_sources": settings.promotion_min_independent_sources,
                "min_item_count": settings.promotion_min_item_count,
                "min_novelty": round(1.0 - settings.promotion_max_similarity_to_existing, 4),
                "min_runs": settings.promotion_min_runs,
            },
        },
    )


# ---------------------------------------------------------------------------
# Detection run
# ---------------------------------------------------------------------------


async def _novelty_score(conn: DBConnection, centroid_text: str, org_id: str) -> float:
    """1 - similarity to the closest existing Topic centroid in this org.

    Returns 1.0 when the organisation has no ordinary Topics yet, because
    nothing has been rediscovered when there is nothing to rediscover.
    """
    row = await conn.fetchrow(SQL_NEAREST_EXISTING_TOPIC, centroid_text, org_id)
    similarity = row["similarity"] if row else None
    if similarity is None:
        return 1.0
    return 1.0 - float(similarity)


async def detect_candidate_topics(pool: asyncpg.Pool) -> int:
    """One detection pass across every Watch Space. Returns candidates written.

    Every cluster large enough to consider is recorded so that its run_count
    accumulates. Only clusters passing all four gates become pending inbox
    rows; the rest stay recorded so a cluster that grows into a candidate
    already has its persistence history.
    """
    written = 0

    async with pool.acquire() as conn:
        clusters = await conn.fetch(
            SQL_WATCH_SPACE_CLUSTERS,
            settings.promotion_min_item_count,
            settings.detection_max_clusters_per_pass,
        )
        if len(clusters) == settings.detection_max_clusters_per_pass:
            log.warning(
                "detection.pass_truncated",
                limit=settings.detection_max_clusters_per_pass,
                reason=(
                    "more clusters qualify than one pass examines, so the "
                    "smallest are not evaluated this cycle"
                ),
            )
        if not clusters:
            log.info(
                "detection.no_watch_space_clusters",
                reason="no active Watch Space has a cluster above the size gate",
            )
            return 0

        for row in clusters:
            org_id = row["org_id"]
            novelty = await _novelty_score(conn, row["centroid_text"], org_id)

            existing = await conn.fetchrow(SQL_EXISTING_CANDIDATE, row["cluster_id"], org_id)
            if existing and existing["status"] in ("dismissed", "accepted"):
                # Triage decisions persist. A dismissed cluster is never
                # re-proposed and an accepted one is already a Topic, however
                # much either grows.
                continue

            # run_count after this pass: the upsert increments an existing row.
            run_count = (existing["run_count"] + 1) if existing else 1

            gates = evaluate_gates(
                cluster_id=row["cluster_id"],
                independent_source_count=row["independent_source_count"] or 0,
                item_count=row["item_count"] or 0,
                novelty_score=novelty,
                run_count=run_count,
            )

            # A cluster below the gates is still recorded, so a slow-growing
            # narrative arrives at the gates with its persistence history
            # already accrued. It is not shown to the analyst until it passes.
            status = "pending" if gates.passed else "recorded"
            if not gates.passed:
                log.debug(
                    "detection.gates_failed",
                    cluster_id=row["cluster_id"],
                    failed_gates=gates.failed_gates,
                )

            evidence = {
                "cluster_label": row["label"],
                "failed_gates": gates.failed_gates,
                "measurements": gates.measurements,
            }

            result = await conn.fetchrow(
                SQL_UPSERT_CANDIDATE,
                str(uuid.uuid4()),
                row["cluster_id"],
                row["watch_space_id"],
                org_id,
                row["independent_source_count"] or 0,
                row["item_count"] or 0,
                row["contributing_account_count"] or 0,
                novelty,
                json.dumps(evidence),
                LABELS_JSON,
                status,
            )

            if gates.passed and result is not None:
                written += 1
                log.info(
                    "detection.candidate_surfaced",
                    cluster_id=row["cluster_id"],
                    watch_space_id=row["watch_space_id"],
                    independent_source_count=row["independent_source_count"],
                    item_count=row["item_count"],
                    novelty_score=round(novelty, 4),
                    run_count=result["run_count"],
                )

    log.info("detection.pass_complete", candidates_passing_all_gates=written)
    return written
