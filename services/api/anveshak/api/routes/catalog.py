"""Catalog & discovery endpoints — curated source suggestions and discovered sources."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

import structlog
from anveshak.db import DBConnection
from anveshak.source_rubric import (
    NEUTRAL_BASELINE,
    creation_score,
    load_rubric,
    rubric_changed_by,
)
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.rbac import require_org_context, require_role
from ..db import catalog as catalog_db
from ..db import sources as sources_db
from ..db import topics as topics_db
from ..db.pool import get_db

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["catalog"])

_LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


async def _insert_with_baseline(
    db: DBConnection,
    *,
    source_id: str,
    name: str,
    handle: str,
    platform: str,
    now: Any,
    org_id: str,
) -> None:
    """Create a Source at its structural baseline, audited (#51, ADR 0004).

    `org_id` is required, not optional: `sources.org_id` and
    `credibility_audit_log.org_id` are both NOT NULL references to
    organizations, so a default of None writes a row postgres refuses.

    The score and its audit row are written together, the same way the
    Source registration route writes them, so an approved catalog entry and
    a hand-registered outlet leave the same trail.
    """
    score, basis, declaration = creation_score(handle)
    rubric = load_rubric()
    log.info(
        "catalog.credibility_baseline",
        url_or_handle=handle,
        score=score,
        basis=basis,
        criteria_met=declaration.criteria_met if basis == "rubric" and declaration else [],
    )
    async with db.transaction():
        await sources_db.insert_source(
            db,
            source_id=source_id,
            name=name,
            url_or_handle=handle,
            platform=platform,
            credibility_score=score,
            now=now,
            labels_json=_LABELS_JSON,
            org_id=org_id,
        )
        if basis == "rubric" and declaration is not None:
            await sources_db.log_creation_baseline(
                db,
                source_id,
                neutral_score=NEUTRAL_BASELINE,
                baseline=score,
                reason=rubric.reason_for(declaration),
                changed_by=rubric_changed_by(rubric.version),
                now=now,
                labels_json=_LABELS_JSON,
                org_id=org_id,
            )


SQL_GET_TOPIC_KEYWORDS = "SELECT keywords FROM topics WHERE id = $1"
SQL_GET_DISCOVERED = "SELECT * FROM discovered_sources WHERE id = $1 AND topic_id = $2"


# ---------------------------------------------------------------------------
# Level 0 — Curated Catalog
# ---------------------------------------------------------------------------


@router.get("/topics/{topic_id}/catalog-suggestions")
async def get_catalog_suggestions(
    topic_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Suggest catalog sources matching the topic's keywords.

    Matches catalog entries whose domain_tags overlap with the topic keywords.
    Sorted by recommendation_rank (most_recommended first), then reliability_tier.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    topic = await db.fetchrow(SQL_GET_TOPIC_KEYWORDS, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

    keywords = topic["keywords"] or []

    # Normalize: extract lowercase single words from multi-word keyword phrases
    # e.g. ["PLA Navy", "Indian Ocean"] → {"pla", "navy", "indian", "ocean", ...}
    # This matches against catalog domain_tags which are single lowercase words
    normalized_tags = set()
    for kw in keywords:
        for word in kw.lower().split():
            if len(word) >= 3:  # skip short words like "of", "in"
                normalized_tags.add(word)
    # Also add the original keywords lowercased (for exact tag matches)
    for kw in keywords:
        normalized_tags.add(kw.lower())

    suggestions = await catalog_db.list_catalog_suggestions(db, sorted(normalized_tags))

    return {
        "topic_id": topic_id,
        "suggestions": suggestions,
        "total": len(suggestions),
    }


@router.post("/topics/{topic_id}/catalog-approve")
async def approve_catalog_entry(
    topic_id: str,
    catalog_entry_id: str = Query(..., description="ID of the catalog entry to approve"),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Approve a catalog entry — create source, link to topic, record approval.

    One-click flow: catalog entry → source → topic_sources → catalog_approval.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    entry = await catalog_db.get_catalog_entry(db, catalog_entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Catalog entry {catalog_entry_id} not found")

    # Create a source from the catalog entry
    source_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    await _insert_with_baseline(
        db,
        source_id=source_id,
        name=entry["name"],
        handle=entry["url_or_handle"],
        platform=entry["platform"],
        now=now,
        org_id=require_org_context(user),
    )

    # Link source to topic
    await sources_db.add_topic_source(db, topic_id, source_id)

    # Record approval
    await catalog_db.insert_catalog_approval(
        db,
        catalog_entry_id=catalog_entry_id,
        topic_id=topic_id,
        source_id=source_id,
        approved_by=user.get("user_id", "unknown"),
        labels_json=_LABELS_JSON,
    )

    log.info(
        "catalog.entry_approved",
        catalog_entry_id=catalog_entry_id,
        source_id=source_id,
        topic_id=topic_id,
    )

    return {
        "catalog_entry_id": catalog_entry_id,
        "source_id": source_id,
        "topic_id": topic_id,
        "name": entry["name"],
    }


@router.get("/catalog")
async def list_catalog(
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("admin")),
) -> dict[str, Any]:
    """List all catalog entries (admin view)."""
    entries = await catalog_db.list_all_catalog(db)
    return {"entries": entries, "total": len(entries)}


# ---------------------------------------------------------------------------
# Discovered Sources (Levels 1-4)
# ---------------------------------------------------------------------------


@router.get("/topics/{topic_id}/discovered")
async def list_discovered_sources(
    topic_id: str,
    status: Optional[str] = Query(
        None, description="Filter by status: pending, approved, dismissed"
    ),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """List discovered sources for a topic, optionally filtered by status."""
    await topics_db.verify_topic_access(db, topic_id, user)
    discovered = await catalog_db.list_discovered(db, topic_id, status=status)
    return {
        "topic_id": topic_id,
        "discovered": discovered,
        "total": len(discovered),
    }


@router.post("/topics/{topic_id}/discovered/{discovered_id}/approve")
async def approve_discovered_source(
    topic_id: str,
    discovered_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Approve a discovered source — create source, link to topic, update status."""
    await topics_db.verify_topic_access(db, topic_id, user)
    row = await db.fetchrow(SQL_GET_DISCOVERED, discovered_id, topic_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Discovered source {discovered_id} not found")

    # Create source from discovered entry
    source_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    await _insert_with_baseline(
        db,
        source_id=source_id,
        name=row["domain_or_handle"],
        handle=row["domain_or_handle"],
        platform=row["platform"],
        now=now,
        org_id=require_org_context(user),
    )

    # Link to topic
    await sources_db.add_topic_source(db, topic_id, source_id)

    # Update discovered source status
    await catalog_db.approve_discovered(db, discovered_id, source_id)

    log.info(
        "discovery.source_approved",
        discovered_id=discovered_id,
        source_id=source_id,
        topic_id=topic_id,
        method=row["discovery_method"],
    )

    return {
        "discovered_id": discovered_id,
        "source_id": source_id,
        "topic_id": topic_id,
        "domain_or_handle": row["domain_or_handle"],
    }


@router.post("/topics/{topic_id}/discovered/{discovered_id}/dismiss")
async def dismiss_discovered_source(
    topic_id: str,
    discovered_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Dismiss a discovered source suggestion."""
    await topics_db.verify_topic_access(db, topic_id, user)
    row = await db.fetchrow(SQL_GET_DISCOVERED, discovered_id, topic_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Discovered source {discovered_id} not found")

    await catalog_db.dismiss_discovered(db, discovered_id)

    log.info(
        "discovery.source_dismissed",
        discovered_id=discovered_id,
        topic_id=topic_id,
    )

    return {
        "discovered_id": discovered_id,
        "status": "dismissed",
    }
