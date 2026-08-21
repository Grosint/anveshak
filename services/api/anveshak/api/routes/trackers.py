"""Tracker endpoints — persistent analyst-owned case files."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, Optional

import structlog
from anveshak.db import DBConnection
from arq import create_pool as arq_create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict

from ..auth.rbac import get_user_org, require_org_context, require_role
from ..db import audit as audit_db
from ..db import reports as reports_db
from ..db import trackers as trackers_db
from ..db.pool import get_db
from ..pagination import paginate_rows
from ..settings import settings

router = APIRouter(prefix="/api/v1/trackers", tags=["trackers"])
log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateTrackerRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    title: str
    topic_id: str
    external_case_ref: Optional[str] = None
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    status: Literal["watching", "active"] = "watching"


class CreateFromClusterRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    external_case_ref: Optional[str] = None
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    status: Literal["watching", "active"] = "active"


class UpdateStatusRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    status: Literal["watching", "active", "concluded"]
    closing_summary: Optional[str] = None


class UpdatePriorityRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    priority: Literal["low", "medium", "high", "critical"]


class AssignRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    assigned_to: Optional[str] = None


class UpdateTrackerRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    title: Optional[str] = None
    external_case_ref: Optional[str] = None


class AddNoteRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    body: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_tracker(
    req: CreateTrackerRequest,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Create a new tracker from scratch."""
    org_id = get_user_org(user)
    tracker = await trackers_db.create_tracker(
        db,
        topic_id=req.topic_id,
        title=req.title,
        created_by=user["sub"],
        org_id=org_id,
        external_case_ref=req.external_case_ref,
        priority=req.priority,
        status=req.status,
    )
    await audit_db.log_action(
        db,
        user["sub"],
        "tracker.create",
        "tracker",
        tracker["id"],
        {"title": req.title},
        request.client.host if request.client else "",
    )
    log.info("tracker.created", tracker_id=tracker["id"], case_number=tracker.get("case_number"))
    return tracker


@router.post("/from-cluster/{cluster_id}", status_code=status.HTTP_201_CREATED)
async def create_from_cluster(
    cluster_id: str,
    req: CreateFromClusterRequest,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Create a tracker seeded from a narrative cluster."""
    org_id = get_user_org(user)
    try:
        tracker = await trackers_db.create_tracker_from_cluster(
            db,
            cluster_id,
            user["sub"],
            org_id=org_id,
            external_case_ref=req.external_case_ref,
            status=req.status,
            priority=req.priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await audit_db.log_action(
        db,
        user["sub"],
        "tracker.create_from_cluster",
        "tracker",
        tracker["id"],
        {"cluster_id": cluster_id},
        request.client.host if request.client else "",
    )
    log.info("tracker.created_from_cluster", tracker_id=tracker["id"], cluster_id=cluster_id)
    return tracker


@router.get("")
async def list_trackers(
    topic_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """List trackers for the user's org, optionally filtered by topic."""
    # Every branch below scopes by org, so None would silently list nothing.
    org_id = require_org_context(user)
    if status_filter:
        # Fetch all (no SQL pagination) then filter + paginate in Python
        if topic_id:
            all_items, _ = await trackers_db.list_trackers_by_topic(db, topic_id, org_id, 1000, 0)
        else:
            all_items, _ = await trackers_db.list_trackers_by_org(db, org_id, 1000, 0)
        filtered = [t for t in all_items if t["status"] == status_filter]
        total = len(filtered)
        items = filtered[offset : offset + limit]
    else:
        if topic_id:
            items, total = await trackers_db.list_trackers_by_topic(
                db, topic_id, org_id, limit, offset
            )
        else:
            items, total = await trackers_db.list_trackers_by_org(db, org_id, limit, offset)
    return paginate_rows(items, total, offset, limit)


@router.get("/{tracker_id}")
async def get_tracker(
    tracker_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Get tracker detail with content/pending counts."""
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    tracker = await trackers_db.get_tracker(db, tracker_id)
    if not tracker:
        raise HTTPException(status_code=404, detail="Tracker not found")
    return tracker


@router.patch("/{tracker_id}/status")
async def update_status(
    tracker_id: str,
    req: UpdateStatusRequest,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    if req.status == "concluded" and not req.closing_summary:
        raise HTTPException(status_code=422, detail="closing_summary required when concluding")
    await trackers_db.update_tracker_status(
        db,
        tracker_id,
        req.status,
        user["sub"],
        closing_summary=req.closing_summary,
    )
    await audit_db.log_action(
        db,
        user["sub"],
        "tracker.status_changed",
        "tracker",
        tracker_id,
        {"status": req.status},
        request.client.host if request.client else "",
    )
    return {"status": "ok"}


@router.patch("/{tracker_id}/priority")
async def update_priority(
    tracker_id: str,
    req: UpdatePriorityRequest,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    await trackers_db.update_tracker_priority(db, tracker_id, req.priority, user["sub"])
    return {"status": "ok"}


@router.patch("/{tracker_id}/assign")
async def assign_tracker(
    tracker_id: str,
    req: AssignRequest,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    await trackers_db.update_tracker_assignment(db, tracker_id, req.assigned_to, user["sub"])
    return {"status": "ok"}


@router.patch("/{tracker_id}")
async def update_tracker(
    tracker_id: str,
    req: UpdateTrackerRequest,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    tracker = await trackers_db.get_tracker(db, tracker_id)
    if not tracker:
        raise HTTPException(status_code=404, detail="Tracker not found")
    now = datetime.now(UTC)
    title = req.title or tracker["title"]
    ext_ref = (
        req.external_case_ref
        if req.external_case_ref is not None
        else tracker.get("external_case_ref")
    )
    await db.execute(trackers_db.SQL_UPDATE_TRACKER_DETAILS, title, ext_ref, now, tracker_id)
    changes: dict = {}
    if req.title is not None:
        changes["title"] = req.title
    if req.external_case_ref is not None:
        changes["external_case_ref"] = req.external_case_ref
    await audit_db.log_action(
        db,
        user["sub"],
        "tracker.updated",
        "tracker",
        tracker_id,
        changes,
        request.client.host if request.client else "",
    )
    await trackers_db._log_audit(db, tracker_id, "updated", user["sub"], changes)
    return {"status": "ok"}


# -- Content --


@router.get("/{tracker_id}/content")
async def list_content(
    tracker_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    return await trackers_db.list_content(db, tracker_id, limit, offset)


@router.get("/{tracker_id}/pending")
async def list_pending(
    tracker_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    return await trackers_db.list_pending(db, tracker_id)


@router.post("/{tracker_id}/content/{item_id}/confirm")
async def confirm_item(
    tracker_id: str,
    item_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    await trackers_db.confirm_content(db, tracker_id, item_id, user["sub"])
    return {"status": "ok"}


@router.post("/{tracker_id}/content/{item_id}/reject")
async def reject_item(
    tracker_id: str,
    item_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    await trackers_db.reject_content(db, tracker_id, item_id, user["sub"])
    return {"status": "ok"}


@router.post("/{tracker_id}/content/confirm-all")
async def confirm_all(
    tracker_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    await trackers_db.confirm_all_pending(db, tracker_id, user["sub"])
    return {"status": "ok"}


@router.post("/{tracker_id}/content/{item_id}")
async def add_content_manually(
    tracker_id: str,
    item_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    await trackers_db.add_content(db, tracker_id, item_id, "manual", user["sub"])
    return {"status": "ok"}


@router.delete("/{tracker_id}/content/{item_id}")
async def remove_content(
    tracker_id: str,
    item_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Soft remove: moves to exclusion list."""
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    await trackers_db.reject_content(db, tracker_id, item_id, user["sub"])
    return {"status": "ok"}


# -- Notes --


@router.post("/{tracker_id}/notes")
async def add_note(
    tracker_id: str,
    req: AddNoteRequest,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    note = await trackers_db.add_note(db, tracker_id, user["sub"], req.body)
    return note


@router.get("/{tracker_id}/notes")
async def list_notes(
    tracker_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    return await trackers_db.list_notes(db, tracker_id)


# -- Signals --


@router.get("/{tracker_id}/signals")
async def list_signals(
    tracker_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    return await trackers_db.list_signals(db, tracker_id)


@router.post("/{tracker_id}/signals/{signal_id}")
async def link_signal(
    tracker_id: str,
    signal_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    await trackers_db.link_signal(db, tracker_id, signal_id, user["sub"])
    return {"status": "ok"}


# -- Reports --


class GenerateTrackerReportRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    report_type: Literal["intelligence_brief", "research_summary", "weekly_digest"] = (
        "intelligence_brief"
    )
    time_window_hours: int = 72
    credibility_min: float = 30.0


@router.get("/{tracker_id}/reports")
async def list_tracker_reports(
    tracker_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    return await trackers_db.list_tracker_reports(db, tracker_id)


@router.post("/{tracker_id}/reports", status_code=status.HTTP_201_CREATED)
async def generate_tracker_report(
    tracker_id: str,
    req: GenerateTrackerReportRequest,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Generate a report scoped to this tracker's confirmed content."""
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    tracker = await trackers_db.get_tracker(db, tracker_id)
    if not tracker:
        raise HTTPException(status_code=404, detail="Tracker not found")

    report_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    time_start = now - timedelta(hours=req.time_window_hours)
    labels_json = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'

    await reports_db.insert_report(
        db,
        report_id,
        tracker["topic_id"],
        req.report_type,
        time_start,
        now,
        req.credibility_min,
        now,
        labels_json,
        tracker_id=tracker_id,
    )

    # Enqueue ARQ job
    try:
        redis = await arq_create_pool(RedisSettings.from_dsn(settings.redis_url))
        arq_job = await redis.enqueue_job("generate_report", report_id, _queue_name="arq:reporter")
        arq_job_id = arq_job.job_id if arq_job else None
    except Exception as exc:
        log.warning("tracker.report_enqueue_failed", tracker_id=tracker_id, error=str(exc))
        arq_job_id = None

    await audit_db.log_action(
        db,
        user["sub"],
        "tracker.report_generated",
        "tracker",
        tracker_id,
        {"report_id": report_id, "report_type": req.report_type},
        request.client.host if request.client else "",
    )
    return {"report_id": report_id, "status": "queued", "arq_job_id": arq_job_id}


# -- Audit log --


@router.get("/{tracker_id}/audit-log")
async def get_audit_log(
    tracker_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await trackers_db.verify_tracker_access(db, tracker_id, user)
    return await trackers_db.list_audit_log(db, tracker_id, limit, offset)
