"""Provenance API endpoints — aggregated intelligence + provenance chains.

Issue #7: Single-call endpoints for the Intelligence View and Provenance Panel.
"""
from __future__ import annotations

import asyncpg
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.rbac import require_role, get_user_org
from ..db.pool import get_db
from ..db import provenance as provenance_db
from ..db import topics as topics_db

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["provenance"])


@router.get("/topics/{topic_id}/intelligence")
async def get_topic_intelligence(
    topic_id: str,
    cluster_limit: int = Query(10, ge=1, le=50),
    identifier_limit: int = Query(15, ge=1, le=50),
    location_limit: int = Query(20, ge=1, le=100),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
):
    """Aggregated intelligence overview for the Intelligence View.

    Returns signals, top clusters, top identifiers, location pills,
    source health strip, and quick stats in a single call.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    return await provenance_db.get_topic_intelligence(
        db, topic_id,
        cluster_limit=cluster_limit,
        identifier_limit=identifier_limit,
        location_limit=location_limit,
    )


@router.get("/identifiers/{identifier_value}/provenance")
async def get_identifier_provenance(
    identifier_value: str,
    topic_id: str = Query(..., description="Topic to scope the provenance chain"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Full provenance chain for one identifier.

    Returns content items, sources, clusters, signals, and
    cross-topic appearances for the given identifier value.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    org_id = get_user_org(user)
    return await provenance_db.get_identifier_provenance(
        db, identifier_value, topic_id, org_id,
    )


@router.get("/content/{content_id}/provenance")
async def get_content_provenance(
    content_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Full provenance chain for one content item.

    Returns source, cluster membership, extracted identifiers,
    and vision results (if media attached).
    """
    result = await provenance_db.get_content_provenance(db, content_id)
    if not result:
        raise HTTPException(status_code=404, detail="Content item not found")
    await topics_db.verify_topic_access(db, result["topic_id"], user)
    return result


@router.get("/topics/{topic_id}/urgency")
async def get_topic_urgency(
    topic_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
):
    """Urgency metrics for dashboard topic card sorting.

    Returns unacknowledged signal count, new content in last 24h,
    and worst source health status.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    return await provenance_db.get_topic_urgency(db, topic_id)
