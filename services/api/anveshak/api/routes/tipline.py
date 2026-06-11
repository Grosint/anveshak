"""Tip-Line Ingestion Endpoint — Engine C Step 6.

POST /api/v1/tipline/ingest — accepts citizen-forwarded scam messages
via HTTP POST (WhatsApp proxy, web form, bulk import).

Authentication: API key per organization (header X-Api-Key).
No JWT required — external systems POST directly.

Rate limiting: 100 requests/minute per API key (middleware).
"""
from __future__ import annotations

import hashlib
import re
import uuid
from typing import Optional

import asyncpg
import structlog
from arq import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from ..db import tipline as tipline_db
from ..db.pool import get_db

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/tipline", tags=["tipline"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TiplineIngestRequest(BaseModel):
    """Citizen-forwarded scam message."""
    model_config = ConfigDict(strict=True)

    text: str = Field(..., min_length=1, description="Forwarded message content")
    topic_id: str = Field(..., description="Topic to associate with")
    media_url: Optional[str] = Field(None, description="Attached image/video URL")
    source_phone: Optional[str] = Field(None, description="Tipline number that received it")
    forwarded_from: Optional[str] = Field(None, description="Original sender if known")
    labels: dict = Field(
        default_factory=lambda: {
            "classification": "OPEN",
            "domain": "tipline",
            "owner_org": "anveshak",
        },
        description="Labels (mandatory per CLAUDE.md)",
    )


class TiplineIngestResponse(BaseModel):
    """Response after tipline content ingestion."""
    model_config = ConfigDict(strict=True)

    id: str
    content_hash: str
    status: str  # "queued" | "duplicate"
    duplicate: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lowercase + collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _compute_hash(text: str) -> str:
    """SHA-256 of normalised text — dedup key."""
    return hashlib.sha256(_normalise(text).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# ARQ pool dependency
# ---------------------------------------------------------------------------

def _get_arq_pool(request: Request) -> ArqRedis:
    """Inject ARQ pool from app state."""
    return request.app.state.arq_pool


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/ingest", response_model=TiplineIngestResponse)
async def ingest_tipline(
    body: TiplineIngestRequest,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    arq_pool: ArqRedis = Depends(_get_arq_pool),
) -> TiplineIngestResponse:
    """Ingest a citizen-forwarded scam message.

    Auth: X-Api-Key header (per-org API key).
    Creates content_item, enqueues analyse_content ARQ job.
    Returns content_item_id and dedup status.
    """
    # 1. Authenticate via API key
    api_key = request.headers.get("x-api-key")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Api-Key header",
        )

    key_info = await tipline_db.lookup_api_key(db, api_key)
    if key_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    org_id: str = key_info["org_id"]

    # 2. Verify topic belongs to org
    topic_valid = await tipline_db.verify_topic_org(db, body.topic_id, org_id)
    if not topic_valid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )

    # 3. Get or create tipline source for this org
    source = await tipline_db.get_or_create_tipline_source(db, org_id)
    source_id: str = source["id"]
    credibility_score: float = source["credibility_score"]

    # 4. Compute content hash for dedup
    content_hash = _compute_hash(body.text)
    content_item_id = str(uuid.uuid4())

    # 5. Insert content item (ON CONFLICT dedup)
    result = await tipline_db.insert_tipline_content(
        db,
        content_item_id=content_item_id,
        topic_id=body.topic_id,
        source_id=source_id,
        raw_text=body.text,
        content_hash=content_hash,
        credibility_score=credibility_score,
        org_id=org_id,
        source_phone=body.source_phone,
        forwarded_from=body.forwarded_from,
    )

    if result is None:
        # Duplicate content
        log.debug(
            "tipline.ingest.dedup",
            content_hash=content_hash,
            topic_id=body.topic_id,
        )
        return TiplineIngestResponse(
            id=content_item_id,
            content_hash=content_hash,
            status="duplicate",
            duplicate=True,
        )

    inserted_id: str = result["id"]

    # 6. Enqueue analyse_content ARQ job
    try:
        await arq_pool.enqueue_job("analyse_content", inserted_id)
        log.info(
            "tipline.ingest.queued",
            content_item_id=inserted_id,
            topic_id=body.topic_id,
            org_id=org_id,
        )
    except Exception as exc:
        # Non-fatal: content is saved, orphan sweep will catch it
        log.warning(
            "tipline.ingest.enqueue_failed",
            content_item_id=inserted_id,
            error=str(exc),
        )

    return TiplineIngestResponse(
        id=inserted_id,
        content_hash=content_hash,
        status="queued",
        duplicate=False,
    )
