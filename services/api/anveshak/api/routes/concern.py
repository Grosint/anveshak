"""Concern taxonomy facet — issue #36, ADR 0001.

Two endpoints, both read-only.

The taxonomy endpoint exists so the interface can offer the analyst the
categories to choose from. It is fetched when the analyst opens the filter,
never volunteered: the system does not tell an analyst what to be concerned
about.

The filter endpoint returns narratives carrying a chosen category, in the
order the underlying query produced. Nothing here sorts by a concern score,
and there is deliberately no endpoint that would.
"""

from __future__ import annotations

from typing import Any

import structlog
from anveshak.db import DBConnection
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.rbac import require_role
from ..db import concern as concern_db
from ..db import topics as topics_db
from ..db.pool import get_db

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["concern"])


@router.get("/concern-taxonomy")
async def get_taxonomy(
    user: dict = Depends(require_role("analyst", "admin", "viewer")),
) -> dict[str, Any]:
    """The versioned taxonomy the customer owns.

    Returned on request so the analyst can pick a filter. The system never
    pushes a category at them.
    """
    return concern_db.taxonomy_payload()


@router.get("/topics/{topic_id}/clusters/by-concern")
async def list_clusters_by_concern(
    topic_id: str,
    categories: list[str] = Query(default=[]),
    limit: int = Query(200, ge=1, le=500),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin", "viewer")),
) -> list[dict[str, Any]]:
    """Narrative clusters, filtered by concern category.

    The order is independent source count then item count, exactly as an
    unfiltered list would be. Applying a filter changes membership and never
    ordering. See ADR 0001.
    """
    await topics_db.verify_topic_access(db, topic_id, user)

    org_row = await db.fetchrow(topics_db.SQL_GET_TOPIC_ORG, topic_id)
    if org_row is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return await concern_db.list_clusters_by_concern(
        db, topic_id, org_id=org_row["org_id"], categories=categories, limit=limit
    )
