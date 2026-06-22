"""Source Assessment endpoints — topic-scoped source intelligence cards.

Routes:
  POST  /api/v1/topics/{tid}/sources/{sid}/assessment
  GET   /api/v1/topics/{tid}/sources/{sid}/assessments
  GET   /api/v1/topics/{tid}/sources/{sid}/assessments/{aid}
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, UTC
from typing import Optional

import asyncpg
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from ..auth.rbac import require_role
from ..db.pool import get_db
from ..db import assessments as assessments_db
from ..db import sources as sources_db
from ..db import topics as topics_db
from ..db import audit as audit_db
from ..settings import settings

log = structlog.get_logger(__name__)

router = APIRouter(tags=["assessments"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateAssessmentRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    time_window_start: Optional[datetime] = None
    time_window_end: Optional[datetime] = None
    time_window_days: int = 30


# ---------------------------------------------------------------------------
# Route: POST /api/v1/topics/{tid}/sources/{sid}/assessment
# ---------------------------------------------------------------------------

@router.post(
    "/api/v1/topics/{topic_id}/sources/{source_id}/assessment",
    status_code=status.HTTP_200_OK,
)
async def create_assessment(
    topic_id: str,
    source_id: str,
    req: CreateAssessmentRequest = CreateAssessmentRequest(),
    *,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict:
    """Compute deterministic source stats and return assessment.

    Phase 0: synchronous — pure SQL aggregation, no LLM.
    Returns immediately with stats.
    """
    # 1. Access control
    await topics_db.verify_topic_access(db, topic_id, user)
    await sources_db.verify_source_access(db, source_id, user)

    # 2. Verify source linked to topic
    linked = await sources_db.topic_source_exists(db, topic_id, source_id)
    if not linked:
        raise HTTPException(
            status_code=400,
            detail="Source is not linked to this topic",
        )

    # 3. Compute time window
    now = datetime.now(UTC)
    time_end = req.time_window_end or now
    time_start = req.time_window_start or (time_end - timedelta(days=req.time_window_days))

    # 4. Check minimum content
    content_count = await assessments_db.count_source_content(
        db, topic_id, source_id, time_start, time_end,
    )
    if content_count < 5:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient data — only {content_count} items found (minimum 5 required)",
        )

    # 5. Get user org
    from ..auth.rbac import get_user_org
    org_id = get_user_org(user)

    # 6. Compute stats
    stats = await assessments_db.compute_source_stats(
        db,
        topic_id=topic_id,
        source_id=source_id,
        org_id=org_id,
        time_start=time_start,
        time_end=time_end,
    )

    # 7. Source snapshot
    snapshot = await assessments_db.get_source_snapshot(db, source_id)

    # 8. Insert assessment row
    assessment_id = str(uuid.uuid4())
    labels = json.dumps({
        "classification": "OPEN",
        "domain": "assessment",
        "owner_org": "anveshak",
    })

    await assessments_db.insert_assessment(
        db,
        assessment_id=assessment_id,
        topic_id=topic_id,
        source_id=source_id,
        org_id=org_id,
        time_window_start=time_start,
        time_window_end=time_end,
        stats_json=json.dumps(stats, default=str),
        content_item_count=content_count,
        source_snapshot_json=json.dumps(snapshot, default=str),
        now=now,
        labels_json=labels,
    )

    # 9. Enqueue platform metadata fetch (async, fail-open)
    try:
        from arq.connections import RedisSettings
        from arq import create_pool as arq_create_pool
        # Get source platform + handle for adapter lookup
        source_row = await db.fetchrow(
            "SELECT platform, url_or_handle FROM sources WHERE id = $1", source_id
        )
        if source_row:
            arq_pool = await arq_create_pool(RedisSettings.from_dsn(settings.redis_url))
            await arq_pool.enqueue_job(
                "fetch_source_metadata",
                source_row["platform"],
                source_row["url_or_handle"],
                assessment_id,
                _queue_name="arq:queue",  # social worker uses default queue
            )
            await arq_pool.close()
    except Exception as exc:
        log.info("assessment.metadata_enqueue_skipped", error=str(exc))

    # 10. Audit log
    await audit_db.log_action(
        db, user["sub"], "assessment.create", "source_assessment", assessment_id,
        {"topic_id": topic_id, "source_id": source_id},
        request.client.host if request.client else "",
    )

    log.info(
        "assessment.created",
        assessment_id=assessment_id,
        topic_id=topic_id,
        source_id=source_id,
        content_count=content_count,
    )

    return {
        "id": assessment_id,
        "topic_id": topic_id,
        "source_id": source_id,
        "time_window_start": time_start.isoformat(),
        "time_window_end": time_end.isoformat(),
        "content_item_count": content_count,
        "stats": stats,
        "source_snapshot": snapshot,
        "platform_metadata": None,
        "brief_md": None,
        "confidence_score": None,
        "generated_at": None,  # NULL until LLM brief is generated (CLAUDE.md rule 4)
        "generation_status": "stats_only",
        "created_at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# Route: POST /api/v1/topics/{tid}/sources/{sid}/assessments/{aid}/brief
# ---------------------------------------------------------------------------

@router.post(
    "/api/v1/topics/{topic_id}/sources/{source_id}/assessments/{assessment_id}/brief",
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_assessment_brief(
    topic_id: str,
    source_id: str,
    assessment_id: str,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict:
    """Enqueue LLM brief generation for an existing assessment.

    Returns 202 ACCEPTED. Poll GET .../assessments/{aid} for generation_status.
    """
    await topics_db.verify_topic_access(db, topic_id, user)

    # Verify assessment exists
    row = await assessments_db.fetch_assessment(db, assessment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Check if brief already generated
    if row.get("brief_md") is not None:
        raise HTTPException(status_code=409, detail="Brief already generated")

    # Enqueue ARQ job
    arq_job_id: Optional[str] = None
    try:
        from arq.connections import RedisSettings
        from arq import create_pool as arq_create_pool
        arq_pool = await arq_create_pool(RedisSettings.from_dsn(settings.redis_url))
        job = await arq_pool.enqueue_job(
            "generate_source_assessment",
            assessment_id,
            _queue_name="arq:reporter",
        )
        arq_job_id = job.job_id if job else None
        await arq_pool.close()

        # Store job ID
        await db.execute(
            "UPDATE source_assessments SET arq_job_id = $1 WHERE id = $2",
            arq_job_id, assessment_id,
        )
    except Exception as exc:
        log.warning("assessment.brief_enqueue_failed", error=str(exc))

    await audit_db.log_action(
        db, user["sub"], "assessment.generate_brief", "source_assessment", assessment_id,
        {"topic_id": topic_id, "source_id": source_id},
        request.client.host if request.client else "",
    )

    return {
        "assessment_id": assessment_id,
        "status": "queued",
        "arq_job_id": arq_job_id,
    }


# ---------------------------------------------------------------------------
# Route: GET /api/v1/topics/{tid}/sources/{sid}/assessments
# ---------------------------------------------------------------------------

@router.get("/api/v1/topics/{topic_id}/sources/{source_id}/assessments")
async def list_assessments(
    topic_id: str,
    source_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> list[dict]:
    """List all assessments for a source in a topic, newest first."""
    await topics_db.verify_topic_access(db, topic_id, user)
    return await assessments_db.list_assessments(db, topic_id, source_id)


# ---------------------------------------------------------------------------
# Route: GET /api/v1/topics/{tid}/sources/{sid}/assessments/{aid}
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/topics/{topic_id}/sources/{source_id}/assessments/{assessment_id}"
)
async def get_assessment(
    topic_id: str,
    source_id: str,
    assessment_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict:
    """Get a single assessment by ID."""
    await topics_db.verify_topic_access(db, topic_id, user)
    row = await assessments_db.fetch_assessment(db, assessment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    # Parse JSONB fields
    if isinstance(row.get("stats"), str):
        row["stats"] = json.loads(row["stats"])
    if isinstance(row.get("source_snapshot"), str):
        row["source_snapshot"] = json.loads(row["source_snapshot"])
    if isinstance(row.get("platform_metadata"), str):
        row["platform_metadata"] = json.loads(row["platform_metadata"])
    if isinstance(row.get("labels"), str):
        row["labels"] = json.loads(row["labels"])
    # Generation status
    if row.get("generated_at"):
        row["generation_status"] = "complete"
    elif row.get("generation_error"):
        row["generation_status"] = "failed"
    elif row.get("arq_job_id"):
        row["generation_status"] = "queued"
    else:
        row["generation_status"] = "stats_only"
    return row
