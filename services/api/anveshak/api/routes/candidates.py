"""Candidate Topic inbox — issues #26 and #27.

Triage is a different task from monitoring, so the inbox is its own
top-level surface rather than a section inside a Topic.

The system never begins monitoring a subject without a human accepting it.
Accepting creates a Topic linked back to the Watch Space that found it and
populates it from content already collected, so it arrives with history
rather than empty. Dismissing is permanent: detection skips a dismissed
cluster on every later pass, so a triage decision is not re-proposed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

import structlog
from anveshak.db import DBConnection
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict

from ..auth.rbac import require_org_context, require_role
from ..db import audit as audit_db
from ..db import candidates as candidates_db
from ..db import topics as topics_db
from ..db.pool import get_db

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/candidate-topics", tags=["candidate-topics"])

_LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


class AcceptCandidateRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    # Defaults to the cluster label. The analyst names the subject they are
    # choosing to monitor, which is the point of the human decision.
    name: Optional[str] = None
    keywords: list[str] = []


@router.get("")
async def list_candidates(
    candidate_status: str = Query("pending", pattern="^(pending|accepted|dismissed)$"),
    limit: int = Query(100, ge=1, le=500),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> list[dict[str, Any]]:
    """Candidates awaiting triage, ordered by how they are spreading.

    ADR 0001: the order is independent source count then item count. Both
    are counts over rows the analyst can open and recount. No concern score
    participates.
    """
    org_id = require_org_context(user)
    return await candidates_db.list_candidates(
        db, org_id=org_id, status=candidate_status, limit=limit
    )


@router.post("/{candidate_id}/accept", status_code=status.HTTP_201_CREATED)
async def accept_candidate(
    candidate_id: str,
    req: AcceptCandidateRequest,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Create a Topic from a candidate and populate it from existing content."""
    org_id = require_org_context(user)

    candidate = await candidates_db.get_candidate(db, candidate_id, org_id=org_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate topic not found")
    if candidate["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Candidate topic already {candidate['status']}",
        )

    topic_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    name = (req.name or candidate["cluster_label"] or "Promoted narrative").strip()

    await topics_db.insert_topic(
        db,
        topic_id,
        name,
        req.keywords or [],
        list(candidate["watch_space_languages"] or ["en"]),
        30.0,
        3,
        [],
        None,
        None,
        now,
        _LABELS_JSON,
        org_id=org_id,
        # Lineage: the Watch Space that found it stays visible on the Topic.
        parent_topic_id=candidate["watch_space_id"],
    )

    # Populate from content already collected, so the Topic arrives with
    # history rather than waiting for the next collection cycle.
    content_ids = await candidates_db.cluster_content_ids(
        db, candidate["cluster_id"], org_id=org_id
    )
    await candidates_db.link_content_to_topic(db, topic_id, content_ids)

    decided = await candidates_db.set_candidate_status(
        db, candidate_id, org_id=org_id, status="accepted", promoted_topic_id=topic_id
    )
    if decided is None:
        # Another request decided it between the read and the write.
        raise HTTPException(status_code=409, detail="Candidate topic already decided")

    await audit_db.log_action(
        db,
        user["sub"],
        "candidate_topic.accept",
        "candidate_topic",
        candidate_id,
        {"topic_id": topic_id, "content_items_linked": len(content_ids)},
        ip_address=request.client.host if request.client else "",
    )

    log.info(
        "candidates.accepted",
        candidate_id=candidate_id,
        topic_id=topic_id,
        watch_space_id=candidate["watch_space_id"],
        content_items_linked=len(content_ids),
    )

    return {
        "candidate_id": candidate_id,
        "topic_id": topic_id,
        "name": name,
        "content_items_linked": len(content_ids),
    }


@router.post("/{candidate_id}/dismiss")
async def dismiss_candidate(
    candidate_id: str,
    request: Request,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Remove a candidate from the inbox, permanently.

    Detection skips a dismissed cluster on every later pass, so the decision
    persists rather than being re-proposed as the cluster grows.
    """
    org_id = require_org_context(user)

    decided = await candidates_db.set_candidate_status(
        db, candidate_id, org_id=org_id, status="dismissed"
    )
    if decided is None:
        raise HTTPException(status_code=404, detail="Candidate topic not found or already decided")

    await audit_db.log_action(
        db,
        user["sub"],
        "candidate_topic.dismiss",
        "candidate_topic",
        candidate_id,
        {},
        ip_address=request.client.host if request.client else "",
    )

    log.info("candidates.dismissed", candidate_id=candidate_id)
    return {"candidate_id": candidate_id, "status": "dismissed"}
