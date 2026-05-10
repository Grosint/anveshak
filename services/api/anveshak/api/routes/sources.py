"""Source management endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import Optional

from urllib.parse import urlparse

import asyncpg
import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from ..auth.rbac import require_role
from ..db import sources as sources_db
from ..db import audit as audit_db
from ..db.pool import get_db

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])
log = structlog.get_logger(__name__)

_LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# Only strong paywall indicators — "subscribe" triggers false positives on
# virtually every news site (nav-bar / footer links).
_PAYWALL_PATTERNS = {"paywall", "premium content", "sign in to read", "create an account", "subscribers only"}


class CreateSourceRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str
    url_or_handle: str
    platform: str  # web|telegram|twitter|reddit|bluesky|rss|upload|darkweb
    credibility_score: float = 50.0
    topic_id: Optional[str] = None  # if provided, auto-link source to this topic
    topic_ids: Optional[list[str]] = None  # link to multiple topics at creation


# ---------------------------------------------------------------------------
# Lightweight health probe — used at registration and manual re-check
# ---------------------------------------------------------------------------

async def _probe_rss(url: str) -> tuple[bool, Optional[str]]:
    """Returns (ok, error_message). Hard check — RSS must return 200 + XML."""
    try:
        async with httpx.AsyncClient(
            timeout=15, follow_redirects=True,
            headers={"User-Agent": _BROWSER_UA},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "")
            if not any(k in ct for k in ("xml", "rss", "atom")):
                # Some feeds serve as text/plain — also accept non-empty body starting with XML
                body = resp.text.lstrip()
                if not body.startswith("<?xml") and not body.startswith("<rss") and not body.startswith("<feed"):
                    return False, f"URL returned content-type '{ct}' — does not look like an RSS/Atom feed"
            return True, None
    except httpx.HTTPStatusError as exc:
        return False, f"HTTP {exc.response.status_code}"
    except Exception as exc:
        return False, str(exc)


async def _probe_web(url: str) -> tuple[str, Optional[str], bool]:
    """Returns (health_status, error_message, hard_failure).

    Soft warnings (paywall heuristic, short content) return hard_failure=False
    so they don't accumulate toward 'down' status.
    """
    try:
        async with httpx.AsyncClient(
            timeout=15, follow_redirects=True,
            headers={"User-Agent": _BROWSER_UA},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text.lower()
            if any(p in text for p in _PAYWALL_PATTERNS):
                return "degraded", "Possible paywall detected — content may be incomplete", False
            if len(resp.text) < 200:
                return "degraded", f"Response too short ({len(resp.text)} chars) — may be blocked", True
            return "healthy", None, False
    except httpx.HTTPStatusError as exc:
        return "degraded", f"HTTP {exc.response.status_code}", True
    except Exception as exc:
        return "degraded", str(exc), True


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_source(
    req: CreateSourceRequest,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    initial_health = "unverified"
    health_error: Optional[str] = None
    warning: Optional[str] = None

    if req.platform == "rss":
        ok, err = await _probe_rss(req.url_or_handle)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"RSS feed not reachable: {err}",
            )
        initial_health = "healthy"

    elif req.platform == "web":
        health_status, err, _hard = await _probe_web(req.url_or_handle)
        initial_health = health_status
        if err:
            health_error = err
            warning = err

    elif req.platform == "darkweb":
        # Validate .onion URL format — API cannot probe (no Tor access)
        parsed = urlparse(req.url_or_handle)
        if not parsed.netloc.endswith(".onion"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Dark web sources must use .onion URLs",
            )
        if parsed.scheme not in ("http", "https"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Dark web sources must use http:// or https:// scheme",
            )
        initial_health = "unverified"  # health checked by scraper via Tor

    source_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    await sources_db.insert_source(
        db, source_id, req.name, req.url_or_handle, req.platform,
        req.credibility_score, now, _LABELS_JSON,
    )
    # Write initial health status
    await sources_db.update_source_health(db, source_id, initial_health, 0, health_error, now)

    # Auto-link to topic(s) if provided
    link_ids: set[str] = set()
    if req.topic_id:
        link_ids.add(req.topic_id)
    if req.topic_ids:
        link_ids.update(req.topic_ids)
    for tid in link_ids:
        await sources_db.add_topic_source(db, tid, source_id)

    log.info(
        "sources.created",
        source_id=source_id,
        platform=req.platform,
        health=initial_health,
    )
    await audit_db.log_action(
        db, user["sub"], "source.create", "source", source_id,
        {"name": req.name, "platform": req.platform},
        request.client.host if request.client else "",
    )
    result: dict = {"id": source_id, "name": req.name, "health_status": initial_health}
    if warning:
        result["warning"] = warning
    return result


@router.get("")
async def list_sources(
    credibility_below: float | None = None,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    if credibility_below is not None:
        return await sources_db.list_sources_below(db, credibility_below)
    return await sources_db.list_sources(db)


@router.post("/{source_id}/check-health", status_code=status.HTTP_200_OK)
async def check_source_health(
    source_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Trigger an immediate health probe for one source. Updates health_status in DB."""
    source = await sources_db.get_source_for_health(db, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    platform: str = source["platform"]
    url: str = source["url_or_handle"]
    prev_failures: int = source["consecutive_failures"]
    now = datetime.now(UTC)

    if platform == "rss":
        ok, err = await _probe_rss(url)
        if ok:
            health_status, failures, health_error = "healthy", 0, None
        else:
            failures = prev_failures + 1
            health_status = "down" if failures >= 3 else "degraded"
            health_error = err

    elif platform == "web":
        health_status, err, hard_failure = await _probe_web(url)
        if health_status == "healthy":
            failures, health_error = 0, None
        elif not hard_failure:
            # Soft warning (paywall heuristic) — don't increment failure counter
            failures = prev_failures
            health_error = err
        else:
            failures = prev_failures + 1
            health_status = "down" if failures >= 3 else "degraded"
            health_error = err

    elif platform == "darkweb":
        # Dark web sources are probed by the scraper service via Tor, not by the API
        health_status, failures, health_error = "unverified", prev_failures, \
            "Dark web health checks run via scraper service (Tor proxy)"

    else:
        # telegram/x/reddit — not HTTP-probeable from API; mark as unverified
        health_status, failures, health_error = "unverified", 0, None

    await sources_db.update_source_health(db, source_id, health_status, failures, health_error, now)
    log.info("sources.health_checked", source_id=source_id, status=health_status)
    return {
        "source_id": source_id,
        "health_status": health_status,
        "consecutive_failures": failures,
        "health_error": health_error,
        "checked_at": now.isoformat(),
    }


@router.patch("/{source_id}/credibility")
async def update_credibility(
    source_id: str,
    new_score: float,
    reason: str,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Update source credibility — always audit-logged."""
    old_score = await sources_db.get_source_score(db, source_id)
    if old_score is None:
        raise HTTPException(status_code=404, detail="Source not found")

    now = datetime.now(UTC)
    async with db.transaction():
        await sources_db.update_credibility(
            db, source_id, str(uuid.uuid4()),
            old_score, new_score, reason,
            f"user:{user['sub']}", now, _LABELS_JSON,
        )
    await audit_db.log_action(
        db, user["sub"], "source.credibility_update", "source", source_id,
        {"old_score": old_score, "new_score": new_score, "reason": reason},
        request.client.host if request.client else "",
    )
    return {"source_id": source_id, "old_score": old_score, "new_score": new_score}


@router.patch("/{source_id}/active")
async def toggle_source_active(
    source_id: str,
    is_active: bool,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    if not await sources_db.source_exists(db, source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    await sources_db.toggle_source_active(db, source_id, is_active, datetime.now(UTC))
    return {"source_id": source_id, "is_active": is_active}


@router.get("/{source_id}/report-warnings/count")
async def get_report_warnings_count(
    source_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    if not await sources_db.source_exists(db, source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    count = await sources_db.count_report_warnings(db, source_id)
    return {"source_id": source_id, "warning_count": count}


class UpdateSourceRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    name: Optional[str] = None
    url_or_handle: Optional[str] = None


@router.patch("/{source_id}")
async def update_source(
    source_id: str,
    req: UpdateSourceRequest,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Update source name and/or URL. Both fields are optional (patch semantics)."""
    if not await sources_db.source_exists(db, source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    if req.name is None and req.url_or_handle is None:
        raise HTTPException(status_code=422, detail="At least one field must be provided")
    now = datetime.now(UTC)
    await sources_db.update_source_fields(db, source_id, req.name, req.url_or_handle, now)
    log.info("sources.updated", source_id=source_id)
    return {"source_id": source_id, "name": req.name, "url_or_handle": req.url_or_handle}


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    request: Request,
    force: bool = False,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Delete a source. Returns 409 if content items exist unless force=true."""
    if not await sources_db.source_exists(db, source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    content_count = await sources_db.count_content_items_for_source(db, source_id)
    if content_count > 0 and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source has {content_count} content item(s). Use force=true to delete anyway.",
        )
    await sources_db.delete_source(db, source_id)
    await audit_db.log_action(
        db, user["sub"], "source.delete", "source", source_id,
        {"force": force, "content_items_removed": content_count},
        request.client.host if request.client else "",
    )
    log.info("sources.deleted", source_id=source_id, content_items_removed=content_count)


@router.get("/{source_id}/audit-log")
async def get_audit_log(
    source_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    if not await sources_db.source_exists(db, source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    return await sources_db.get_audit_log(db, source_id)
