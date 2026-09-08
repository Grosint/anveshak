"""Actor View — issue #35.

Public content authored by one handle within one Topic, reached from any
handle in the Provenance Panel so an investigation trail stays continuous.

This is a query, never a stored entity. No actor table exists and no
persistent per-person record is created; a handle is an Identifier and
everything below is derived from content_items on demand. That is a
retention posture rather than an implementation detail, so nothing here may
grow a write path.
"""

from __future__ import annotations

from typing import Any

import structlog
from anveshak.db import DBConnection
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.rbac import require_role
from ..db import actors as actors_db
from ..db import topics as topics_db
from ..db.pool import get_db

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/topics", tags=["actors"])


@router.get("/{topic_id}/actors/{handle}")
async def get_actor(
    topic_id: str,
    handle: str,
    days: int = Query(90, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin", "viewer")),
) -> dict[str, Any]:
    """Return one handle's public content, activity and engagement in a topic.

    Organisation isolation runs twice: verify_topic_access() rejects a topic
    outside the caller's organisation, and every query carries org_id as
    well, because a handle is addressable by name rather than by an opaque
    identifier.
    """
    await topics_db.verify_topic_access(db, topic_id, user)

    # Scope on the topic's own organisation. verify_topic_access has already
    # established the caller may see this topic, and a super-admin carries no
    # org_id of their own, so reading it from the topic keeps the second
    # isolation layer intact for both cases.
    org_row = await db.fetchrow(topics_db.SQL_GET_TOPIC_ORG, topic_id)
    if org_row is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    org_id: str = org_row["org_id"]

    summary = await actors_db.get_actor_summary(db, topic_id, handle, org_id=org_id)
    content = await actors_db.list_actor_content(
        db, topic_id, handle, org_id=org_id, limit=limit, offset=offset
    )
    activity = await actors_db.get_actor_activity(db, topic_id, handle, org_id=org_id, days=days)

    return {
        "handle": actors_db.normalise_handle(handle),
        "topic_id": topic_id,
        "summary": summary,
        "content": content,
        "activity": activity,
    }
