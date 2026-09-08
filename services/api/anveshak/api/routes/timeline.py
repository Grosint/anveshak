"""Sentiment Timeline endpoint — issue #29.

Lives in the Intelligence View, which already answers "what is happening?".
"""

from __future__ import annotations

from typing import Any

import structlog
from anveshak.db import DBConnection
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.rbac import require_role
from ..db import timeline as timeline_db
from ..db import topics as topics_db
from ..db.pool import get_db

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/topics", tags=["timeline"])


@router.get("/{topic_id}/sentiment-timeline")
async def get_sentiment_timeline(
    topic_id: str,
    days: int = Query(90, ge=1, le=730),
    as_percentage: bool = Query(False),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin", "viewer")),
) -> dict[str, Any]:
    """Supporting and opposing volume over publication time, with hostility.

    Absolute volume by default. The percentage view is opt-in, so a volume
    explosion is never hidden by normalisation.
    """
    await topics_db.verify_topic_access(db, topic_id, user)

    org_row = await db.fetchrow(topics_db.SQL_GET_TOPIC_ORG, topic_id)
    if org_row is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return await timeline_db.get_timeline(
        db,
        topic_id,
        org_id=org_row["org_id"],
        days=days,
        as_percentage=as_percentage,
    )
