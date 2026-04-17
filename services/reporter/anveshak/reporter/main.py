"""Anveshak Reporter Service — M5: LLM report generation, GIS output, PDF export."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, UTC
from typing import Optional

import structlog
from arq import create_pool as arq_create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from prometheus_client import make_asgi_app
from pydantic import BaseModel, ConfigDict

from .metrics import REGISTRY as REPORTER_REGISTRY

from . import db as db_module
from .pdf import generate_pdf
from .rag import get_embedding_model
from .settings import settings

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: pre-warm embedding model, create DB pool and ARQ pool."""
    log.info("reporter.starting")

    app.state.db_pool = await db_module.get_pool(settings.postgres_url)
    app.state.arq_pool = await arq_create_pool(
        RedisSettings.from_dsn(settings.redis_url)
    )

    # Pre-warm embedding model to avoid cold-start during first report request
    try:
        get_embedding_model(settings.embedding_model)
        log.info("reporter.embedding_model_warmed", model=settings.embedding_model)
    except Exception as exc:
        log.warning("reporter.embedding_warmup_failed", error=str(exc))

    log.info("reporter.ready")
    yield

    # Shutdown
    await app.state.arq_pool.close()
    await app.state.db_pool.close()
    log.info("reporter.stopped")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Anveshak Reporter Service",
    version="1.0.0",
    lifespan=lifespan,
)

# 8A.17 — Prometheus metrics endpoint (uses service-isolated registry, 8A.18)
app.mount("/metrics", make_asgi_app(registry=REPORTER_REGISTRY))


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class GenerateReportRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    topic_id: str
    report_type: str = "intelligence_brief"  # intelligence_brief|research_summary|weekly_digest
    # Explicit window takes precedence; time_window_hours is a convenience fallback
    time_window_start: Optional[datetime] = None
    time_window_end: Optional[datetime] = None
    time_window_hours: int = 72
    credibility_min: float = 30.0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "anveshak-reporter",
        "report_model": settings.ollama_model,
    }


@app.post("/api/v1/reports")
async def create_report(req: GenerateReportRequest) -> dict:
    """Create a report row and dispatch ARQ job. Returns in <100 ms.

    The report is generated asynchronously — poll GET /api/v1/reports/{id}
    until generated_at is set.
    """
    report_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    time_end = req.time_window_end or now
    time_start = req.time_window_start or (time_end - timedelta(hours=req.time_window_hours))

    await db_module.create_report_row(
        app.state.db_pool,
        report_id=report_id,
        topic_id=req.topic_id,
        report_type=req.report_type,
        time_window_start=time_start,
        time_window_end=time_end,
        credibility_min=req.credibility_min,
    )

    arq_job = await app.state.arq_pool.enqueue_job("generate_report", report_id)
    arq_job_id = arq_job.job_id if arq_job else None

    log.info(
        "reporter.report_queued",
        report_id=report_id,
        topic_id=req.topic_id,
        arq_job_id=arq_job_id,
    )
    return {"report_id": report_id, "status": "queued", "arq_job_id": arq_job_id}


@app.get("/api/v1/reports/{report_id}")
async def get_report(report_id: str) -> dict:
    """Return report metadata, generation status, and any source warnings."""
    report = await db_module.fetch_report(app.state.db_pool, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    generation_status = "complete" if report.get("generated_at") else "queued"
    result = dict(report)
    result["generation_status"] = generation_status
    return result


@app.get("/api/v1/topics/{topic_id}/reports")
async def list_topic_reports(topic_id: str) -> list[dict]:
    """Return all reports for a topic, newest first."""
    rows = await db_module.list_topic_reports(app.state.db_pool, topic_id)
    return rows


@app.get("/api/v1/reports/{report_id}/geojson")
async def get_report_geojson(report_id: str) -> dict:
    """Return the GeoJSON FeatureCollection for a generated report."""
    report = await db_module.fetch_report(app.state.db_pool, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.get("generated_at") is None:
        raise HTTPException(status_code=202, detail="Report not yet generated")
    geojson = report.get("geojson") or {"type": "FeatureCollection", "features": []}
    return geojson


@app.get("/api/v1/reports/{report_id}/pdf")
async def get_report_pdf(report_id: str) -> FileResponse:
    """Download report as PDF.

    If PDF is already cached (pdf_path set), serve it immediately.
    If not, generate on-demand and return.
    Returns HTTP 202 with Retry-After header while still pending.
    """
    from fastapi.responses import Response

    report = await db_module.fetch_report(app.state.db_pool, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    if report.get("generated_at") is None:
        return Response(
            status_code=202,
            headers={"Retry-After": "30"},
            content="Report generation pending",
        )

    # Check for cached PDF
    existing_path: Optional[str] = report.get("pdf_path")
    if existing_path:
        import os
        if os.path.exists(existing_path):
            return FileResponse(
                existing_path,
                media_type="application/pdf",
                filename=f"report_{report_id}.pdf",
            )

    # Generate PDF on demand
    report_data = {
        "id": report_id,
        "report_type": report.get("report_type", "intelligence_brief"),
        "topic_name": report.get("topic_name", "Intelligence Report"),
        "generated_at": str(report.get("generated_at", "")),
        "confidence_score": report.get("confidence_score", 0.0),
        "content_item_count": report.get("content_item_count", 0),
        "labels": report.get("labels") or {},
    }

    # Parse content_md for key fields if available
    _enrich_report_data_from_md(report_data, report.get("content_md"))

    pdf_path = await generate_pdf(report_id, report_data, settings.pdf_output_dir)

    # Store path for future cache hits
    async with app.state.db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE reports SET pdf_path = $1, updated_at = NOW() WHERE id = $2",
            pdf_path,
            report_id,
        )

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"report_{report_id}.pdf",
    )


def _enrich_report_data_from_md(report_data: dict, content_md: Optional[str]) -> None:
    """Best-effort parse of content_md into structured fields for PDF template."""
    if not content_md:
        report_data.setdefault("executive_summary", "")
        report_data.setdefault("key_findings", [])
        report_data.setdefault("recommendations", [])
        report_data.setdefault("source_citations", [])
        return

    lines = content_md.split("\n")
    current_section = None
    summary_lines: list[str] = []
    findings: list[str] = []
    recs: list[str] = []
    citations: list[str] = []

    for line in lines:
        stripped = line.strip()
        if "Executive Summary" in stripped:
            current_section = "summary"
        elif "Key Findings" in stripped:
            current_section = "findings"
        elif "Recommendations" in stripped:
            current_section = "recommendations"
        elif "Source Citations" in stripped:
            current_section = "citations"
        elif stripped.startswith("- "):
            item = stripped[2:]
            if current_section == "findings":
                findings.append(item)
            elif current_section == "recommendations":
                recs.append(item)
            elif current_section == "citations":
                citations.append(item)
        elif stripped and current_section == "summary":
            summary_lines.append(stripped)

    report_data["executive_summary"] = " ".join(summary_lines)
    report_data["key_findings"] = findings
    report_data["recommendations"] = recs
    report_data["source_citations"] = citations


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)  # nosec B104 — containerized service must bind all interfaces; network isolation enforced by Docker/k3s
