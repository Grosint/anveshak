"""Scam template endpoints — list, link/unlink to topics."""
from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from ..auth.rbac import require_role, get_user_org
from ..db.pool import get_db
from ..db import templates as tpl_db
from ..db import topics as topics_db

router = APIRouter(tags=["templates"])


# ---------------------------------------------------------------------------
# GET /api/v1/templates — list all scam templates
# ---------------------------------------------------------------------------

@router.get("/api/v1/templates")
async def list_templates(
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin", "super-admin")),
) -> list[dict]:
    org_id = get_user_org(user)
    return await tpl_db.list_templates(db, org_id=org_id)


# ---------------------------------------------------------------------------
# GET /api/v1/templates/{template_id}
# ---------------------------------------------------------------------------

@router.get("/api/v1/templates/{template_id}")
async def get_template(
    template_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin", "super-admin")),
) -> dict:
    row = await tpl_db.get_template(db, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return row


# ---------------------------------------------------------------------------
# GET /api/v1/topics/{topic_id}/templates — templates linked to topic
# ---------------------------------------------------------------------------

@router.get("/api/v1/topics/{topic_id}/templates")
async def list_topic_templates(
    topic_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin", "super-admin")),
) -> list[dict]:
    await topics_db.verify_topic_access(db, topic_id, user)
    return await tpl_db.list_topic_templates(db, topic_id)


# ---------------------------------------------------------------------------
# POST /api/v1/topics/{topic_id}/templates/{template_id} — link
# ---------------------------------------------------------------------------

@router.post(
    "/api/v1/topics/{topic_id}/templates/{template_id}",
    status_code=status.HTTP_201_CREATED,
)
async def link_template(
    topic_id: str,
    template_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict:
    await topics_db.verify_topic_access(db, topic_id, user)
    tpl = await tpl_db.get_template(db, template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Template not found")
    await tpl_db.link_template(db, topic_id, template_id)
    return {"topic_id": topic_id, "template_id": template_id, "status": "linked"}


# ---------------------------------------------------------------------------
# DELETE /api/v1/topics/{topic_id}/templates/{template_id} — unlink
# ---------------------------------------------------------------------------

@router.delete(
    "/api/v1/topics/{topic_id}/templates/{template_id}",
    status_code=status.HTTP_200_OK,
)
async def unlink_template(
    topic_id: str,
    template_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict:
    await topics_db.verify_topic_access(db, topic_id, user)
    await tpl_db.unlink_template(db, topic_id, template_id)
    return {"topic_id": topic_id, "template_id": template_id, "status": "unlinked"}
