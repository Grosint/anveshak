"""Identifier Search API — Engine C Step 7.

Six endpoints for analysts to search, browse, and export identifiers:
  /search          — full-text + partial match on extracted identifiers
  /top             — most frequent identifiers by source_count
  /clusters        — list identifier clusters for a topic
  /clusters/{id}   — cluster detail with items + sources
  /export          — CSV/JSON download for CFCFRMS, I4C, bank requests
  /co-occurrence   — content items where both identifiers appear
"""
from __future__ import annotations

import csv
import io
import json
from typing import Any, Optional

import asyncpg
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ..auth.rbac import require_role
from ..db import identifiers as identifiers_db
from ..db import topics as topics_db
from ..db import audit as audit_db
from ..db.pool import get_db

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/identifiers", tags=["identifiers"])

MAX_EXPORT_ROWS = 10000

EXPORT_COLUMNS = [
    "entity_type", "entity_text", "confidence",
    "content_item_id", "content_url",
    "source_name", "source_platform", "captured_at",
]


# ---------------------------------------------------------------------------
# Helpers (reuse export.py pattern)
# ---------------------------------------------------------------------------

def _rows_to_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        clean = {}
        for k in columns:
            v = row.get(k, "")
            clean[k] = str(v) if v is not None else ""
        writer.writerow(clean)
    return buf.getvalue()


def _rows_to_json(rows: list[dict[str, Any]]) -> str:
    return json.dumps(rows, default=str, indent=2)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/convergence")
async def get_identifier_convergence(
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
) -> list[dict[str, Any]]:
    """Identifiers appearing in 2+ topics — cross-topic convergence detection."""
    from ..auth.rbac import get_user_org
    org_id = get_user_org(user)
    if not org_id:
        raise HTTPException(status_code=400, detail="Org context required for convergence")
    return await identifiers_db.get_identifier_convergence(
        db, org_id=org_id, limit=limit,
    )


@router.get("/search-global")
async def search_identifiers_global(
    q: str = Query(..., min_length=2, description="Search query (partial match)"),
    type: Optional[str] = Query(None, description="Filter by identifier type"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
) -> list[dict[str, Any]]:
    """Cross-topic identifier search, scoped to user's org."""
    from ..auth.rbac import get_user_org
    org_id = get_user_org(user)
    if not org_id:
        raise HTTPException(status_code=400, detail="Org context required for global search")
    return await identifiers_db.search_identifiers_global(
        db, q=q, org_id=org_id, identifier_type=type, limit=limit,
    )


@router.get("/search")
async def search_identifiers(
    topic_id: str = Query(..., description="Topic ID to search within"),
    q: str = Query(..., min_length=1, description="Search query (partial match)"),
    type: Optional[str] = Query(None, description="Filter by identifier type"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
) -> list[dict[str, Any]]:
    """Search extracted identifiers with partial match (phone suffix, UPI domain, etc.)."""
    await topics_db.verify_topic_access(db, topic_id, user)
    return await identifiers_db.search_identifiers(
        db, q=q, topic_id=topic_id, identifier_type=type, limit=limit,
    )


@router.get("/top")
async def get_top_identifiers(
    topic_id: str = Query(..., description="Topic ID"),
    type: Optional[str] = Query(None, description="Filter by identifier type"),
    min_items: int = Query(1, ge=1, le=100, description="Min content items to include"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
) -> list[dict[str, Any]]:
    """Most frequently appearing identifiers, grouped from extracted_entities."""
    await topics_db.verify_topic_access(db, topic_id, user)
    return await identifiers_db.get_top_identifiers(
        db, topic_id=topic_id, identifier_type=type,
        min_items=min_items, limit=limit,
    )


@router.get("/clusters")
async def list_clusters(
    topic_id: str = Query(..., description="Topic ID"),
    type: Optional[str] = Query(None, description="Filter by identifier type"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
) -> list[dict[str, Any]]:
    """List identifier clusters for a topic, sorted by source_count descending."""
    await topics_db.verify_topic_access(db, topic_id, user)
    return await identifiers_db.list_identifier_clusters(
        db, topic_id=topic_id, identifier_type=type, limit=limit, offset=offset,
    )


@router.get("/clusters/{cluster_id}")
async def get_cluster_detail(
    cluster_id: str,
    topic_id: str = Query(..., description="Topic ID (for access control)"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
) -> dict[str, Any]:
    """Full cluster detail: identifier, all content items, all sources, timeline."""
    # Verify access BEFORE fetching cluster data — prevents timing-based enumeration
    await topics_db.verify_topic_access(db, topic_id, user)
    result = await identifiers_db.get_cluster_detail(db, cluster_id=cluster_id)
    if not result:
        raise HTTPException(status_code=404, detail="Identifier cluster not found")
    if result["topic_id"] != topic_id:
        raise HTTPException(status_code=404, detail="Identifier cluster not found")
    return result


@router.get("/export")
async def export_identifiers(
    request: Request,
    topic_id: str = Query(..., description="Topic ID to export"),
    format: str = Query("csv", pattern="^(csv|json)$", description="Export format"),
    limit: int = Query(5000, ge=1, le=MAX_EXPORT_ROWS, description="Max rows"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> StreamingResponse:
    """Export all identifiers for a topic as CSV or JSON (for CFCFRMS, I4C, bank requests)."""
    await topics_db.verify_topic_access(db, topic_id, user)
    rows = await identifiers_db.export_identifiers(db, topic_id=topic_id, limit=limit)
    if not rows:
        raise HTTPException(status_code=404, detail="No identifiers found for this topic")

    data = _rows_to_csv(rows, EXPORT_COLUMNS) if format == "csv" else _rows_to_json(rows)
    log.info("identifiers.export", topic_id=topic_id, format=format, rows=len(rows))
    await audit_db.log_action(
        db, user["sub"], "export.identifiers", "topic", topic_id,
        {"format": format, "rows": len(rows)},
        request.client.host if request.client else "",
    )

    filename = f"anveshak_identifiers_{topic_id[:8]}"
    if format == "csv":
        return StreamingResponse(
            iter([data]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )
    return StreamingResponse(
        iter([data]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
    )


@router.post("/topics/{topic_id}/templates/{template_id}")
async def link_template(
    topic_id: str,
    template_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, str]:
    """Link a scam template to a topic."""
    await topics_db.verify_topic_access(db, topic_id, user)
    await identifiers_db.link_template(db, topic_id=topic_id, template_id=template_id)
    return {"status": "linked", "topic_id": topic_id, "template_id": template_id}


@router.delete("/topics/{topic_id}/templates/{template_id}")
async def unlink_template(
    topic_id: str,
    template_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, str]:
    """Unlink a scam template from a topic."""
    await topics_db.verify_topic_access(db, topic_id, user)
    await identifiers_db.unlink_template(db, topic_id=topic_id, template_id=template_id)
    return {"status": "unlinked", "topic_id": topic_id, "template_id": template_id}


@router.get("/topics/{topic_id}/templates")
async def list_topic_templates(
    topic_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
) -> list[dict[str, Any]]:
    """List all scam templates linked to a topic."""
    await topics_db.verify_topic_access(db, topic_id, user)
    return await identifiers_db.list_topic_templates(db, topic_id=topic_id)


@router.get("/co-occurrence")
async def get_co_occurrence(
    topic_id: str = Query(..., description="Topic ID"),
    identifier_a: str = Query(..., description="First identifier value"),
    identifier_b: str = Query(..., description="Second identifier value"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
) -> dict[str, Any]:
    """Content items where both identifiers appear — network inference."""
    await topics_db.verify_topic_access(db, topic_id, user)
    items = await identifiers_db.get_co_occurrence(
        db, topic_id=topic_id,
        identifier_a=identifier_a, identifier_b=identifier_b,
        limit=limit,
    )
    return {
        "topic_id": topic_id,
        "identifier_a": identifier_a,
        "identifier_b": identifier_b,
        "items": items,
        "count": len(items),
    }
