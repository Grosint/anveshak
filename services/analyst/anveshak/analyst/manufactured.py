"""Manufactured Narrative signal — issue #32.

An analyst cannot currently tell a story many independent outlets reported
from a story many accounts amplified. Both look like volume.

This signal is the inverse of the existing convergence rule. That one fires
when independent source count rises; this one fires when item count and
contributing account count climb while independent source count stays flat.
It reuses measurements already computed.

The wording matters as much as the arithmetic. The signal reports that a
narrative's spread lacks independent sourcing. It never asserts that the
narrative is false, because nothing here measures truth. See ADR 0001.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

import asyncpg
import structlog

from .metrics import analyst_signals_fired_total
from .settings import settings
from .signal_writer import SQL_INSERT_SIGNAL, BroadcastFn, is_duplicate_signal

log = structlog.get_logger(__name__)

_SIGNAL_TYPE_MANUFACTURED = "manufactured_narrative"

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

# Accounts, not sources. Ten posts from one account are ten items from one
# account; the distinction between a source and an account is the whole
# measurement here.
SQL_AMPLIFIED_CLUSTERS = """
    SELECT nc.id                       AS cluster_id,
           nc.topic_id,
           nc.label,
           nc.item_count,
           nc.independent_source_count,
           COUNT(DISTINCT ci.labels->>'author_handle') AS contributing_account_count
    FROM narrative_clusters nc
    JOIN topics t ON t.id = nc.topic_id
    JOIN content_items ci ON ci.narrative_cluster_id = nc.id
    WHERE t.status = 'active'
      AND nc.archived_at IS NULL
      AND nc.independent_source_count <= $1
      AND nc.item_count >= $2
      AND ci.labels->>'author_handle' IS NOT NULL
      AND ci.org_id = t.org_id
      AND (ci.content_quality IS NULL OR ci.content_quality != 'low_quality')
    GROUP BY nc.id, nc.topic_id, nc.label, nc.item_count, nc.independent_source_count
    HAVING COUNT(DISTINCT ci.labels->>'author_handle') >= $3
    ORDER BY nc.item_count DESC
    LIMIT $4
"""

# The repeated claim, and the items an analyst opens to read it across
# accounts. Ordered by account so the repetition is visible rather than
# implied.
# org_id is carried explicitly rather than inferred from the cluster. This
# query puts up to 200 characters of raw scraped text into the signal card
# via most_repeated_claim(), so it is the worst place to rely on an
# invariant no constraint enforces.
SQL_CLUSTER_CLAIM_SAMPLE = """
    SELECT ci.id,
           ci.labels->>'author_handle' AS author_handle,
           COALESCE(NULLIF(ci.clean_text, ''), ci.raw_text) AS work_text
    FROM content_items ci
    JOIN narrative_clusters nc ON nc.id = ci.narrative_cluster_id
    JOIN topics t ON t.id = nc.topic_id
    WHERE ci.narrative_cluster_id = $1
      AND ci.org_id = t.org_id
      AND ci.labels->>'author_handle' IS NOT NULL
      AND (ci.content_quality IS NULL OR ci.content_quality != 'low_quality')
    ORDER BY ci.labels->>'author_handle', ci.captured_at
    LIMIT $2
"""


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def qualifies(
    *,
    item_count: int,
    contributing_account_count: int,
    independent_source_count: int,
) -> bool:
    """True when volume and account breadth climbed while sourcing stayed flat.

    All three conditions are required. Volume alone is a busy narrative,
    many accounts alone is a busy platform, and flat sourcing alone is a
    small story. Together they are amplification.
    """
    return (
        item_count >= settings.manufactured_min_item_count
        and contributing_account_count >= settings.manufactured_min_account_count
        and independent_source_count <= settings.manufactured_max_independent_sources
    )


def build_description(
    *,
    item_count: int,
    contributing_account_count: int,
    independent_source_count: int,
) -> str:
    """State what was measured.

    Every word here is a count. Nothing claims the narrative is false,
    because nothing in this module measures truth.
    """
    return (
        f"{item_count} items from {contributing_account_count} accounts, "
        f"carried by {independent_source_count} independent "
        f"{'source' if independent_source_count == 1 else 'sources'}. "
        f"Spread lacks independent sourcing."
    )


def most_repeated_claim(rows: list[dict[str, Any]]) -> str:
    """The opening sentence that recurs across the most distinct accounts.

    A crude measure on purpose. It exists so the card can show the analyst
    the sentence to go and read, not to decide anything.
    """
    by_opening: dict[str, set[str]] = {}
    for row in rows:
        text = (row.get("work_text") or "").strip()
        if not text:
            continue
        opening = text.split(".")[0].strip()[:200]
        if not opening:
            continue
        by_opening.setdefault(opening, set()).add(row.get("author_handle") or "")

    if not by_opening:
        return ""
    counts = Counter({opening: len(handles) for opening, handles in by_opening.items()})
    return counts.most_common(1)[0][0]


def build_evidence(
    *,
    cluster_id: str,
    item_count: int,
    contributing_account_count: int,
    independent_source_count: int,
    repeated_claim: str,
    content_item_ids: list[str],
) -> dict[str, Any]:
    """The arithmetic behind the signal, for an analyst to check rather than trust.

    Carries each threshold and the margin by which it was crossed, so the
    card can show which one fired and by how much.
    """
    return {
        "cluster_id": cluster_id,
        "item_count": item_count,
        "account_count": contributing_account_count,
        "independent_source_count": independent_source_count,
        "thresholds": {
            "min_item_count": settings.manufactured_min_item_count,
            "min_account_count": settings.manufactured_min_account_count,
            "max_independent_sources": settings.manufactured_max_independent_sources,
        },
        "margins": {
            "item_count": item_count - settings.manufactured_min_item_count,
            "account_count": (contributing_account_count - settings.manufactured_min_account_count),
            "independent_sources_below_ceiling": (
                settings.manufactured_max_independent_sources - independent_source_count
            ),
        },
        "repeated_claim": repeated_claim,
        "content_item_ids": content_item_ids,
    }


# ---------------------------------------------------------------------------
# Check cycle
# ---------------------------------------------------------------------------


async def check_manufactured_narratives(
    pool: asyncpg.Pool,
    broadcast: BroadcastFn,
) -> int:
    """One pass over amplified clusters. Returns count of signals fired.

    Dedup is the shared 24h per-cluster window every other signal uses.
    """
    fired = 0

    async with pool.acquire() as conn:
        clusters = await conn.fetch(
            SQL_AMPLIFIED_CLUSTERS,
            settings.manufactured_max_independent_sources,
            settings.manufactured_min_item_count,
            settings.manufactured_min_account_count,
            settings.manufactured_max_clusters_per_pass,
        )

        for row in clusters:
            cluster_id: str = row["cluster_id"]
            item_count: int = row["item_count"] or 0
            account_count: int = row["contributing_account_count"] or 0
            isc: int = row["independent_source_count"] or 0

            if not qualifies(
                item_count=item_count,
                contributing_account_count=account_count,
                independent_source_count=isc,
            ):
                continue

            if await is_duplicate_signal(conn, cluster_id, _SIGNAL_TYPE_MANUFACTURED):
                continue

            sample = await conn.fetch(
                SQL_CLUSTER_CLAIM_SAMPLE,
                cluster_id,
                settings.manufactured_claim_sample_size,
            )
            sample_rows = [dict(r) for r in sample]

            description = build_description(
                item_count=item_count,
                contributing_account_count=account_count,
                independent_source_count=isc,
            )
            evidence = build_evidence(
                cluster_id=cluster_id,
                item_count=item_count,
                contributing_account_count=account_count,
                independent_source_count=isc,
                repeated_claim=most_repeated_claim(sample_rows),
                content_item_ids=[r["id"] for r in sample_rows],
            )

            signal_id = str(uuid.uuid4())
            now = datetime.now(UTC)
            await conn.execute(
                SQL_INSERT_SIGNAL,
                signal_id,
                row["topic_id"],
                cluster_id,
                _SIGNAL_TYPE_MANUFACTURED,
                description,
                json.dumps(evidence),
                now,
            )
            analyst_signals_fired_total.labels(severity="MEDIUM").inc()

            payload = {
                "type": "signal",
                "signal_id": signal_id,
                "topic_id": row["topic_id"],
                "cluster_id": cluster_id,
                "cluster_label": row["label"],
                "severity": "MEDIUM",
                "signal_type": _SIGNAL_TYPE_MANUFACTURED,
                "description": description,
            }
            try:
                await broadcast(payload)
            except Exception as exc:
                log.warning("manufactured.broadcast_failed", signal_id=signal_id, error=str(exc))

            log.info(
                "manufactured.signal_fired",
                signal_id=signal_id,
                cluster_id=cluster_id,
                item_count=item_count,
                account_count=account_count,
                independent_source_count=isc,
            )
            fired += 1

    return fired
