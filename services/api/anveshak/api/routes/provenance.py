"""Provenance API endpoints — aggregated intelligence + provenance chains.

Issue #7: Single-call endpoints for the Intelligence View and Provenance Panel.
"""

from __future__ import annotations

import structlog
from anveshak.db import DBConnection
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.rbac import require_org_context, require_role
from ..db import provenance as provenance_db
from ..db import topics as topics_db
from ..db.pool import get_db, require_pool

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["provenance"])


@router.get("/topics/{topic_id}/intelligence")
async def get_topic_intelligence(
    topic_id: str,
    cluster_limit: int = Query(10, ge=1, le=50),
    identifier_limit: int = Query(15, ge=1, le=50),
    location_limit: int = Query(20, ge=1, le=100),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
):
    """Aggregated intelligence overview for the Intelligence View.

    Returns signals, top clusters, top identifiers, location pills,
    source health strip, and quick stats in a single call.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    pool = require_pool()
    return await provenance_db.get_topic_intelligence(
        pool,
        topic_id,
        cluster_limit=cluster_limit,
        identifier_limit=identifier_limit,
        location_limit=location_limit,
    )


@router.get("/identifiers/{identifier_value}/provenance")
async def get_identifier_provenance(
    identifier_value: str,
    topic_id: str = Query(..., description="Topic to scope the provenance chain"),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Full provenance chain for one identifier.

    Returns content items, sources, clusters, signals, and
    cross-topic appearances for the given identifier value.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    # Not get_user_org: org_id scopes the cross-topic query, and None would
    # silently return an empty chain instead of reporting a broken token.
    org_id = require_org_context(user)
    pool = require_pool()
    return await provenance_db.get_identifier_provenance(
        pool,
        identifier_value,
        topic_id,
        org_id,
    )


@router.get("/clusters/{cluster_id}/provenance")
async def get_cluster_provenance(
    cluster_id: str,
    topic_id: str = Query(..., description="Topic to scope the cluster"),
    content_limit: int = Query(30, ge=1, le=100),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Enriched provenance for one narrative cluster.

    Returns cluster header, signal link, content timeline,
    ranked identifiers, and source spread.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    pool = require_pool()
    result = await provenance_db.get_cluster_provenance(
        pool,
        cluster_id,
        topic_id,
        content_limit=content_limit,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return result


@router.get("/clusters/{cluster_id}/flow")
async def get_cluster_flow(
    cluster_id: str,
    topic_id: str = Query(..., description="Topic to scope the cluster"),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Information flow graph for one cluster.

    Returns source nodes with temporal ordering and edges
    showing information propagation direction.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    pool = require_pool()
    return await provenance_db.get_cluster_flow(pool, cluster_id, topic_id)


@router.get("/content/{content_id}/provenance")
async def get_content_provenance(
    content_id: str,
    db: DBConnection = Depends(get_db),
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
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
):
    """Urgency metrics for dashboard topic card sorting.

    Returns unacknowledged signal count, new content in last 24h,
    and worst source health status.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    return await provenance_db.get_topic_urgency(db, topic_id)
