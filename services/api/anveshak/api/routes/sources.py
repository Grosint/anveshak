"""Source management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
import asyncpg
import uuid
from datetime import datetime, UTC
from ..db.pool import get_db
from ..db import sources as sources_db
from ..auth.jwt import get_current_user

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])

_LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


class CreateSourceRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str
    url_or_handle: str
    platform: str  # web|telegram|twitter|reddit|bluesky|rss|upload
    credibility_score: float = 50.0


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_source(
    req: CreateSourceRequest,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    source_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    await sources_db.insert_source(
        db, source_id, req.name, req.url_or_handle, req.platform,
        req.credibility_score, now, _LABELS_JSON,
    )
    return {"id": source_id, "name": req.name}


@router.get("")
async def list_sources(
    credibility_below: float | None = None,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if credibility_below is not None:
        return await sources_db.list_sources_below(db, credibility_below)
    return await sources_db.list_sources(db)


@router.patch("/{source_id}/credibility")
async def update_credibility(
    source_id: str,
    new_score: float,
    reason: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Update source credibility — always audit-logged."""
    old_score = await sources_db.get_source_score(db, source_id)
    if old_score is None:
        raise HTTPException(status_code=404, detail="Source not found")

    now = datetime.now(UTC)
    async with db.transaction():
        await sources_db.update_credibility(
            db, source_id, str(uuid.uuid4()),
            old_score, new_score, reason,
            f"user:{user['sub']}", now, _LABELS_JSON,
        )
    return {"source_id": source_id, "old_score": old_score, "new_score": new_score}


@router.patch("/{source_id}/active")
async def toggle_source_active(
    source_id: str,
    is_active: bool,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if not await sources_db.source_exists(db, source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    await sources_db.toggle_source_active(db, source_id, is_active, datetime.now(UTC))
    return {"source_id": source_id, "is_active": is_active}


@router.get("/{source_id}/report-warnings/count")
async def get_report_warnings_count(
    source_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if not await sources_db.source_exists(db, source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    count = await sources_db.count_report_warnings(db, source_id)
    return {"source_id": source_id, "warning_count": count}


@router.get("/{source_id}/audit-log")
async def get_audit_log(
    source_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if not await sources_db.source_exists(db, source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    return await sources_db.get_audit_log(db, source_id)
