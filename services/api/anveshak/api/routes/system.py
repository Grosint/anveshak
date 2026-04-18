"""System endpoints — pipeline health metrics."""
from __future__ import annotations

import asyncpg
import structlog
from fastapi import APIRouter, Depends

from ..auth.jwt import get_current_user
from ..db import system as system_db
from ..db.pool import get_db

router = APIRouter(prefix="/api/v1/system", tags=["system"])
log = structlog.get_logger(__name__)


@router.get("/pipeline-health")
async def pipeline_health(
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
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
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return vector pipeline health metrics for validation.

    Read-only schema and data checks for migrations 002–006.
    Used by `make validate-vector` (scripts/validate_vector.py).
    """
    metrics = await system_db.get_vector_health(db)
    log.info("system.vector_health_queried", user=user.get("sub"))
    return metrics
