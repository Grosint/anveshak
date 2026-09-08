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
               AND ci.labels->>'author_handle' IS NOT NULL) AS contributing_account_count
    FROM narrative_clusters nc
    JOIN topics t ON t.id = nc.topic_id
    WHERE t.is_watch_space = TRUE
      AND t.status = 'active'
      AND nc.archived_at IS NULL
      AND nc.embedding_centroid IS NOT NULL
      AND nc.item_count >= $1
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
# survive the next detection pass: the conflict branch never resets status.
SQL_UPSERT_CANDIDATE = """
    INSERT INTO candidate_topics (
        id, cluster_id, watch_space_id, org_id, status,
        independent_source_count, item_count, contributing_account_count,
        novelty_score, run_count, evidence, labels, created_at, updated_at
    )
    VALUES ($1, $2, $3, $4, 'pending', $5, $6, $7, $8, 1, $9::jsonb, $10::jsonb,
            NOW(), NOW())
    ON CONFLICT (cluster_id) DO UPDATE SET
        independent_source_count   = EXCLUDED.independent_source_count,
        item_count                 = EXCLUDED.item_count,
        contributing_account_count = EXCLUDED.contributing_account_count,
        novelty_score              = EXCLUDED.novelty_score,
        run_count                  = candidate_topics.run_count + 1,
        evidence                   = EXCLUDED.evidence,
        updated_at                 = NOW()
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

SQL_PENDING_CANDIDATES = """
    SELECT ct.id, ct.cluster_id, ct.watch_space_id, ct.org_id,
           ct.independent_source_count, ct.item_count,
           ct.contributing_account_count, ct.novelty_score, ct.run_count,
           ct.evidence, ct.created_at,
           nc.label AS cluster_label,
           t.name   AS watch_space_name
    FROM candidate_topics ct
    JOIN narrative_clusters nc ON nc.id = ct.cluster_id
    JOIN topics t ON t.id = ct.watch_space_id
    WHERE ct.status = 'pending'
      AND ct.org_id = $1
    ORDER BY ct.independent_source_count DESC,
             ct.item_count DESC,
             ct.created_at DESC
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


def order_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order by how a narrative is spreading. See ADR 0001.

    Independent source count first, then item count. Both are counts over rows
    an analyst can open and recount, which is the property that makes the
    ordering defensible. Nothing here reads a judgement about content.
    """
    return sorted(
        candidates,
        key=lambda c: (
            -(c.get("independent_source_count") or 0),
            -(c.get("item_count") or 0),
        ),
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
        clusters = await conn.fetch(SQL_WATCH_SPACE_CLUSTERS, settings.promotion_min_item_count)
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
            if existing and existing["status"] == "dismissed":
                # Triage decisions persist. A dismissed cluster is never
                # re-proposed, however much it grows.
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

            if not gates.passed and not existing:
                # Nothing recorded yet and it does not qualify. Recording it
                # anyway is what gives a slow-growing narrative the
                # persistence history it will need later.
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


async def list_pending_candidates(conn: DBConnection, org_id: str) -> list[dict[str, Any]]:
    """Pending candidates for one organisation, ordered by propagation."""
    rows = await conn.fetch(SQL_PENDING_CANDIDATES, org_id)
    return [dict(r) for r in rows]
