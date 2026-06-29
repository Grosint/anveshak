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
import os
import uuid
from datetime import datetime, timedelta, UTC
from typing import Optional

import asyncpg
import structlog
from arq.connections import RedisSettings
from arq import create_pool as arq_create_pool
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict

from ..auth.rbac import require_role
from ..db.pool import get_db
from ..db import reports as reports_db
from ..db import topics as topics_db
from ..db import audit as audit_db
from ..pagination import paginate_rows
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
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict:
    """Create a pending report row and enqueue the generation job.

    Returns {report_id, status, arq_job_id} in <100 ms.
    Poll GET /api/v1/reports/{report_id} until generation_status='complete'.
    """
    await topics_db.verify_topic_access(db, req.topic_id, user)
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
        job = await arq_pool.enqueue_job("generate_report", report_id, _queue_name="arq:reporter")
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
    await audit_db.log_action(
        db, user["sub"], "report.generate", "report", report_id,
        {"topic_id": req.topic_id, "report_type": req.report_type},
        request.client.host if request.client else "",
    )
    return {"report_id": report_id, "status": "queued", "arq_job_id": arq_job_id}


# ---------------------------------------------------------------------------
# Route: GET /api/v1/reports/{report_id}
# ---------------------------------------------------------------------------

@router.get("/api/v1/reports/{report_id}")
async def get_report(
    report_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict:
    """Return report metadata, generation status, and source warnings."""
    row = await reports_db.fetch_report(db, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    await topics_db.verify_topic_access(db, row["topic_id"], user)
    if row.get("generated_at"):
        row["generation_status"] = "complete"
    elif row.get("generation_error"):
        row["generation_status"] = "failed"
    else:
        row["generation_status"] = "queued"
    return row


# ---------------------------------------------------------------------------
# Route: GET /api/v1/topics/{topic_id}/reports
# ---------------------------------------------------------------------------

@router.get("/api/v1/topics/{topic_id}/reports")
async def list_topic_reports(
    topic_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict:
    """Return paginated reports for a topic, newest first."""
    await topics_db.verify_topic_access(db, topic_id, user)
    items, total = await reports_db.list_topic_reports(db, topic_id, limit, offset)
    return paginate_rows(items, total, offset, limit)


# ---------------------------------------------------------------------------
# Route: GET /api/v1/reports/{report_id}/geojson
# ---------------------------------------------------------------------------

@router.get("/api/v1/reports/{report_id}/geojson")
async def get_report_geojson(
    report_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict:
    """Return the GeoJSON FeatureCollection for a generated report."""
    row = await reports_db.get_report_geojson(db, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    await topics_db.verify_topic_access(db, row["topic_id"], user)
    if row["generated_at"] is None:
        raise HTTPException(status_code=202, detail="Report not yet generated")
    geojson = row["geojson"] or {"type": "FeatureCollection", "features": []}
    return geojson


# ---------------------------------------------------------------------------
# Route: GET /api/v1/reports/{report_id}/pdf
# ---------------------------------------------------------------------------

@router.get("/api/v1/reports/{report_id}/pdf")
async def get_report_pdf(
    report_id: str,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Download report as PDF.

    Serves pre-generated PDFs from the shared reporter_output volume.
    If report is still generating, returns 202 with Retry-After.
    If report is generated but PDF not yet created, enqueues a PDF generation
    job and returns 202.
    """
    row = await reports_db.fetch_report(db, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    await topics_db.verify_topic_access(db, row["topic_id"], user)

    if row.get("generated_at") is None:
        return Response(
            status_code=202,
            headers={"Retry-After": "30"},
            content="Report generation pending",
        )

    # Serve cached PDF — generated eagerly by report-worker at generation time
    pdf_path: Optional[str] = row.get("pdf_path")
    if pdf_path and os.path.exists(pdf_path):
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"report_{report_id}.pdf",
        )

    # PDF not on disk — report was generated but PDF failed or pre-dates eager generation.
    # Regenerate the report to get a PDF (analyst action).
    raise HTTPException(
        status_code=404,
        detail="PDF not available. The report was generated before PDF-at-generation was enabled. "
               "Generate a new report to get a PDF.",
    )
