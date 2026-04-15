"""Report management endpoints — API gateway layer.

Implements direct asyncpg access (same pattern as topics.py).
PDF download is handled by the reporter service directly.

Routes:
  POST   /api/v1/reports
  GET    /api/v1/reports/{id}
  GET    /api/v1/topics/{id}/reports
  GET    /api/v1/reports/{id}/geojson
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, UTC
from typing import Optional

import asyncpg
import structlog
from arq.connections import RedisSettings
from arq import create_pool as arq_create_pool
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..auth.jwt import get_current_user
from ..db.pool import get_db
from ..db import reports as reports_db
from ..settings import settings

log = structlog.get_logger(__name__)

router = APIRouter(tags=["reports"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class GenerateReportRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    topic_id: str
    report_type: str = "intelligence_brief"
    # Explicit window takes precedence; time_window_hours is a convenience fallback
    time_window_start: Optional[datetime] = None
    time_window_end: Optional[datetime] = None
    time_window_hours: int = 72
    credibility_min: float = 30.0


# ---------------------------------------------------------------------------
# Route: POST /api/v1/reports
# ---------------------------------------------------------------------------

@router.post("/api/v1/reports", status_code=status.HTTP_202_ACCEPTED)
async def create_report(
    req: GenerateReportRequest,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    """Create a pending report row and enqueue the generation job.

    Returns {report_id, status, arq_job_id} in <100 ms.
    Poll GET /api/v1/reports/{report_id} until generation_status='complete'.
    """
    report_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    time_end = req.time_window_end or now
    time_start = req.time_window_start or (time_end - timedelta(hours=req.time_window_hours))
    labels = json.dumps(
        {"classification": "OPEN", "domain": "report", "owner_org": "anveshak"}
    )

    await reports_db.insert_report(
        db, report_id, req.topic_id, req.report_type,
        time_start, time_end, req.credibility_min, now, labels,
    )

    arq_job_id: Optional[str] = None
    try:
        arq_pool = await arq_create_pool(RedisSettings.from_dsn(settings.redis_url))
        job = await arq_pool.enqueue_job("generate_report", report_id)
        arq_job_id = job.job_id if job else None
        await arq_pool.close()
    except Exception as exc:
        log.warning(
            "reports.arq_enqueue_failed",
            report_id=report_id,
            error=str(exc),
        )

    log.info(
        "reports.report_queued",
        report_id=report_id,
        topic_id=req.topic_id,
        arq_job_id=arq_job_id,
    )
    return {"report_id": report_id, "status": "queued", "arq_job_id": arq_job_id}


# ---------------------------------------------------------------------------
# Route: GET /api/v1/reports/{report_id}
# ---------------------------------------------------------------------------

@router.get("/api/v1/reports/{report_id}")
async def get_report(
    report_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    """Return report metadata, generation status, and source warnings."""
    row = await reports_db.fetch_report(db, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    row["generation_status"] = "complete" if row.get("generated_at") else "queued"
    return row


# ---------------------------------------------------------------------------
# Route: GET /api/v1/topics/{topic_id}/reports
# ---------------------------------------------------------------------------

@router.get("/api/v1/topics/{topic_id}/reports")
async def list_topic_reports(
    topic_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> list[dict]:
    """Return all reports for a topic, newest first."""
    return await reports_db.list_topic_reports(db, topic_id)


# ---------------------------------------------------------------------------
# Route: GET /api/v1/reports/{report_id}/geojson
# ---------------------------------------------------------------------------

@router.get("/api/v1/reports/{report_id}/geojson")
async def get_report_geojson(
    report_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    """Return the GeoJSON FeatureCollection for a generated report."""
    row = await reports_db.get_report_geojson(db, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if row["generated_at"] is None:
        raise HTTPException(status_code=202, detail="Report not yet generated")
    geojson = row["geojson"] or {"type": "FeatureCollection", "features": []}
    return geojson
