"""Topic management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from typing import Optional
import asyncpg
import uuid
from datetime import datetime, UTC
from arq import create_pool as arq_create_pool
from arq.connections import RedisSettings
from ..db.pool import get_db
from ..db import topics as topics_db
from ..db import sources as sources_db
from ..auth.jwt import get_current_user
from ..settings import settings
from anveshak.models import Labels, Topic, TopicStatus

router = APIRouter(prefix="/api/v1/topics", tags=["topics"])

_LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


class CreateTopicRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str
    keywords: list[str]
    languages: list[str] = ["en"]
    credibility_min: float = 30.0
    signal_threshold: int = 3
    clip_categories: list[str] = []
    scheduled_report_cron: Optional[str] = None
    scheduled_report_type: Optional[str] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_topic(
    req: CreateTopicRequest,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    topic_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    await topics_db.insert_topic(
        db, topic_id, req.name, req.keywords, req.languages,
        req.credibility_min, req.signal_threshold,
        req.clip_categories, req.scheduled_report_cron, req.scheduled_report_type,
        now, _LABELS_JSON,
    )
    try:
        redis = await arq_create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.enqueue_job("backfill_topic_job", topic_id)
    except Exception as exc:
        import structlog
        structlog.get_logger(__name__).warning(
            "topics.backfill_enqueue_failed",
            topic_id=topic_id,
            error=str(exc),
        )
    return {"id": topic_id, "name": req.name, "status": "active"}


@router.get("")
async def list_topics(
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await topics_db.list_topics(db)


class UpdateTopicStatusRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    status: str  # active | paused | archived


@router.patch("/{topic_id}/status")
async def update_topic_status(
    topic_id: str,
    req: UpdateTopicStatusRequest,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if req.status not in ("active", "paused", "archived"):
        raise HTTPException(status_code=422, detail="status must be active|paused|archived")
    if not await topics_db.topic_exists(db, topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    await topics_db.update_topic_status(db, topic_id, req.status, datetime.now(UTC))
    return {"topic_id": topic_id, "status": req.status}


@router.get("/{topic_id}")
async def get_topic(
    topic_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    row = await topics_db.get_topic(db, topic_id)
    if not row:
        raise HTTPException(status_code=404, detail="Topic not found")
    return row


@router.get("/{topic_id}/content")
async def get_topic_content(
    topic_id: str,
    limit: int = 50,
    offset: int = 0,
    has_embedding: Optional[bool] = None,
    platform: Optional[str] = None,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await topics_db.get_topic_content(db, topic_id, limit, offset, has_embedding, platform)


@router.get("/{topic_id}/entities")
async def get_topic_entities(
    topic_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await topics_db.get_topic_entities(db, topic_id)


@router.get("/{topic_id}/clusters")
async def get_topic_clusters(
    topic_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await topics_db.get_topic_clusters(db, topic_id)


@router.get("/{topic_id}/sources")
async def get_topic_sources(
    topic_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return all sources that have contributed content to this topic.

    Each source includes item_count — number of content items from that source
    in this topic, descending (most active source first). Criterion 7.10.
    """
    if not await topics_db.topic_exists(db, topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    return await sources_db.list_topic_sources(db, topic_id)
