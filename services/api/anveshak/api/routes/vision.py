"""Vision analysis API routes.

Criteria:
  4.25–4.27: pHash reverse lookup endpoint
  4.28:      POST /api/v1/vision/analyse — multipart upload → ARQ job → job_id
  4.29:      GET  /api/v1/vision/jobs/{job_id} — poll status + results
  4.30:      GET  /api/v1/content/{id}/vision — all vision_results for a content_item
  4.31:      GET  /api/v1/media/{asset_id} — serve media file for frontend display

All heavy ML work dispatched as ARQ jobs (CLAUDE.md rule 5: never block routes).
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

import asyncpg
import structlog
from arq import ArqRedis
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from ..auth.rbac import require_role
from ..db.pool import get_db
from ..db import vision as vision_db
from ..db import topics as topics_db
from ..settings import settings

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/vision", tags=["vision"])

_IMG_EXTS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"})
_VID_EXTS: frozenset[str] = frozenset({".mp4", ".avi", ".mov", ".webm", ".mkv"})


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_arq_pool(request: Request) -> ArqRedis:
    """Inject ARQ pool from app state (wired in main.py lifespan)."""
    return request.app.state.arq_pool


# ---------------------------------------------------------------------------
# POST /api/v1/vision/analyse
# ---------------------------------------------------------------------------

@router.post("/analyse")
async def analyse_image(
    request: Request,
    file: UploadFile = File(...),
    content_item_id: Optional[str] = Query(
        None,
        description="Associate upload with an existing content_item (optional for ad-hoc analysis)",
    ),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Accept image/video upload → store to disk → dispatch ARQ job.

    Criteria 4.28: multipart upload → ARQ job dispatched → returns {job_id}.
    Never blocks — job processes in background, poll GET /jobs/{job_id}.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file upload")

    max_bytes = settings.vision_max_video_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {settings.vision_max_video_size_mb}MB.",
        )

    # Hash + store file directly (no vision service proxy needed)
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    filename = file.filename or "upload.bin"
    ext = Path(filename).suffix.lower() or ".jpg"

    now = datetime.now(UTC)
    storage_path_obj = (
        Path(settings.media_storage_root)
        / "media"
        / "uploads"
        / now.strftime("%Y")
        / now.strftime("%m")
        / now.strftime("%d")
        / f"{content_hash}{ext}"
    )
    storage_path_obj.parent.mkdir(parents=True, exist_ok=True)
    storage_path_obj.write_bytes(file_bytes)

    if ext in _IMG_EXTS:
        asset_type = "image"
    elif ext in _VID_EXTS:
        asset_type = "video"
    else:
        asset_type = "document"

    storage_path: str = str(storage_path_obj)
    log.info(
        "vision_api.upload_stored",
        content_hash=content_hash,
        asset_type=asset_type,
        size_bytes=len(file_bytes),
    )

    # Resolve content_item_id — required FK on media_assets.
    # For ad-hoc uploads (no existing content_item) create a stub so the FK is satisfied.
    resolved_content_item_id = content_item_id or await vision_db.get_or_create_stub_content_item(
        db, content_hash, file.filename or "upload",
    )

    # Upsert media_assets row with ON CONFLICT(content_hash) DO NOTHING (criteria 4.34 dedup)
    existing = await vision_db.get_media_asset_by_hash(db, content_hash)
    if existing:
        media_asset_id = existing["id"]
    else:
        new_id = str(uuid.uuid4())
        row = await vision_db.insert_media_asset(
            db, new_id, resolved_content_item_id, asset_type, storage_path, content_hash,
        )
        # RETURNING id → None if conflict (shouldn't happen, but guard anyway)
        media_asset_id = row["id"] if row else new_id

    # Dispatch ARQ vision job (CLAUDE.md rule 5: never call ML inline)
    arq_pool: ArqRedis = get_arq_pool(request)
    job = await arq_pool.enqueue_job("run_vision_analysis", media_asset_id, _queue_name="arq:vision")

    log.info(
        "vision_api.job_dispatched",
        job_id=job.job_id,
        media_asset_id=media_asset_id,
        asset_type=asset_type,
    )
    return {
        "job_id": job.job_id,
        "media_asset_id": media_asset_id,
        "asset_type": asset_type,
        "status": "queued",
    }


# ---------------------------------------------------------------------------
# POST /api/v1/vision/analyse-youtube
# ---------------------------------------------------------------------------

@router.post("/analyse-youtube")
async def analyse_youtube_video(
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Accept YouTube video URL → dispatch download + vision analysis as ARQ job.

    On-demand only — not automatic. Downloads video via yt-dlp, stores as media_asset,
    enqueues run_vision_analysis for keyframe deepfake detection.
    """
    body = await request.json()
    video_url = body.get("video_url", "")
    content_item_id = body.get("content_item_id")

    if not video_url or "youtube.com" not in video_url and "youtu.be" not in video_url:
        raise HTTPException(status_code=400, detail="Valid YouTube URL required")

    arq_pool: ArqRedis = get_arq_pool(request)
    job = await arq_pool.enqueue_job(
        "download_and_analyse_youtube",
        video_url,
        content_item_id,
        _queue_name="arq:vision",
    )

    log.info(
        "vision_api.youtube_job_dispatched",
        job_id=job.job_id,
        video_url=video_url,
    )
    return {
        "job_id": job.job_id,
        "status": "queued",
    }


# ---------------------------------------------------------------------------
# GET /api/v1/vision/jobs/recent
# ---------------------------------------------------------------------------

@router.get("/jobs/recent")
async def list_recent_vision_jobs(
    limit: int = Query(10, ge=1, le=50),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Return the last N completed vision analysis jobs for history display."""
    rows = await db.fetch(
        """SELECT id, status, result, created_at
           FROM analysis_jobs
           WHERE job_type = 'vision_analysis' AND status = 'completed'
           ORDER BY created_at DESC
           LIMIT $1""",
        limit,
    )
    jobs = []
    for r in rows:
        result = r["result"] or {}
        if isinstance(result, str):
            import json as _json
            try:
                result = _json.loads(result)
            except Exception:
                result = {}
        yolo = result.get("yolo_detections") or []
        jobs.append({
            "job_id": r["id"],
            "deepfake_score": result.get("deepfake_score"),
            "yolo_count": len(yolo) if isinstance(yolo, list) else 0,
            "clip_top": max(result.get("clip_labels", {}).items(), key=lambda x: x[1], default=("", 0))[0] if result.get("clip_labels") else None,
            "status": r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        })
    return jobs


# ---------------------------------------------------------------------------
# GET /api/v1/vision/jobs/{job_id}
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}")
async def get_vision_job(
    job_id: str,
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Poll vision job status. Returns results when complete.

    Criteria 4.29: returns job status + results when complete.
    Checks ARQ Redis first for in-flight jobs, then falls back to
    analysis_jobs DB table (authoritative for completed jobs).
    """
    from arq.jobs import Job, JobStatus

    arq_pool: ArqRedis = get_arq_pool(request)
    job = Job(job_id, arq_pool, _queue_name="arq:vision")

    status = await job.status()

    # ARQ Redis found the job — return from Redis
    if status != JobStatus.not_found:
        result = None
        error = None
        if status == JobStatus.complete:
            try:
                info = await job.result_info()
                if info:
                    if info.success:
                        result = info.result
                    else:
                        error = str(info.result)
            except Exception:
                pass
        return {
            "job_id": job_id,
            "status": status.value,
            "result": result,
            "error": error,
        }

    # Fallback: analysis_jobs DB is authoritative for completed jobs
    # (ARQ keys expire from Redis but DB rows persist)
    row = await db.fetchrow(
        "SELECT status, result, error FROM analysis_jobs WHERE id = $1",
        job_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job_id,
        "status": row["status"],
        "result": row["result"],
        "error": row["error"],
    }


# ---------------------------------------------------------------------------
# GET /api/v1/vision/reverse-search
# ---------------------------------------------------------------------------

@router.get("/reverse-search")
async def reverse_image_search(
    phash: str = Query(..., description="Perceptual hash (16 hex chars, 64-bit)"),
    threshold: Optional[int] = Query(
        None,
        description="Max Hamming distance (default from settings)",
    ),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Find near-duplicate media assets by pHash Hamming distance.

    Criteria 4.25–4.27: threshold from settings.phash_duplicate_threshold (never hardcoded).
    SQL: BIT_COUNT(phash # query_phash) <= threshold
    """
    try:
        phash_int = int(phash, 16)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid phash. Must be 16 hex characters (64-bit integer).",
        )

    effective_threshold = (
        threshold if threshold is not None else settings.phash_duplicate_threshold
    )

    rows = await vision_db.phash_reverse_search(db, phash_int, effective_threshold)
    return [
        {
            "media_asset_id": r["id"],
            "content_item_id": r["content_item_id"],
            "asset_type": r["asset_type"],
            "content_hash": r["content_hash"],
            "url": r["url"],
            "topic_id": r["topic_id"],
            "hamming_distance": r["hamming_distance"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /api/v1/content/{id}/vision  (separate router, mounted at /api/v1/content)
# ---------------------------------------------------------------------------

content_vision_router = APIRouter(prefix="/api/v1/content", tags=["vision"])


@content_vision_router.get("/{content_id}/vision")
async def get_vision_for_content(
    content_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """All vision_results for all media assets linked to a content_item.

    Criteria 4.30.
    deepfake_score is always float (CLAUDE.md rule 7 — never bool).
    """
    rows = await vision_db.get_vision_results_for_content(db, content_id)
    return [
        {
            "vision_result_id": r["id"],
            "media_asset_id": r["media_asset_id"],
            "yolo_detections": r["yolo_detections"],
            "clip_labels": r["clip_labels"],
            "deepfake_score": r["deepfake_score"],           # float 0.0–1.0 or null (analysis failed)
            "deepfake_model": r["deepfake_model"],
            "synthetic_probability": r["synthetic_probability"],
            "processed_at": r["processed_at"],
            "asset_type": r["asset_type"],
            "exif_data": r["exif_data"],
            "phash": hex(r["phash"]) if r["phash"] is not None else None,
            "content_hash": r["content_hash"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /api/v1/media/{asset_id} — serve media file for frontend display
# ---------------------------------------------------------------------------

SQL_GET_MEDIA_ASSET_PATH = """
    SELECT ma.storage_path, ma.asset_type, ma.content_hash,
           ci.topic_id
    FROM media_assets ma
    JOIN content_items ci ON ci.id = ma.content_item_id
    WHERE ma.id = $1
"""


@content_vision_router.get("/media/{asset_id}")
async def serve_media(
    asset_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Serve a media asset file for frontend display.

    Auth required — verifies user has access via JWT.
    Returns the image/video file with correct content-type.
    """
    row = await db.fetchrow(SQL_GET_MEDIA_ASSET_PATH, asset_id)
    if not row:
        raise HTTPException(status_code=404, detail="Media asset not found")

    # Org isolation: verify user has access to the topic owning this media
    await topics_db.verify_topic_access(db, row["topic_id"], user)

    storage_path = Path(row["storage_path"])
    if not storage_path.is_file():
        log.warning("media.serve.file_missing", asset_id=asset_id, path=str(storage_path))
        raise HTTPException(status_code=404, detail="Media file not found on disk")

    content_type = mimetypes.guess_type(str(storage_path))[0] or "application/octet-stream"
    return FileResponse(
        path=str(storage_path),
        media_type=content_type,
        filename=f"{row['content_hash']}{storage_path.suffix}",
    )
