"""Content item endpoints — full item detail and pgvector similarity search.

Criteria 1.21: GET /api/v1/content/{id}   — full item + entities
Criteria 1.23: GET /api/v1/search         — pgvector cosine similarity search
Criteria 1.24: similarity_score float in search results
"""
from __future__ import annotations

import asyncpg
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.rbac import require_role
from ..db.pool import get_db
from ..db import content as content_db
from ..db import topics as topics_db
from ..embedding import embed_query as _embed_query

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["content"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/content/{content_id}")
async def get_content_item(
    content_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Full content item including extracted entities (criteria 1.21)."""
    row = await content_db.get_content_item(db, content_id)
    if not row:
        raise HTTPException(status_code=404, detail="Content item not found")
    await topics_db.verify_topic_access(db, row["topic_id"], user)
    row["extracted_entities"] = await content_db.get_entities(db, content_id)
    return row


@router.get("/search")
async def search_content(
    q: str = Query(..., min_length=1, description="Search query text"),
    topic_id: str = Query(..., description="Topic to search within"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """pgvector cosine similarity search within a topic (criteria 1.23, 1.24)."""
    await topics_db.verify_topic_access(db, topic_id, user)
    try:
        query_vec_str = await _embed_query(q)
    except Exception as exc:
        log.error("search.embed_failed", query=q, error=str(exc))
        raise HTTPException(status_code=503, detail="Embedding service unavailable")

    return await content_db.vector_search(db, query_vec_str, topic_id)
