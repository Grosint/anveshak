"""Keyword alert rules — CRUD for analyst-defined keyword monitoring."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from anveshak.db import DBConnection
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from ..auth.rbac import get_user_org, require_role
from ..db import alerts as alerts_db
from ..db import audit as audit_db
from ..db import topics as topics_db
from ..db.pool import get_db

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/topics/{topic_id}/alerts", tags=["alerts"])


class CreateAlertRuleRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    keywords: list[str]
    match_mode: str = "any"


class UpdateAlertRuleRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    keywords: list[str] | None = None
    match_mode: str | None = None
    is_active: bool | None = None


@router.post("")
async def create_alert_rule(
    topic_id: str,
    req: CreateAlertRuleRequest,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    await topics_db.verify_topic_access(db, topic_id, user)
    if req.match_mode not in ("any", "all"):
        raise HTTPException(422, "match_mode must be 'any' or 'all'")
    if not req.keywords:
        raise HTTPException(422, "keywords must be non-empty")

    rule_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    await alerts_db.create_rule(
        db,
        rule_id,
        topic_id,
        req.keywords,
        req.match_mode,
        user.get("sub", ""),
        get_user_org(user),
        now,
    )
    await audit_db.log_action(
        db,
        user["sub"],
        "alert_rule.create",
        "keyword_alert_rule",
        rule_id,
        {"topic_id": topic_id, "keywords": req.keywords, "match_mode": req.match_mode},
        request.client.host if request.client else "",
    )
    return {
        "id": rule_id,
        "topic_id": topic_id,
        "keywords": req.keywords,
        "match_mode": req.match_mode,
    }


@router.get("")
async def list_alert_rules(
    topic_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
) -> list[dict[str, Any]]:
    await topics_db.verify_topic_access(db, topic_id, user)
    return await alerts_db.list_rules(db, topic_id)


@router.patch("/{rule_id}")
async def update_alert_rule(
    topic_id: str,
    rule_id: str,
    req: UpdateAlertRuleRequest,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    await topics_db.verify_topic_access(db, topic_id, user)
    result = await alerts_db.update_rule(db, rule_id, req.keywords, req.match_mode, req.is_active)
    if not result:
        raise HTTPException(404, "Alert rule not found")
    return result


@router.delete("/{rule_id}")
async def delete_alert_rule(
    topic_id: str,
    rule_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, str]:
    await topics_db.verify_topic_access(db, topic_id, user)
    deleted = await alerts_db.delete_rule(db, rule_id)
    if not deleted:
        raise HTTPException(404, "Alert rule not found")
    return {"deleted": rule_id}


@router.get("/triggers")
async def list_alert_triggers(
    topic_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
) -> list[dict[str, Any]]:
    await topics_db.verify_topic_access(db, topic_id, user)
    return await alerts_db.list_triggers(db, topic_id, limit, offset)
