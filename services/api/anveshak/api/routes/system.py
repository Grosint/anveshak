"""System endpoints — pipeline health, audit trail, failed jobs."""

from __future__ import annotations

from typing import Optional

import structlog
from anveshak.db import DBConnection
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.rbac import require_role
from ..db import analytics as analytics_db
from ..db import audit as audit_db
from ..db import failed_jobs as failed_jobs_db
from ..db import system as system_db
from ..db import topics as topics_db
from ..db.pool import get_db
from ..pagination import paginate_rows

router = APIRouter(prefix="/api/v1/system", tags=["system"])
log = structlog.get_logger(__name__)


@router.get("/pipeline-health")
async def pipeline_health(
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Return live pipeline metrics for validation and monitoring.

    All counts are computed at query time from the live database — no caching.
    Used by `make validate` (scripts/validate_pipeline.py) and Grafana dashboards.
    """
    metrics = await system_db.get_pipeline_metrics(db)
    log.info("system.pipeline_health_queried", user=user.get("sub"))
    return metrics


@router.get("/vector-health")
async def vector_health(
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Return vector pipeline health metrics for validation.

    Read-only schema and data checks for migrations 002–006.
    Used by `make validate-vector` (scripts/validate_vector.py).
    """
    metrics = await system_db.get_vector_health(db)
    log.info("system.vector_health_queried", user=user.get("sub"))
    return metrics


@router.get("/audit-trail")
async def get_audit_trail(
    resource_type: Optional[str] = Query(
        None, description="Filter by resource type (omit for all)"
    ),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0, description="Offset for cursor-based pagination"),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Return audit trail entries. Analysts must provide resource_id (scoped to their org)."""
    user_role = user.get("role", "")
    if user_role == "analyst":
        if not resource_id:
            raise HTTPException(status_code=403, detail="Analysts must filter by resource_id")
        await topics_db.verify_topic_access(db, resource_id, user)
    items, total = await audit_db.get_audit_trail(db, resource_type, resource_id, limit, offset)
    return paginate_rows(items, total, offset, limit)


@router.get("/analytics-dashboard")
async def analytics_dashboard(
    days: int = Query(30, ge=1, le=365),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Cross-topic aggregate analytics for the intelligence dashboard, org-scoped."""
    org_id = user.get("org_id", "")
    data = await analytics_db.get_dashboard_data(db, days, org_id=org_id)
    log.info("system.analytics_dashboard_queried", user=user.get("sub"), days=days, org_id=org_id)
    return data


@router.get("/failed-jobs")
async def get_failed_jobs(
    queue_name: Optional[str] = Query(None, description="Filter by ARQ queue"),
    limit: int = Query(100, ge=1, le=1000),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Return dead-letter queue entries (admin only)."""
    return await failed_jobs_db.list_failed_jobs(db, queue_name, limit)
