"""Candidate Topic repository — issues #26 and #27.

A Candidate Topic is a narrative that surfaced inside a Watch Space and is
waiting on an analyst decision. Nothing is monitored until that decision, so
accepting is the only path that creates a Topic.

org_id sits directly on candidate_topics because a candidate is reachable by
its own UUID, so every query here carries it.

Ordering is by measurements of propagation only. No concern score sorts
anything. See ADR 0001.
"""

from __future__ import annotations

from typing import Any, Optional

from anveshak.db import DBConnection

SQL_LIST_CANDIDATES = """
    SELECT ct.id,
           ct.cluster_id,
           ct.watch_space_id,
           ct.status,
           ct.independent_source_count,
           ct.item_count,
           ct.contributing_account_count,
           ct.novelty_score,
           ct.run_count,
           ct.evidence,
           ct.created_at,
           ct.promoted_topic_id,
           nc.label AS cluster_label,
           t.name   AS watch_space_name
    FROM candidate_topics ct
    JOIN narrative_clusters nc ON nc.id = ct.cluster_id
    JOIN topics t ON t.id = ct.watch_space_id
    WHERE ct.org_id = $1
      AND ct.status = $2
    ORDER BY ct.independent_source_count DESC,
             ct.item_count DESC,
             ct.created_at DESC
    LIMIT $3
"""

SQL_GET_CANDIDATE = """
    SELECT ct.id,
           ct.cluster_id,
           ct.watch_space_id,
           ct.org_id,
           ct.status,
           ct.independent_source_count,
           ct.item_count,
           ct.contributing_account_count,
           ct.novelty_score,
           ct.run_count,
           ct.evidence,
           ct.promoted_topic_id,
           nc.label AS cluster_label,
           t.keywords AS watch_space_keywords,
           t.languages AS watch_space_languages
    FROM candidate_topics ct
    JOIN narrative_clusters nc ON nc.id = ct.cluster_id
    JOIN topics t ON t.id = ct.watch_space_id
    WHERE ct.id = $1
      AND ct.org_id = $2
"""

SQL_SET_STATUS = """
    UPDATE candidate_topics
    SET status = $3, promoted_topic_id = $4, decided_at = NOW(), updated_at = NOW()
    WHERE id = $1 AND org_id = $2 AND status = 'pending'
    RETURNING id, status
"""

# The content behind a candidate: the cluster's own items. Used to populate
# an accepted Topic without waiting for new collection.
SQL_CLUSTER_CONTENT_IDS = """
    SELECT ci.id
    FROM content_items ci
    WHERE ci.narrative_cluster_id = $1
      AND ci.org_id = $2
      AND (ci.content_quality IS NULL OR ci.content_quality != 'low_quality')
    ORDER BY COALESCE(ci.published_at, ci.captured_at) DESC
    LIMIT $3
"""

SQL_LINK_CONTENT_TO_TOPIC = """
    INSERT INTO topic_content_items (topic_id, content_item_id)
    SELECT $1, unnest($2::text[])
    ON CONFLICT DO NOTHING
"""


async def list_candidates(
    conn: DBConnection,
    *,
    org_id: str,
    status: str = "pending",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Candidates for one organisation, ordered by how they are spreading."""
    rows = await conn.fetch(SQL_LIST_CANDIDATES, org_id, status, limit)
    return [dict(r) for r in rows]


async def get_candidate(
    conn: DBConnection, candidate_id: str, *, org_id: str
) -> Optional[dict[str, Any]]:
    row = await conn.fetchrow(SQL_GET_CANDIDATE, candidate_id, org_id)
    return dict(row) if row else None


async def set_candidate_status(
    conn: DBConnection,
    candidate_id: str,
    *,
    org_id: str,
    status: str,
    promoted_topic_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Decide a pending candidate. Returns None if it was already decided.

    The status guard in the WHERE clause makes the decision idempotent: a
    second accept finds no pending row and changes nothing, so two clicks
    cannot create two Topics.
    """
    row = await conn.fetchrow(SQL_SET_STATUS, candidate_id, org_id, status, promoted_topic_id)
    return dict(row) if row else None


async def cluster_content_ids(
    conn: DBConnection, cluster_id: str, *, org_id: str, limit: int = 5000
) -> list[str]:
    """Content already collected for this cluster.

    Bounded: the whole result becomes one unnest() array parameter, and the
    most recent content is what makes an accepted Topic immediately usable.
    """
    rows = await conn.fetch(SQL_CLUSTER_CONTENT_IDS, cluster_id, org_id, limit)
    return [r["id"] for r in rows]


async def link_content_to_topic(conn: DBConnection, topic_id: str, content_ids: list[str]) -> None:
    """Attach existing content to a newly accepted Topic.

    Uses topic_content_items rather than reassigning content_items.topic_id,
    because the content still belongs to the Watch Space that collected it.
    """
    if not content_ids:
        return
    await conn.execute(SQL_LINK_CONTENT_TO_TOPIC, topic_id, content_ids)
