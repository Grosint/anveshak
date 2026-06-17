"""Tracker repository — SQL constants and async functions for persistent case files.

Trackers are analyst-owned objects that survive Leiden re-clustering.
Content is linked via tracker_content_items with provenance tracking.
Notes are append-only and immutable.
"""
from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import Any, Optional

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

_LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'

SQL_INSERT_TRACKER = """
    INSERT INTO trackers (
        id, case_number, org_id, topic_id, origin_cluster_id,
        title, external_case_ref, centroid, centroid_threshold,
        status, priority, assigned_to, created_by,
        created_at, updated_at, labels
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
"""

SQL_GET_TRACKER = """
    SELECT t.*,
           (SELECT COUNT(*) FROM tracker_content_items tci
            WHERE tci.tracker_id = t.id AND tci.status = 'confirmed') AS content_count,
           (SELECT COUNT(*) FROM tracker_content_items tci
            WHERE tci.tracker_id = t.id AND tci.status = 'pending') AS pending_count
    FROM trackers t
    WHERE t.id = $1
"""

SQL_GET_TRACKER_ORG = "SELECT org_id FROM trackers WHERE id = $1"

SQL_LIST_TRACKERS_BY_ORG = """
    SELECT t.*,
           (SELECT COUNT(*) FROM tracker_content_items tci
            WHERE tci.tracker_id = t.id AND tci.status = 'confirmed') AS content_count,
           (SELECT COUNT(*) FROM tracker_content_items tci
            WHERE tci.tracker_id = t.id AND tci.status = 'pending') AS pending_count
    FROM trackers t
    WHERE t.org_id = $1
    ORDER BY t.updated_at DESC
"""

SQL_LIST_TRACKERS_BY_TOPIC = """
    SELECT t.*,
           (SELECT COUNT(*) FROM tracker_content_items tci
            WHERE tci.tracker_id = t.id AND tci.status = 'confirmed') AS content_count,
           (SELECT COUNT(*) FROM tracker_content_items tci
            WHERE tci.tracker_id = t.id AND tci.status = 'pending') AS pending_count
    FROM trackers t
    WHERE t.topic_id = $1 AND t.org_id = $2
    ORDER BY t.updated_at DESC
"""

SQL_UPDATE_TRACKER_STATUS = """
    UPDATE trackers
    SET status = $1, concluded_by = $2, concluded_at = $3,
        closing_summary = $4, updated_at = $5
    WHERE id = $6
"""

SQL_UPDATE_TRACKER_PRIORITY = """
    UPDATE trackers SET priority = $1, updated_at = $2 WHERE id = $3
"""

SQL_UPDATE_TRACKER_ASSIGNMENT = """
    UPDATE trackers SET assigned_to = $1, updated_at = $2 WHERE id = $3
"""

SQL_UPDATE_TRACKER_DETAILS = """
    UPDATE trackers SET title = $1, external_case_ref = $2, updated_at = $3 WHERE id = $4
"""

# -- Content items --

SQL_INSERT_TRACKER_CONTENT = """
    INSERT INTO tracker_content_items (
        tracker_id, content_item_id, attached_by, status,
        similarity_score, confirmed_by, confirmed_at, attached_at
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    ON CONFLICT DO NOTHING
"""

SQL_LIST_TRACKER_CONTENT = """
    SELECT ci.id, ci.url, LEFT(ci.clean_text, 500) AS clean_text,
           ci.language, ci.credibility_score_at_capture, ci.captured_at,
           s.name AS source_name, s.platform,
           tci.attached_by, tci.status, tci.similarity_score,
           tci.confirmed_by, tci.confirmed_at, tci.attached_at
    FROM tracker_content_items tci
    JOIN content_items ci ON ci.id = tci.content_item_id
    LEFT JOIN sources s ON s.id = ci.source_id
    WHERE tci.tracker_id = $1 AND tci.status = 'confirmed'
    ORDER BY ci.captured_at DESC
    LIMIT $2 OFFSET $3
"""

SQL_LIST_PENDING_CONTENT = """
    SELECT ci.id, ci.url, LEFT(ci.clean_text, 500) AS clean_text,
           ci.language, ci.credibility_score_at_capture, ci.captured_at,
           s.name AS source_name, s.platform,
           tci.attached_by, tci.similarity_score, tci.attached_at
    FROM tracker_content_items tci
    JOIN content_items ci ON ci.id = tci.content_item_id
    LEFT JOIN sources s ON s.id = ci.source_id
    WHERE tci.tracker_id = $1 AND tci.status = 'pending'
    ORDER BY tci.similarity_score DESC
"""

SQL_CONFIRM_CONTENT = """
    UPDATE tracker_content_items
    SET status = 'confirmed', confirmed_by = $1, confirmed_at = $2
    WHERE tracker_id = $3 AND content_item_id = $4
"""

SQL_CONFIRM_ALL_PENDING = """
    UPDATE tracker_content_items
    SET status = 'confirmed', confirmed_by = $1, confirmed_at = $2
    WHERE tracker_id = $3 AND status = 'pending'
"""

SQL_DELETE_TRACKER_CONTENT = """
    DELETE FROM tracker_content_items
    WHERE tracker_id = $1 AND content_item_id = $2
"""

# -- Exclusions --

SQL_INSERT_EXCLUSION = """
    INSERT INTO tracker_content_exclusions (
        tracker_id, content_item_id, excluded_by, excluded_at
    ) VALUES ($1, $2, $3, $4)
    ON CONFLICT DO NOTHING
"""

# -- Notes (append-only, NO update/delete SQL) --

SQL_INSERT_NOTE = """
    INSERT INTO tracker_notes (
        id, tracker_id, user_id, body, created_at, labels
    ) VALUES ($1, $2, $3, $4, $5, $6)
"""

SQL_LIST_NOTES = """
    SELECT id, tracker_id, user_id, body, created_at
    FROM tracker_notes
    WHERE tracker_id = $1
    ORDER BY created_at DESC
"""

# -- Signals --

SQL_LINK_SIGNAL = """
    INSERT INTO tracker_signals (tracker_id, signal_id, linked_at, linked_by)
    VALUES ($1, $2, $3, $4)
    ON CONFLICT DO NOTHING
"""

SQL_LIST_TRACKER_SIGNALS = """
    SELECT s.*, ts.linked_at, ts.linked_by
    FROM tracker_signals ts
    JOIN signals s ON s.id = ts.signal_id
    WHERE ts.tracker_id = $1
    ORDER BY ts.linked_at DESC
"""

# -- Audit log --

SQL_INSERT_AUDIT_LOG = """
    INSERT INTO tracker_audit_log (
        id, tracker_id, action, actor_id, detail, created_at
    ) VALUES ($1, $2, $3, $4, $5, $6)
"""

SQL_LIST_AUDIT_LOG = """
    SELECT id, tracker_id, action, actor_id, detail, created_at
    FROM tracker_audit_log
    WHERE tracker_id = $1
    ORDER BY created_at DESC
    LIMIT $2 OFFSET $3
"""

# -- Seed from cluster --

SQL_SEED_FROM_CLUSTER = """
    INSERT INTO tracker_content_items (
        tracker_id, content_item_id, attached_by, status, attached_at
    )
    SELECT $1, ci.id, 'seed', 'confirmed', NOW()
    FROM content_items ci
    WHERE ci.narrative_cluster_id = $2
    ON CONFLICT DO NOTHING
"""

SQL_GET_CLUSTER_CENTROID = """
    SELECT embedding_centroid, label, topic_id
    FROM narrative_clusters
    WHERE id = $1
"""


# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------


async def generate_case_number(conn: asyncpg.Connection) -> str:
    """Generate next case number: TRK-{year}-{sequence:04d}."""
    seq_val = await conn.fetchval("SELECT nextval('tracker_case_seq')")
    year = datetime.now(UTC).year
    return f"TRK-{year}-{seq_val:04d}"


async def create_tracker(
    conn: asyncpg.Connection,
    *,
    topic_id: str,
    title: str,
    created_by: str,
    org_id: str | None = None,
    origin_cluster_id: str | None = None,
    external_case_ref: str | None = None,
    centroid: Any = None,
    centroid_threshold: float = 0.70,
    status: str = "watching",
    priority: str = "medium",
    assigned_to: str | None = None,
) -> dict[str, Any]:
    """Create a new tracker and return its data."""
    tracker_id = str(uuid.uuid4())
    case_number = await generate_case_number(conn)
    now = datetime.now(UTC)

    await conn.execute(
        SQL_INSERT_TRACKER,
        tracker_id, case_number, org_id, topic_id, origin_cluster_id,
        title, external_case_ref, centroid, centroid_threshold,
        status, priority, assigned_to, created_by,
        now, now, _LABELS_JSON,
    )

    # Log creation
    await _log_audit(conn, tracker_id, "created", created_by, {
        "title": title, "status": status, "priority": priority,
    })

    row = await conn.fetchrow(SQL_GET_TRACKER, tracker_id)
    return dict(row) if row else {"id": tracker_id, "case_number": case_number}


async def create_tracker_from_cluster(
    conn: asyncpg.Connection,
    cluster_id: str,
    user_id: str,
    *,
    org_id: str | None = None,
    external_case_ref: str | None = None,
    status: str = "active",
    priority: str = "medium",
) -> dict[str, Any]:
    """Create a tracker seeded from a narrative cluster."""
    cluster = await conn.fetchrow(SQL_GET_CLUSTER_CENTROID, cluster_id)
    if not cluster:
        raise ValueError(f"Cluster {cluster_id} not found")

    tracker = await create_tracker(
        conn,
        topic_id=cluster["topic_id"],
        title=cluster["label"],
        created_by=user_id,
        org_id=org_id,
        origin_cluster_id=cluster_id,
        centroid=cluster["embedding_centroid"],
        status=status,
        priority=priority,
        external_case_ref=external_case_ref,
    )

    # Seed content items from cluster
    await conn.execute(SQL_SEED_FROM_CLUSTER, tracker["id"], cluster_id)

    return tracker


async def get_tracker(
    conn: asyncpg.Connection, tracker_id: str
) -> dict[str, Any] | None:
    """Get a single tracker with content/pending counts."""
    row = await conn.fetchrow(SQL_GET_TRACKER, tracker_id)
    return dict(row) if row else None


async def list_trackers_by_org(
    conn: asyncpg.Connection, org_id: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_TRACKERS_BY_ORG, org_id)
    return [dict(r) for r in rows]


async def list_trackers_by_topic(
    conn: asyncpg.Connection, topic_id: str, org_id: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_TRACKERS_BY_TOPIC, topic_id, org_id)
    return [dict(r) for r in rows]


async def update_tracker_status(
    conn: asyncpg.Connection,
    tracker_id: str,
    status: str,
    user_id: str,
    *,
    closing_summary: str | None = None,
) -> None:
    """Update tracker status. Concluded requires closing_summary."""
    if status == "concluded" and not closing_summary:
        raise ValueError("closing_summary is required when concluding a tracker")

    now = datetime.now(UTC)
    concluded_by = user_id if status == "concluded" else None
    concluded_at = now if status == "concluded" else None

    await conn.execute(
        SQL_UPDATE_TRACKER_STATUS,
        status, concluded_by, concluded_at, closing_summary, now, tracker_id,
    )
    await _log_audit(conn, tracker_id, "status_changed", user_id, {
        "status": status, "closing_summary": closing_summary,
    })


async def update_tracker_priority(
    conn: asyncpg.Connection, tracker_id: str, priority: str, user_id: str
) -> None:
    now = datetime.now(UTC)
    await conn.execute(SQL_UPDATE_TRACKER_PRIORITY, priority, now, tracker_id)
    await _log_audit(conn, tracker_id, "priority_changed", user_id, {"priority": priority})


async def update_tracker_assignment(
    conn: asyncpg.Connection, tracker_id: str, assigned_to: str | None, user_id: str
) -> None:
    now = datetime.now(UTC)
    await conn.execute(SQL_UPDATE_TRACKER_ASSIGNMENT, assigned_to, now, tracker_id)
    await _log_audit(conn, tracker_id, "assigned", user_id, {"assigned_to": assigned_to})


# -- Content management --

async def add_content(
    conn: asyncpg.Connection,
    tracker_id: str,
    content_item_id: str,
    attached_by: str,
    user_id: str,
    *,
    similarity_score: float | None = None,
    status: str = "confirmed",
) -> None:
    """Add a content item to a tracker."""
    now = datetime.now(UTC)
    confirmed_by = user_id if status == "confirmed" else None
    confirmed_at = now if status == "confirmed" else None

    await conn.execute(
        SQL_INSERT_TRACKER_CONTENT,
        tracker_id, content_item_id, attached_by, status,
        similarity_score, confirmed_by, confirmed_at, now,
    )
    await _log_audit(conn, tracker_id, "content_added", user_id, {
        "content_item_id": content_item_id, "attached_by": attached_by,
    })


async def confirm_content(
    conn: asyncpg.Connection, tracker_id: str, content_item_id: str, user_id: str
) -> None:
    now = datetime.now(UTC)
    await conn.execute(SQL_CONFIRM_CONTENT, user_id, now, tracker_id, content_item_id)
    await _log_audit(conn, tracker_id, "content_confirmed", user_id, {
        "content_item_id": content_item_id,
    })


async def confirm_all_pending(
    conn: asyncpg.Connection, tracker_id: str, user_id: str
) -> None:
    now = datetime.now(UTC)
    await conn.execute(SQL_CONFIRM_ALL_PENDING, user_id, now, tracker_id)
    await _log_audit(conn, tracker_id, "all_pending_confirmed", user_id, {})


async def reject_content(
    conn: asyncpg.Connection, tracker_id: str, content_item_id: str, user_id: str
) -> None:
    """Reject a pending item: remove from tracker, add to exclusions."""
    now = datetime.now(UTC)
    await conn.execute(SQL_DELETE_TRACKER_CONTENT, tracker_id, content_item_id)
    await conn.execute(SQL_INSERT_EXCLUSION, tracker_id, content_item_id, user_id, now)
    await _log_audit(conn, tracker_id, "content_rejected", user_id, {
        "content_item_id": content_item_id,
    })


async def list_content(
    conn: asyncpg.Connection, tracker_id: str, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_TRACKER_CONTENT, tracker_id, limit, offset)
    return [dict(r) for r in rows]


async def list_pending(
    conn: asyncpg.Connection, tracker_id: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_PENDING_CONTENT, tracker_id)
    return [dict(r) for r in rows]


# -- Notes (append-only) --

async def add_note(
    conn: asyncpg.Connection, tracker_id: str, user_id: str, body: str
) -> dict[str, Any]:
    """Add an immutable note to a tracker."""
    note_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    await conn.execute(
        SQL_INSERT_NOTE,
        note_id, tracker_id, user_id, body, now, _LABELS_JSON,
    )
    await _log_audit(conn, tracker_id, "note_added", user_id, {"note_id": note_id})
    return {"id": note_id, "tracker_id": tracker_id, "user_id": user_id,
            "body": body, "created_at": now}


async def list_notes(
    conn: asyncpg.Connection, tracker_id: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_NOTES, tracker_id)
    return [dict(r) for r in rows]


# -- Signals --

async def link_signal(
    conn: asyncpg.Connection, tracker_id: str, signal_id: str, user_id: str
) -> None:
    now = datetime.now(UTC)
    await conn.execute(SQL_LINK_SIGNAL, tracker_id, signal_id, now, user_id)
    await _log_audit(conn, tracker_id, "signal_linked", user_id, {"signal_id": signal_id})


async def list_signals(
    conn: asyncpg.Connection, tracker_id: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_TRACKER_SIGNALS, tracker_id)
    return [dict(r) for r in rows]


# -- Audit log --

async def _log_audit(
    conn: asyncpg.Connection,
    tracker_id: str,
    action: str,
    actor_id: str,
    detail: dict[str, Any],
) -> None:
    """Append to tracker audit log."""
    import json
    await conn.execute(
        SQL_INSERT_AUDIT_LOG,
        str(uuid.uuid4()), tracker_id, action, actor_id,
        json.dumps(detail), datetime.now(UTC),
    )


async def list_audit_log(
    conn: asyncpg.Connection, tracker_id: str, limit: int = 100, offset: int = 0
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_AUDIT_LOG, tracker_id, limit, offset)
    return [dict(r) for r in rows]


# -- Access control --

async def verify_tracker_access(
    conn: asyncpg.Connection, tracker_id: str, user: dict
) -> None:
    """Raise 404 if tracker doesn't belong to user's org."""
    from ..auth.rbac import is_super_admin, get_user_org

    if is_super_admin(user):
        return
    row = await conn.fetchrow(SQL_GET_TRACKER_ORG, tracker_id)
    if not row or row["org_id"] != get_user_org(user):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Tracker not found")
