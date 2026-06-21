"""Vision ARQ worker — image/video analysis jobs.

Entry point: arq anveshak.vision.jobs.WorkerSettings

Criteria:
  4.7–4.11:  YOLO detection, label tagging
  4.12–4.16: Face deepfake detection (FacetorchDetector)
  4.17–4.21: Non-face deepfake + video keyframe analysis
  4.22–4.24: CLIP classification
  4.31–4.34: Data flow assertions (integration tests verify these)
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

import arq
import asyncpg
import structlog
from arq.connections import RedisSettings

from .metrics import vision_analyses_total, vision_analysis_duration_seconds, vision_deepfake_score, arq_jobs_failed_total

from .db import (
    clear_media_storage_path,
    create_pool,
    get_expired_media_assets,
    get_media_asset,
    get_topic_clip_categories,
    insert_vision_result,
    tag_content_item,
    update_media_asset_exif_phash,
)
from .detectors import get_deepfake_detector
from .detectors.clip_detector import CLIPClassifier
from .detectors.yolo_detector import YOLODetector
from .media_store import (
    compute_phash,
    extract_exif,
    is_video_path,
    read_media_bytes,
)
from .settings import settings
from .video import extract_keyframes, worst_case_score

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons — loaded once per worker process, reused across jobs
# ---------------------------------------------------------------------------

import threading

# Serializes GPU-bound inference to prevent concurrent CUDA kernel conflicts
_inference_semaphore = asyncio.Semaphore(1)

_yolo_detector: Optional[YOLODetector] = None
_deepfake_image_detector = None
_deepfake_video_detector = None
_clip_classifier: Optional[CLIPClassifier] = None

_yolo_lock = threading.Lock()
_deepfake_image_lock = threading.Lock()
_deepfake_video_lock = threading.Lock()
_clip_lock = threading.Lock()


def _get_yolo() -> YOLODetector:
    global _yolo_detector
    if _yolo_detector is None:
        with _yolo_lock:
            if _yolo_detector is None:  # double-checked locking
                _yolo_detector = YOLODetector()
    return _yolo_detector


def _get_deepfake_image_detector():
    global _deepfake_image_detector
    if _deepfake_image_detector is None:
        with _deepfake_image_lock:
            if _deepfake_image_detector is None:
                _deepfake_image_detector = get_deepfake_detector(
                    settings.vision_deepfake_image_model, settings.vision_device
                )
    return _deepfake_image_detector


def _get_deepfake_video_detector():
    global _deepfake_video_detector
    if _deepfake_video_detector is None:
        with _deepfake_video_lock:
            if _deepfake_video_detector is None:
                _deepfake_video_detector = get_deepfake_detector(
                    settings.vision_deepfake_video_model, settings.vision_device
                )
    return _deepfake_video_detector


def _get_clip() -> CLIPClassifier:
    global _clip_classifier
    if _clip_classifier is None:
        with _clip_lock:
            if _clip_classifier is None:
                _clip_classifier = CLIPClassifier()
    return _clip_classifier


# ---------------------------------------------------------------------------
# Main ARQ job
# ---------------------------------------------------------------------------

async def run_vision_analysis(ctx: dict, media_asset_id: str) -> dict:
    """Full vision analysis pipeline for one media asset.

    Dispatched by:
    - scraper/jobs.py after media download (criteria 4.1)
    - social/ingest.py after media download (criteria 4.2)
    - api/routes/vision.py for manual uploads (criteria 4.28)

    Returns a summary dict with deepfake_score and detection counts.
    The ARQ job result is stored in Redis and polled by GET /vision/jobs/{job_id}.
    """
    pool: asyncpg.Pool = ctx["db_pool"]

    async with pool.acquire() as conn:
        asset = await get_media_asset(conn, media_asset_id)
        if not asset:
            log.warning("vision.job.asset_not_found", media_asset_id=media_asset_id)
            return {"error": "media_asset_not_found", "media_asset_id": media_asset_id}

        topic_id: str = asset["topic_id"]
        content_item_id: str = asset["content_item_id"]
        storage_path: str = asset["storage_path"]

        # STEP 1: Load bytes
        try:
            image_bytes = await asyncio.to_thread(read_media_bytes, storage_path)
        except FileNotFoundError as exc:
            log.error("vision.job.file_missing", path=storage_path, error=str(exc))
            return {"error": "file_not_found", "path": storage_path}

        is_video = is_video_path(storage_path)

        # STEP 2: EXIF + pHash (criteria 4.5, 4.6)
        exif_data: dict = {}
        phash_val: Optional[int] = None
        if not is_video:
            exif_data = await asyncio.to_thread(
                extract_exif, image_bytes, settings.exif_backend
            ) or {}
            phash_val = await asyncio.to_thread(compute_phash, image_bytes)

        await update_media_asset_exif_phash(conn, media_asset_id, exif_data, phash_val)

        # STEP 3: YOLO detection (criteria 4.7–4.11)
        yolo_detections: list[dict] = []
        high_interest: list[str] = []
        if not is_video:
            try:
                yolo = _get_yolo()
                detections = await asyncio.to_thread(yolo.detect, image_bytes)
                yolo_detections = yolo.to_jsonb(detections)
                high_interest = yolo.high_interest_labels(detections)
            except Exception as exc:
                log.warning("vision.yolo.failed", media_asset_id=media_asset_id, error=str(exc))

        # STEP 4: Deepfake detection (criteria 4.12–4.21)
        deepfake_score: float | None = None
        deepfake_model_name: str = ""
        synthetic_probability: Optional[float] = None

        if is_video:
            deepfake_score, deepfake_model_name = await _analyse_video(
                storage_path, media_asset_id
            )
        else:
            deepfake_score, deepfake_model_name = await _analyse_image(
                image_bytes, media_asset_id
            )
            synthetic_probability = deepfake_score  # same score for image

        # STEP 5: CLIP classification (criteria 4.22–4.24)
        clip_labels: list[dict] = []
        if topic_id and not is_video:
            try:
                categories = await get_topic_clip_categories(conn, topic_id)
                if categories:
                    clip = _get_clip()
                    clip_results = await asyncio.to_thread(
                        clip.classify, image_bytes, categories
                    )
                    clip_labels = clip.to_jsonb(clip_results)
            except Exception as exc:
                log.warning("vision.clip.failed", media_asset_id=media_asset_id, error=str(exc))

        # STEP 6: Persist vision_results (criteria 4.32)
        await insert_vision_result(
            conn=conn,
            media_asset_id=media_asset_id,
            yolo_detections=yolo_detections,
            clip_labels=clip_labels,
            deepfake_score=deepfake_score,          # float 0.0–1.0 or None on error (CLAUDE.md rule 7)
            deepfake_model=deepfake_model_name,
            synthetic_probability=synthetic_probability,
        )

        # STEP 7: Tag content_items.labels with high-interest YOLO detections (criteria 4.11)
        if high_interest:
            extra_labels = {"yolo_detections": high_interest}
            await tag_content_item(conn, content_item_id, extra_labels)
            log.info(
                "vision.content_tagged",
                content_item_id=content_item_id,
                labels=high_interest,
            )

        # STEP 8: Log deepfake risk if above threshold (criteria 4.33)
        # Note: actual credibility downgrade is handled by analyst/credibility.py
        # which queries vision_results JOIN media_assets JOIN content_items.
        # No direct call needed here — Phase 2 loop handles it.
        if deepfake_score is not None and deepfake_score > settings.deepfake_high_risk_threshold:
            log.warning(
                "vision.deepfake_high_risk",
                media_asset_id=media_asset_id,
                score=deepfake_score,
                model=deepfake_model_name,
                hint="Credibility auto-downgrade will fire on next analyst loop cycle.",
            )

    # 8A.10–8A.12 — increment vision metrics
    vision_analyses_total.labels(
        analysis_type="deepfake_video" if is_video else "deepfake_face"
    ).inc()
    if yolo_detections:
        vision_analyses_total.labels(analysis_type="yolo").inc()
    if clip_labels:
        vision_analyses_total.labels(analysis_type="clip").inc()
    if deepfake_score is not None:
        vision_deepfake_score.observe(deepfake_score)

    result = {
        "media_asset_id": media_asset_id,
        "deepfake_score": deepfake_score,
        "deepfake_model": deepfake_model_name,
        "yolo_detections": len(yolo_detections),
        "clip_categories_matched": len(clip_labels),
        "high_interest_labels": high_interest,
        "is_video": is_video,
        "phash": phash_val,
    }
    log.info("vision.job.complete", **result)
    return result


async def _analyse_image(image_bytes: bytes, media_asset_id: str) -> tuple[float | None, str]:
    """Route image to face or non-face deepfake detector based on face presence."""
    try:
        face_detector = _get_deepfake_image_detector()
        # Check if image has faces — use face detector if so, general otherwise
        has_faces = await asyncio.to_thread(face_detector.has_faces, image_bytes)
        if has_faces:
            score = await asyncio.to_thread(face_detector.score, image_bytes)
            model_name = f"{settings.vision_deepfake_image_model}:face"
        else:
            video_detector = _get_deepfake_video_detector()
            score = await asyncio.to_thread(video_detector.score, image_bytes)
            model_name = f"{settings.vision_deepfake_video_model}:no_face"
        return score, model_name
    except Exception as exc:
        log.error(
            "vision.deepfake_image.failed",
            media_asset_id=media_asset_id,
            error=str(exc),
        )
        return None, "error"


async def _analyse_video(storage_path: str, media_asset_id: str) -> tuple[float | None, str]:
    """Extract keyframes and propagate worst-case deepfake score."""
    try:
        from pathlib import Path
        frames = await extract_keyframes(Path(storage_path))
        if not frames:
            log.error(
                "vision.deepfake_video.no_frames",
                media_asset_id=media_asset_id,
                storage_path=storage_path,
            )
            return None, "no_frames"

        video_detector = _get_deepfake_video_detector()
        frame_scores: list[float] = []
        for frame_bytes in frames:
            score = await asyncio.to_thread(video_detector.score, frame_bytes)
            frame_scores.append(score)

        score = worst_case_score(frame_scores)
        model_name = f"{settings.vision_deepfake_video_model}:video:{len(frames)}frames"
        log.info(
            "vision.video.analysed",
            frame_count=len(frames),
            worst_score=score,
        )
        return score, model_name
    except Exception as exc:
        log.error(
            "vision.deepfake_video.failed",
            media_asset_id=media_asset_id,
            error=str(exc),
        )
        return None, "error"


# ---------------------------------------------------------------------------
# Media retention cleanup
# ---------------------------------------------------------------------------

async def cleanup_expired_media(ctx: dict) -> dict:
    """Delete media files older than MEDIA_RETENTION_DAYS where vision analysis is complete.

    Runs as ARQ cron job. Files are deleted from disk; DB metadata (pHash, EXIF,
    deepfake_score) is preserved. storage_path is set to NULL to indicate deletion.
    Processes up to 100 files per run to avoid long-running transactions.
    """
    if settings.media_retention_days == 0:
        log.info("vision.cleanup.disabled", reason="MEDIA_RETENTION_DAYS=0")
        return {"skipped": "retention_disabled"}

    from datetime import datetime, timedelta, UTC
    from pathlib import Path

    cutoff = datetime.now(UTC) - timedelta(days=settings.media_retention_days)
    pool: asyncpg.Pool = ctx["db_pool"]
    deleted = 0
    errors = 0

    async with pool.acquire() as conn:
        rows = await get_expired_media_assets(conn, cutoff)
        for row in rows:
            storage_path = row["storage_path"]
            try:
                Path(storage_path).unlink(missing_ok=True)
                await clear_media_storage_path(conn, row["id"])
                deleted += 1
            except Exception as exc:
                errors += 1
                log.warning(
                    "vision.cleanup.file_error",
                    media_asset_id=row["id"],
                    path=storage_path,
                    error=str(exc),
                )

    log.info(
        "vision.cleanup.complete",
        cutoff_days=settings.media_retention_days,
        deleted=deleted,
        errors=errors,
        candidates=len(rows),
    )
    return {"deleted": deleted, "errors": errors, "candidates": len(rows)}


# ---------------------------------------------------------------------------
# ARQ worker lifecycle
# ---------------------------------------------------------------------------

async def on_startup(ctx: dict) -> None:
    ctx["db_pool"] = await create_pool()
    log.info(
        "vision_worker.ready",
        device=settings.vision_device,
        yolo_model=settings.yolo_model_size,
        deepfake_image=settings.vision_deepfake_image_model,
        deepfake_video=settings.vision_deepfake_video_model,
    )


async def on_shutdown(ctx: dict) -> None:
    await ctx["db_pool"].close()
    log.info("vision_worker.stopped")


async def on_job_result(ctx: dict, result) -> None:  # type: ignore[type-arg]
    """8A.19 — increment failure counter when an ARQ job exhausts all retries."""
    if getattr(result, "success", True) is False:
        job_name = getattr(result, "function", "unknown")
        arq_jobs_failed_total.labels(job_name=job_name).inc()
        log.warning("vision_worker.job_failed", job=job_name)


async def run_yolo(ctx: dict, media_asset_id: str) -> dict:
    """ARQ job: run YOLO object detection on a single media asset.

    Criteria 4.7: `run_yolo(media_asset_id: str)` ARQ function exists.
    Can be enqueued independently for parallel processing or re-analysis.
    Stores results in vision_results.yolo_detections and tags content_items.labels.
    """
    pool: asyncpg.Pool = ctx["db_pool"]

    async with pool.acquire() as conn:
        asset = await get_media_asset(conn, media_asset_id)
        if not asset:
            log.warning("vision.run_yolo.asset_not_found", media_asset_id=media_asset_id)
            return {"error": "media_asset_not_found"}

        storage_path: str = asset["storage_path"]
        content_item_id: str = asset["content_item_id"]

        try:
            image_bytes = await asyncio.to_thread(read_media_bytes, storage_path)
        except FileNotFoundError:
            log.error("vision.run_yolo.file_missing", path=storage_path)
            return {"error": "file_not_found"}

        if is_video_path(storage_path):
            return {"skipped": "video_not_supported_for_yolo_only_mode"}

        yolo = _get_yolo()
        detections = await asyncio.to_thread(yolo.detect, image_bytes)
        yolo_detections = yolo.to_jsonb(detections)
        high_interest = yolo.high_interest_labels(detections)

        # Upsert yolo_detections into vision_results
        import json
        await conn.execute("""
            INSERT INTO vision_results (id, media_asset_id, yolo_detections, labels)
            VALUES ($1, $2, $3::jsonb,
                    '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
            ON CONFLICT (media_asset_id) DO UPDATE
            SET yolo_detections = EXCLUDED.yolo_detections
        """, str(__import__("uuid").uuid4()), media_asset_id, json.dumps(yolo_detections))

        if high_interest:
            await tag_content_item(conn, content_item_id, {"yolo_detections": high_interest})

    log.info("vision.run_yolo.complete", media_asset_id=media_asset_id, count=len(yolo_detections))
    return {"media_asset_id": media_asset_id, "yolo_detections": len(yolo_detections),
            "high_interest_labels": high_interest}


async def run_clip(ctx: dict, media_asset_id: str, categories: list[str]) -> dict:
    """ARQ job: run CLIP classification on a single media asset.

    Criteria 4.22: `run_clip(media_asset_id: str, categories: list[str])` ARQ function exists.
    Can be enqueued independently when topic categories change or for re-classification.
    Criteria 4.23: categories parameter comes from topic.clip_categories.
    Criteria 4.24: results stored in vision_results.clip_labels JSONB.
    """
    pool: asyncpg.Pool = ctx["db_pool"]

    async with pool.acquire() as conn:
        asset = await get_media_asset(conn, media_asset_id)
        if not asset:
            log.warning("vision.run_clip.asset_not_found", media_asset_id=media_asset_id)
            return {"error": "media_asset_not_found"}

        if not categories:
            return {"skipped": "no_categories_provided"}

        storage_path: str = asset["storage_path"]
        if is_video_path(storage_path):
            return {"skipped": "video_not_supported_for_clip"}

        try:
            image_bytes = await asyncio.to_thread(read_media_bytes, storage_path)
        except FileNotFoundError:
            log.error("vision.run_clip.file_missing", path=storage_path)
            return {"error": "file_not_found"}

        clip = _get_clip()
        clip_results = await asyncio.to_thread(clip.classify, image_bytes, categories)
        clip_labels = clip.to_jsonb(clip_results)

        import json
        await conn.execute("""
            INSERT INTO vision_results (id, media_asset_id, clip_labels, labels)
            VALUES ($1, $2, $3::jsonb,
                    '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
            ON CONFLICT (media_asset_id) DO UPDATE
            SET clip_labels = EXCLUDED.clip_labels
        """, str(__import__("uuid").uuid4()), media_asset_id, json.dumps(clip_labels))

    log.info("vision.run_clip.complete", media_asset_id=media_asset_id,
             top_label=clip_labels[0]["label"] if clip_labels else None)
    return {"media_asset_id": media_asset_id, "clip_labels": clip_labels}


# ---------------------------------------------------------------------------
# YouTube video download + analyse (on-demand only)
# ---------------------------------------------------------------------------

async def download_and_analyse_youtube(
    ctx: dict, video_url: str, content_item_id: str | None = None
) -> dict:
    """Download YouTube video via yt-dlp, store as media_asset, run vision pipeline.

    On-demand only — triggered by analyst clicking "Analyse Video" button.
    Uses yt-dlp (lazy import, not in base deps). Max size from YOUTUBE_MAX_VIDEO_SIZE_MB.
    """
    import hashlib
    import uuid
    from pathlib import Path
    from datetime import datetime, UTC

    try:
        import yt_dlp
    except ImportError:
        log.error("vision.youtube.yt_dlp_not_installed",
                  hint="Install yt-dlp: pip install yt-dlp")
        return {"error": "yt-dlp not installed", "video_url": video_url}

    max_size_mb = settings.vision_max_video_size_mb
    now = datetime.now(UTC)
    dl_dir = Path(settings.media_storage_root) / "media" / "youtube" / now.strftime("%Y/%m/%d")
    dl_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = dl_dir / f"tmp_{uuid.uuid4().hex}"

    ydl_opts = {
        "format": "best[filesize<{}M]/best".format(max_size_mb),
        "outtmpl": str(tmp_path) + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "max_filesize": max_size_mb * 1024 * 1024,
    }

    try:
        log.info("vision.youtube.downloading", video_url=video_url)
        info = await asyncio.to_thread(lambda: _yt_download(ydl_opts, video_url))
    except Exception as exc:
        log.error("vision.youtube.download_failed", video_url=video_url, error=str(exc))
        return {"error": str(exc), "video_url": video_url}

    # Find downloaded file
    downloaded = None
    for f in dl_dir.glob(f"tmp_{tmp_path.name.split('_')[1]}*"):
        if f.is_file() and f.stat().st_size > 0:
            downloaded = f
            break

    if not downloaded:
        log.error("vision.youtube.file_not_found", video_url=video_url)
        return {"error": "Downloaded file not found", "video_url": video_url}

    # Hash and rename
    file_bytes = downloaded.read_bytes()
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    ext = downloaded.suffix or ".mp4"
    final_path = dl_dir / f"{content_hash}{ext}"
    downloaded.rename(final_path)

    log.info("vision.youtube.stored",
             content_hash=content_hash, size_mb=len(file_bytes) / (1024 * 1024))

    # Create media_asset and run vision
    pool = ctx.get("db_pool")
    if pool:
        async with pool.acquire() as conn:
            cid = content_item_id
            if not cid:
                from .db import get_or_create_stub_content_item
                cid = await get_or_create_stub_content_item(conn, content_hash, video_url)

            asset_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO media_assets (id, content_item_id, asset_type, storage_path, content_hash)
                   VALUES ($1, $2, 'video', $3, $4)
                   ON CONFLICT (content_hash) DO NOTHING""",
                asset_id, cid, str(final_path), content_hash,
            )

        # Chain to existing vision analysis
        return await run_vision_analysis(ctx, asset_id)

    return {"error": "no db_pool", "video_url": video_url}


def _yt_download(opts: dict, url: str) -> dict:
    """Blocking yt-dlp download — called via asyncio.to_thread."""
    import yt_dlp
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


class WorkerSettings:
    """ARQ worker entry point: arq anveshak.vision.jobs.WorkerSettings"""

    functions = [
        arq.func(run_vision_analysis, max_tries=2),  # idempotent via content_hash dedup
        arq.func(run_yolo, max_tries=2),
        arq.func(run_clip, max_tries=2),
        arq.func(download_and_analyse_youtube, max_tries=1),
    ]
    cron_jobs = [
        arq.cron(cleanup_expired_media, hour=3, minute=0),  # daily at 03:00 UTC
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    on_job_result = on_job_result
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    queue_name = "arq:vision"  # dedicated queue — avoids consuming scraper/social jobs
    max_jobs = 2     # vision is CPU-heavy — limit concurrency to avoid OOM
    job_timeout = 300  # 5 minutes max per job (handles slow CPU deepfake)
    keep_result = 3600  # 8C.6 — keep results 1h for UI polling
