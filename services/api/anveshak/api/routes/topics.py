"""Topic management endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Optional

import structlog
from anveshak.db import DBConnection
from arq import create_pool as arq_create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict

from ..auth.rbac import get_user_org, is_super_admin, require_org_context, require_role
from ..db import audit as audit_db
from ..db import sources as sources_db
from ..db import topics as topics_db
from ..db.pool import get_db
from ..settings import settings

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/topics", tags=["topics"])

_LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


class CreateTopicRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str
    keywords: list[str]
    languages: list[str] = ["en"]
    credibility_min: float = 30.0
    signal_threshold: int = 3
    identifier_signal_threshold: int = 2
    clip_categories: list[str] = []
    scheduled_report_cron: Optional[str] = None
    scheduled_report_type: Optional[str] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_topic(
    req: CreateTopicRequest,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    topic_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    org_id = get_user_org(user)
    await topics_db.insert_topic(
        db,
        topic_id,
        req.name,
        req.keywords,
        req.languages,
        req.credibility_min,
        req.signal_threshold,
        req.clip_categories,
        req.scheduled_report_cron,
        req.scheduled_report_type,
        now,
        _LABELS_JSON,
        org_id=org_id,
        identifier_signal_threshold=req.identifier_signal_threshold,
    )
    enqueue_failed = False
    try:
        redis = await arq_create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.enqueue_job("backfill_topic_job", topic_id, _queue_name="arq:analyst")
    except Exception as exc:
        enqueue_failed = True
        import structlog

        structlog.get_logger(__name__).warning(
            "topics.backfill_enqueue_failed",
            topic_id=topic_id,
            error=str(exc),
        )
    await audit_db.log_action(
        db,
        user["sub"],
        "topic.create",
        "topic",
        topic_id,
        {"name": req.name, "keywords": req.keywords},
        request.client.host if request.client else "",
    )
    if enqueue_failed:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=202,
            content={
                "id": topic_id,
                "name": req.name,
                "status": "active",
                "warning": "Topic created but background processing delayed",
            },
        )
    return {"id": topic_id, "name": req.name, "status": "active"}


@router.get("")
async def list_topics(
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin", "super-admin")),
):
    if is_super_admin(user):
        return await topics_db.list_topics(db)
    # Super-admin took the branch above, so require an org here rather than
    # passing None and returning an empty list.
    return await topics_db.list_topics_by_org(db, require_org_context(user))


class UpdateTopicStatusRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    status: str  # active | paused | archived


@router.patch("/{topic_id}/status")
async def update_topic_status(
    topic_id: str,
    req: UpdateTopicStatusRequest,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await topics_db.verify_topic_access(db, topic_id, user)
    if req.status not in ("active", "paused", "archived"):
        raise HTTPException(status_code=422, detail="status must be active|paused|archived")
    if not await topics_db.topic_exists(db, topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    await topics_db.update_topic_status(db, topic_id, req.status, datetime.now(UTC))
    await audit_db.log_action(
        db,
        user["sub"],
        "topic.status_change",
        "topic",
        topic_id,
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
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Update or clear scheduled report configuration for a topic."""
    await topics_db.verify_topic_access(db, topic_id, user)
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
        db,
        topic_id,
        req.scheduled_report_cron,
        req.scheduled_report_type,
    )
    return {
        "topic_id": topic_id,
        "scheduled_report_cron": req.scheduled_report_cron,
        "scheduled_report_type": req.scheduled_report_type,
    }


@router.get("/{topic_id}")
async def get_topic(
    topic_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await topics_db.verify_topic_access(db, topic_id, user)
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
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await topics_db.verify_topic_access(db, topic_id, user)
    if sentiment and sentiment not in ("positive", "negative", "neutral"):
        raise HTTPException(status_code=422, detail="sentiment must be positive|negative|neutral")
    if sort_by and sort_by not in ("captured_at", "relevance"):
        raise HTTPException(status_code=422, detail="sort_by must be captured_at|relevance")
    topic = await topics_db.get_topic(db, topic_id)
    relevance_threshold = topic.get("topic_relevance_threshold") if topic else None
    return await topics_db.get_topic_content(
        db,
        topic_id,
        limit,
        offset,
        has_embedding,
        platform,
        include_low_quality,
        sentiment,
        relevance_threshold=relevance_threshold,
        sort_by=sort_by or "captured_at",
    )


@router.get("/{topic_id}/sentiment-trend")
async def get_sentiment_trend(
    topic_id: str,
    days: int = 30,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await topics_db.verify_topic_access(db, topic_id, user)
    if days < 1 or days > 365:
        raise HTTPException(status_code=422, detail="days must be 1-365")
    return await topics_db.get_sentiment_trend(db, topic_id, days)


@router.get("/{topic_id}/trending-keywords")
async def get_trending_keywords(
    topic_id: str,
    days: int = 7,
    limit: int = 15,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await topics_db.verify_topic_access(db, topic_id, user)
    if days < 1 or days > 365:
        raise HTTPException(status_code=422, detail="days must be 1-365")
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=422, detail="limit must be 1-50")
    return await topics_db.get_trending_keywords(db, topic_id, days, limit)


@router.get("/{topic_id}/entities")
async def get_topic_entities(
    topic_id: str,
    days: int = 30,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await topics_db.verify_topic_access(db, topic_id, user)
    if days < 1 or days > 365:
        raise HTTPException(status_code=422, detail="days must be 1-365")
    return await topics_db.get_topic_entities(db, topic_id, days)


@router.get("/{topic_id}/clusters")
async def get_topic_clusters(
    topic_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    await topics_db.verify_topic_access(db, topic_id, user)
    return await topics_db.get_topic_clusters(db, topic_id)


@router.get("/{topic_id}/clusters/search")
async def search_topic_clusters(
    topic_id: str,
    # request has no default: FastAPI always injects it, so `= None` was dead and
    # forced a needless None check at the audit-log call below.
    request: Request,
    q: str = Query(..., min_length=1, description="Search query text"),
    limit: int = Query(20, ge=1, le=50),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Narrative search: rank clusters by centroid cosine similarity.

    Falls back to ILIKE on label/executive_summary when embedding service
    is unavailable. Every search is audit-logged for court readiness.
    """
    await topics_db.verify_topic_access(db, topic_id, user)

    # Try semantic search via centroid embedding
    try:
        from ..embedding import embed_query

        query_vec_str = await embed_query(q)
        clusters = await topics_db.search_clusters_by_centroid(
            db,
            query_vec_str,
            topic_id,
            limit=limit,
        )
    except Exception as exc:
        log.warning(
            "cluster_search.embed_fallback",
            query=q,
            topic_id=topic_id,
            error=str(exc),
        )
        query_vec_str = None
        clusters = await topics_db.search_clusters_by_label(
            db,
            q,
            topic_id,
            limit=limit,
        )

    # Audit log — immutable record of every search
    await audit_db.log_action(
        db,
        user["sub"],
        "search.cluster",
        "topic",
        topic_id,
        {
            "query": q,
            "mode": "centroid" if query_vec_str else "keyword",
            "result_count": len(clusters),
            "result_cluster_ids": [c["id"] for c in clusters],
        },
        request.client.host if request.client else "",
    )

    return clusters


@router.get("/{topic_id}/clusters/{cluster_id}/content")
async def get_cluster_content(
    topic_id: str,
    cluster_id: str,
    # request has no default: FastAPI always injects it.
    request: Request,
    q: Optional[str] = Query(None, description="Optional query for relevance ranking"),
    sort: str = Query("time", description="time or relevance"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Drill-down: content items within a cluster, optionally ranked by query similarity.

    Multi-tenancy guard: cluster must belong to the topic in the URL path,
    and topic must belong to the user's org.
    """
    await topics_db.verify_topic_access(db, topic_id, user)

    # Verify cluster belongs to this topic (prevents cross-org leak via UUID guessing)
    if not await topics_db.verify_cluster_belongs_to_topic(db, cluster_id, topic_id):
        raise HTTPException(status_code=404, detail="Cluster not found in this topic")

    if sort not in ("time", "relevance"):
        raise HTTPException(status_code=422, detail="sort must be time|relevance")

    query_vec_str = None
    if q and sort == "relevance":
        try:
            from ..embedding import embed_query

            query_vec_str = await embed_query(q)
        except Exception as exc:
            log.warning(
                "cluster_content.embed_failed",
                query=q,
                cluster_id=cluster_id,
                error=str(exc),
            )
            # Fall back to time sort if embedding unavailable
            sort = "time"

    items = await topics_db.get_cluster_content(
        db,
        cluster_id,
        sort=sort,
        query_vec_str=query_vec_str,
        limit=limit,
        offset=offset,
    )

    # Audit log
    await audit_db.log_action(
        db,
        user["sub"],
        "search.cluster_content",
        "cluster",
        cluster_id,
        {
            "topic_id": topic_id,
            "query": q,
            "sort": sort,
            "result_count": len(items),
        },
        request.client.host if request.client else "",
    )

    return items


@router.get("/{topic_id}/sources")
async def get_topic_sources(
    topic_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Return all sources assigned to this topic via topic_sources.

    Each source includes item_count — number of content items from that source
    in this topic, descending (most active source first). Criterion 7.10.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    if not await topics_db.topic_exists(db, topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    return await sources_db.list_topic_sources(db, topic_id)


@router.post("/{topic_id}/sources/{source_id}", status_code=status.HTTP_201_CREATED)
async def add_topic_source(
    topic_id: str,
    source_id: str,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Associate a source with a topic so the scraper monitors it."""
    await topics_db.verify_topic_access(db, topic_id, user)
    if not await topics_db.topic_exists(db, topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    if not await sources_db.source_exists(db, source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    await sources_db.add_topic_source(db, topic_id, source_id)
    await audit_db.log_action(
        db,
        user["sub"],
        "topic.source_link",
        "topic",
        topic_id,
        {"source_id": source_id},
        request.client.host if request.client else "",
    )
    return {"topic_id": topic_id, "source_id": source_id, "status": "linked"}


@router.delete("/{topic_id}/sources/{source_id}", status_code=status.HTTP_200_OK)
async def remove_topic_source(
    topic_id: str,
    source_id: str,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Remove a source from a topic's monitoring list."""
    await topics_db.verify_topic_access(db, topic_id, user)
    if not await topics_db.topic_exists(db, topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    await sources_db.remove_topic_source(db, topic_id, source_id)
    await audit_db.log_action(
        db,
        user["sub"],
        "topic.source_unlink",
        "topic",
        topic_id,
        {"source_id": source_id},
        request.client.host if request.client else "",
    )
    return {"topic_id": topic_id, "source_id": source_id, "status": "unlinked"}
