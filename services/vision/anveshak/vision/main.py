"""Anveshak Vision Service — FastAPI application.

Exposes:
  GET  /health              — service health check
  POST /analyse             — direct image upload (proxied by API gateway)

The heavy ML pipeline (YOLO, deepfake, CLIP) runs in the ARQ worker (jobs.py).
This FastAPI app handles health + direct-upload file storage only.
"""
from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from arq import create_pool as arq_create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, File, HTTPException, UploadFile
from prometheus_client import make_asgi_app

from .db import create_pool
from .metrics import REGISTRY as VISION_REGISTRY
from .settings import settings

log = structlog.get_logger(__name__)

_IMG_EXTS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"})
_VID_EXTS: frozenset[str] = frozenset({".mp4", ".avi", ".mov", ".webm", ".mkv"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await create_pool()
    app.state.arq_pool = await arq_create_pool(
        RedisSettings.from_dsn(settings.redis_url)
    )
    log.info(
        "anveshak_vision.ready",
        device=settings.vision_device,
        yolo_model=settings.yolo_model_size,
        deepfake_image_model=settings.vision_deepfake_image_model,
        deepfake_video_model=settings.vision_deepfake_video_model,
    )
    yield
    await app.state.db_pool.close()
    await app.state.arq_pool.close()
    log.info("anveshak_vision.stopped")


app = FastAPI(
    title="Anveshak Vision Service",
    version="1.0.0",
    lifespan=lifespan,
)

# 8A.17 — Prometheus metrics endpoint (uses service-isolated registry, 8A.18)
app.mount("/metrics", make_asgi_app(registry=VISION_REGISTRY))


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "anveshak-vision",
        "device": settings.vision_device,
        "yolo_model": settings.yolo_model_size,
        "deepfake_image_model": settings.vision_deepfake_image_model,
        "deepfake_video_model": settings.vision_deepfake_video_model,
        "clip_model": settings.clip_model_name,
    }


@app.post("/analyse")
async def analyse_upload(file: UploadFile = File(...)):
    """Accept multipart image/video upload, store to disk, dispatch ARQ job.

    Called by api/routes/vision.py which passes the content_item context.
    Returns the storage metadata so the API can create the media_assets DB row.

    Criteria 4.28: multipart upload → store → job dispatch happens in api route.
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file upload")

    max_bytes = settings.vision_max_video_size_mb * 1024 * 1024
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {settings.vision_max_video_size_mb}MB.",
        )

    content_hash = hashlib.sha256(image_bytes).hexdigest()
    filename = file.filename or "upload.bin"
    ext = Path(filename).suffix.lower() or ".jpg"

    from datetime import datetime, UTC
    now = datetime.now(UTC)
    storage_path = (
        settings.media_storage_root
        / "media"
        / "uploads"
        / now.strftime("%Y")
        / now.strftime("%m")
        / now.strftime("%d")
        / f"{content_hash}{ext}"
    )
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(image_bytes)

    if ext in _IMG_EXTS:
        asset_type = "image"
    elif ext in _VID_EXTS:
        asset_type = "video"
    else:
        asset_type = "document"

    log.info(
        "vision.upload.stored",
        content_hash=content_hash,
        asset_type=asset_type,
        size_bytes=len(image_bytes),
    )
    return {
        "content_hash": content_hash,
        "storage_path": str(storage_path),
        "asset_type": asset_type,
        "file_size_bytes": len(image_bytes),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)  # nosec B104 — containerized service must bind all interfaces; network isolation enforced by Docker/k3s
