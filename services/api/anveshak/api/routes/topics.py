"""Topic management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
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
from ..db import audit as audit_db
from ..auth.rbac import require_role
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
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
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
        await redis.enqueue_job("backfill_topic_job", topic_id, _queue_name="arq:analyst")
    except Exception as exc:
        import structlog
        structlog.get_logger(__name__).warning(
            "topics.backfill_enqueue_failed",
            topic_id=topic_id,
            error=str(exc),
        )
    await audit_db.log_action(
        db, user["sub"], "topic.create", "topic", topic_id,
        {"name": req.name, "keywords": req.keywords},
        request.client.host if request.client else "",
    )
    return {"id": topic_id, "name": req.name, "status": "active"}


@router.get("")
async def list_topics(
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
):
    return await topics_db.list_topics(db)


class UpdateTopicStatusRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    status: str  # active | paused | archived


@router.patch("/{topic_id}/status")
async def update_topic_status(
    topic_id: str,
    req: UpdateTopicStatusRequest,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    if req.status not in ("active", "paused", "archived"):
        raise HTTPException(status_code=422, detail="status must be active|paused|archived")
    if not await topics_db.topic_exists(db, topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    await topics_db.update_topic_status(db, topic_id, req.status, datetime.now(UTC))
    await audit_db.log_action(
        db, user["sub"], "topic.status_change", "topic", topic_id,
        {"new_status": req.status},
        request.client.host if request.client else "",
    )
    return {"topic_id": topic_id, "status": req.status}


class UpdateScheduleRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    scheduled_report_cron: Optional[str] = None
    scheduled_report_type: Optional[str] = None


@router.patch("/{topic_id}/schedule")
async def update_topic_schedule(
    topic_id: str,
    req: UpdateScheduleRequest,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Update or clear scheduled report configuration for a topic."""
    if not await topics_db.topic_exists(db, topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    # Validate cron expression if provided
    if req.scheduled_report_cron:
        try:
            from croniter import croniter
            croniter(req.scheduled_report_cron)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid cron expression: {exc}")
    await topics_db.update_topic_schedule(
        db, topic_id, req.scheduled_report_cron, req.scheduled_report_type,
    )
    return {
        "topic_id": topic_id,
        "scheduled_report_cron": req.scheduled_report_cron,
        "scheduled_report_type": req.scheduled_report_type,
    }


@router.get("/{topic_id}")
async def get_topic(
    topic_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
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
    include_low_quality: bool = False,
    sentiment: Optional[str] = None,
    sort_by: Optional[str] = None,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    if sentiment and sentiment not in ("positive", "negative", "neutral"):
        raise HTTPException(status_code=422, detail="sentiment must be positive|negative|neutral")
    if sort_by and sort_by not in ("captured_at", "relevance"):
        raise HTTPException(status_code=422, detail="sort_by must be captured_at|relevance")
    topic = await topics_db.get_topic(db, topic_id)
    relevance_threshold = topic.get("topic_relevance_threshold") if topic else None
    return await topics_db.get_topic_content(
        db, topic_id, limit, offset, has_embedding, platform, include_low_quality, sentiment,
        relevance_threshold=relevance_threshold,
        sort_by=sort_by or "captured_at",
    )


@router.get("/{topic_id}/sentiment-trend")
async def get_sentiment_trend(
    topic_id: str,
    days: int = 30,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    if days < 1 or days > 365:
        raise HTTPException(status_code=422, detail="days must be 1-365")
    return await topics_db.get_sentiment_trend(db, topic_id, days)


@router.get("/{topic_id}/trending-keywords")
async def get_trending_keywords(
    topic_id: str,
    days: int = 7,
    limit: int = 15,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    if days < 1 or days > 365:
        raise HTTPException(status_code=422, detail="days must be 1-365")
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=422, detail="limit must be 1-50")
    return await topics_db.get_trending_keywords(db, topic_id, days, limit)


@router.get("/{topic_id}/entities")
async def get_topic_entities(
    topic_id: str,
    days: int = 30,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    if days < 1 or days > 365:
        raise HTTPException(status_code=422, detail="days must be 1-365")
    return await topics_db.get_topic_entities(db, topic_id, days)


@router.get("/{topic_id}/clusters")
async def get_topic_clusters(
    topic_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    return await topics_db.get_topic_clusters(db, topic_id)


@router.get("/{topic_id}/sources")
async def get_topic_sources(
    topic_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Return all sources assigned to this topic via topic_sources.

    Each source includes item_count — number of content items from that source
    in this topic, descending (most active source first). Criterion 7.10.
    """
    if not await topics_db.topic_exists(db, topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    return await sources_db.list_topic_sources(db, topic_id)


@router.post("/{topic_id}/sources/{source_id}", status_code=status.HTTP_201_CREATED)
async def add_topic_source(
    topic_id: str,
    source_id: str,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Associate a source with a topic so the scraper monitors it."""
    if not await topics_db.topic_exists(db, topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    if not await sources_db.source_exists(db, source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    await sources_db.add_topic_source(db, topic_id, source_id)
    await audit_db.log_action(
        db, user["sub"], "topic.source_link", "topic", topic_id,
        {"source_id": source_id},
        request.client.host if request.client else "",
    )
    return {"topic_id": topic_id, "source_id": source_id, "status": "linked"}


@router.delete("/{topic_id}/sources/{source_id}", status_code=status.HTTP_200_OK)
async def remove_topic_source(
    topic_id: str,
    source_id: str,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Remove a source from a topic's monitoring list."""
    if not await topics_db.topic_exists(db, topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    await sources_db.remove_topic_source(db, topic_id, source_id)
    await audit_db.log_action(
        db, user["sub"], "topic.source_unlink", "topic", topic_id,
        {"source_id": source_id},
        request.client.host if request.client else "",
    )
    return {"topic_id": topic_id, "source_id": source_id, "status": "unlinked"}
