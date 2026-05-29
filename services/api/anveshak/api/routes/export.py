"""Export endpoints — CSV/JSON download for content items, signals, entities.

Streaming CSV to avoid loading entire dataset in memory.
Row limit enforced to prevent accidental data dumps.
"""
from __future__ import annotations

import csv
import io
import json
from typing import Any

import asyncpg
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ..auth.rbac import require_role
from ..db import audit as audit_db
from ..db import topics as topics_db
from ..db.pool import get_db

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/export", tags=["export"])

MAX_EXPORT_ROWS = 10000


# ---------------------------------------------------------------------------
# SQL queries
# ---------------------------------------------------------------------------

SQL_EXPORT_CONTENT = """
    SELECT ci.id, ci.url, ci.clean_text, ci.language,
           ci.credibility_score_at_capture, ci.captured_at,
           ci.content_hash, ci.source_id,
           s.name AS source_name, s.platform
    FROM content_items ci
    JOIN sources s ON ci.source_id = s.id
    WHERE ci.topic_id = $1
    ORDER BY ci.captured_at DESC
    LIMIT $2
"""

SQL_EXPORT_SIGNALS = """
    SELECT s.id, s.topic_id, s.signal_type, s.description,
           s.status, s.created_at, s.delivered_at,
           nc.label AS cluster_label
    FROM signals s
    LEFT JOIN narrative_clusters nc ON s.cluster_id = nc.id
    WHERE s.topic_id = $1
    ORDER BY s.created_at DESC
    LIMIT $2
"""

SQL_EXPORT_ENTITIES = """
    SELECT ee.id, ee.entity_type, ee.entity_text, ee.confidence,
           ee.language, ee.created_at,
           ci.url AS content_url, ci.topic_id
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE ci.topic_id = $1
    ORDER BY ee.entity_type, ee.entity_text
    LIMIT $2
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rows_to_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    """Convert rows to CSV string."""
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
    """Convert rows to JSON string."""
    return json.dumps(rows, default=str, indent=2)


async def _fetch_rows(db: asyncpg.Connection, sql: str, topic_id: str, limit: int) -> list[dict]:
    rows = await db.fetch(sql, topic_id, limit)
    return [dict(r) for r in rows]


def _make_response(data: str, fmt: str, filename: str) -> StreamingResponse:
    """Create streaming response with correct content type and disposition."""
    if fmt == "csv":
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

CONTENT_COLUMNS = [
    "id", "url", "clean_text", "language", "credibility_score_at_capture",
    "captured_at", "content_hash", "source_id", "source_name", "platform",
]

SIGNAL_COLUMNS = [
    "id", "topic_id", "signal_type", "description", "status",
    "created_at", "delivered_at", "cluster_label",
]

ENTITY_COLUMNS = [
    "id", "entity_type", "entity_text", "confidence",
    "language", "created_at", "content_url", "topic_id",
]


@router.get("/content")
async def export_content(
    request: Request,
    topic_id: str = Query(..., description="Topic ID to export"),
    format: str = Query("csv", pattern="^(csv|json)$", description="Export format"),
    limit: int = Query(1000, ge=1, le=MAX_EXPORT_ROWS, description="Max rows"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Export content items for a topic as CSV or JSON."""
    await topics_db.verify_topic_access(db, topic_id, user)
    rows = await _fetch_rows(db, SQL_EXPORT_CONTENT, topic_id, limit)
    if not rows:
        raise HTTPException(status_code=404, detail="No content found for this topic")

    data = _rows_to_csv(rows, CONTENT_COLUMNS) if format == "csv" else _rows_to_json(rows)
    log.info("export.content", topic_id=topic_id, format=format, rows=len(rows))
    await audit_db.log_action(
        db, user["sub"], "export.content", "topic", topic_id,
        {"format": format, "rows": len(rows)},
        request.client.host if request.client else "",
    )
    return _make_response(data, format, f"anveshak_content_{topic_id[:8]}")


@router.get("/signals")
async def export_signals(
    request: Request,
    topic_id: str = Query(..., description="Topic ID to export"),
    format: str = Query("csv", pattern="^(csv|json)$", description="Export format"),
    limit: int = Query(1000, ge=1, le=MAX_EXPORT_ROWS, description="Max rows"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Export signals for a topic as CSV or JSON."""
    await topics_db.verify_topic_access(db, topic_id, user)
    rows = await _fetch_rows(db, SQL_EXPORT_SIGNALS, topic_id, limit)
    if not rows:
        raise HTTPException(status_code=404, detail="No signals found for this topic")

    data = _rows_to_csv(rows, SIGNAL_COLUMNS) if format == "csv" else _rows_to_json(rows)
    log.info("export.signals", topic_id=topic_id, format=format, rows=len(rows))
    await audit_db.log_action(
        db, user["sub"], "export.signals", "topic", topic_id,
        {"format": format, "rows": len(rows)},
        request.client.host if request.client else "",
    )
    return _make_response(data, format, f"anveshak_signals_{topic_id[:8]}")


@router.get("/entities")
async def export_entities(
    request: Request,
    topic_id: str = Query(..., description="Topic ID to export"),
    format: str = Query("csv", pattern="^(csv|json)$", description="Export format"),
    limit: int = Query(5000, ge=1, le=MAX_EXPORT_ROWS, description="Max rows"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Export extracted entities for a topic as CSV or JSON."""
    await topics_db.verify_topic_access(db, topic_id, user)
    rows = await _fetch_rows(db, SQL_EXPORT_ENTITIES, topic_id, limit)
    if not rows:
        raise HTTPException(status_code=404, detail="No entities found for this topic")

    data = _rows_to_csv(rows, ENTITY_COLUMNS) if format == "csv" else _rows_to_json(rows)
    log.info("export.entities", topic_id=topic_id, format=format, rows=len(rows))
    await audit_db.log_action(
        db, user["sub"], "export.entities", "topic", topic_id,
        {"format": format, "rows": len(rows)},
        request.client.host if request.client else "",
    )
    return _make_response(data, format, f"anveshak_entities_{topic_id[:8]}")
