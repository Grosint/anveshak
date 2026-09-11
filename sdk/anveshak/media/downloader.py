"""Media asset downloader — shared by scraper and social services.

Downloads bytes from a URL, stores to disk, computes content_hash.
EXIF extraction and pHash computation are deferred to the vision ARQ worker,
keeping this module free of heavy ML/image dependencies.

Criteria 4.1–4.4: download, store, hash.
Criteria 4.5–4.6 (EXIF, pHash): handled by vision/jobs.py.
"""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import structlog
from anveshak.net.safe_fetch import DEFAULT_MAX_REDIRECTS, fetch_bytes

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# MIME type → asset type mapping
# ---------------------------------------------------------------------------

_MIME_TO_ASSET_TYPE: dict[str, str] = {
    "image": "image",
    "video": "video",
    "application/pdf": "document",
}

_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".bmp",  # images
        ".mp4",
        ".avi",
        ".mov",
        ".webm",
        ".mkv",  # videos
        ".pdf",
    }  # documents
)


# mimetypes returns inconsistent results — normalise common cases
_NORMALISE: dict[str, str] = {
    ".jpeg": ".jpg",
    ".jpe": ".jpg",
    ".jfif": ".jpg",
}


@dataclass(frozen=True)
class MediaDownloadResult:
    """Result returned by download_media_asset on success."""

    content_hash: str  # SHA-256 of raw bytes
    storage_path: str  # absolute path where file was written
    asset_type: str  # image|video|document
    file_size_bytes: int
    original_url: str
    content_type: str  # MIME type from HTTP response


def _infer_asset_type(content_type: str, url: str) -> Optional[str]:
    """Infer asset type from MIME type or URL extension."""
    ct = content_type.split(";")[0].strip().lower()
    for prefix, atype in _MIME_TO_ASSET_TYPE.items():
        if ct.startswith(prefix):
            return atype
    # Fallback: infer from URL extension
    ext = Path(urlparse(url).path).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        return "image"
    if ext in {".mp4", ".avi", ".mov", ".webm", ".mkv"}:
        return "video"
    if ext == ".pdf":
        return "document"
    return None


def _storage_path(storage_root: Path, topic_id: str, content_hash: str, ext: str) -> Path:
    """Compute deterministic storage path: media/{topic_id}/{YYYY}/{MM}/{DD}/{hash}{ext}."""
    now = datetime.now(UTC)
    return (
        storage_root
        / "media"
        / topic_id
        / now.strftime("%Y")
        / now.strftime("%m")
        / now.strftime("%d")
        / f"{content_hash}{ext}"
    )


def _extension_from_content_type(content_type: str, url: str) -> str:
    """Determine file extension from MIME type or URL."""
    ct = content_type.split(";")[0].strip()
    ext = mimetypes.guess_extension(ct, strict=False)
    if ext:
        return _NORMALISE.get(ext, ext)
    # Fallback to URL extension
    url_ext = Path(urlparse(url).path).suffix.lower()
    return url_ext if url_ext in _SUPPORTED_EXTENSIONS else ".bin"


async def _handle_local_file(
    path_str: str,
    topic_id: str,
    storage_root: Path,
) -> Optional[MediaDownloadResult]:
    """Handle media already on disk (Telegram adapter, WhatsApp bridge).

    Validates path is inside media storage volume to prevent path traversal.
    Reads bytes, computes hash, copies to canonical storage path if needed.
    """
    local = Path(path_str)

    # SECURITY: validate path is inside media storage volume
    # storage_root is already the media volume root (e.g. /app/media)
    try:
        local.resolve().relative_to(storage_root.resolve())
    except ValueError:
        log.warning("media.local_path_outside_volume", path=path_str, allowed=str(storage_root))
        return None

    if not local.is_file():
        log.warning("media.local_file_not_found", path=path_str)
        return None

    data = await asyncio.to_thread(local.read_bytes)
    if not data:
        return None

    content_type = mimetypes.guess_type(path_str)[0] or "application/octet-stream"
    asset_type = _infer_asset_type(content_type, path_str)
    if asset_type is None:
        log.debug("media.local_unsupported_type", path=path_str, content_type=content_type)
        return None

    content_hash = hashlib.sha256(data).hexdigest()
    ext = local.suffix or ".bin"
    dest = _storage_path(storage_root, topic_id, content_hash, ext)

    if dest.resolve() != local.resolve():
        await asyncio.to_thread(_write_file, dest, data)

    log.info(
        "media.local_file_ingested",
        path=path_str,
        content_hash=content_hash,
        asset_type=asset_type,
        size_bytes=len(data),
    )
    return MediaDownloadResult(
        content_hash=content_hash,
        storage_path=str(dest),
        asset_type=asset_type,
        file_size_bytes=len(data),
        original_url=path_str,
        content_type=content_type,
    )


async def download_media_asset(
    url: str,
    topic_id: str,
    storage_root: Path,
    max_size_mb: int = 50,
    timeout_s: int = 30,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> Optional[MediaDownloadResult]:
    """Download a media asset from URL or read from local path, persist to disk.

    Handles both HTTP URLs (scraper) and local file paths (Telegram, WhatsApp).

    Returns None if:
    - HTTP fetch fails, is refused by the address guard, or names a host that
      is not external
    - The document runs past max_size_mb, measured as it is read rather than
      after the whole body is already resident
    - Content type is not a supported media type (image/video/document)
    - Local path is outside media storage volume (path traversal protection)

    Does NOT insert into DB — caller is responsible for the media_assets INSERT
    and enqueuing the vision ARQ job. This keeps the SDK free of DB dependencies.
    """
    # Local file path — pre-downloaded by adapter/bridge
    if url.startswith("/"):
        return await _handle_local_file(url, topic_id, storage_root)

    # A media URL is markup written by whoever we are collecting from, so the
    # destination is validated at every redirect hop rather than only at the
    # first, and the connection is made to the address that was validated.
    result = await fetch_bytes(
        url,
        timeout=timeout_s,
        headers={"User-Agent": "Mozilla/5.0 (compatible; Anveshak/1.0)"},
        max_redirects=max_redirects,
        limit=max_size_mb * 1024 * 1024,
    )
    if result is None:
        # safe_fetch logged which check refused and with what limit.
        log.warning("media.download_failed", url=url)
        return None

    content_type = result.headers.get("content-type", "application/octet-stream")
    asset_type = _infer_asset_type(content_type, url)
    if asset_type is None:
        log.debug("media.skipped_unsupported_type", url=url, content_type=content_type)
        return None

    data = result.body
    if not data:
        log.debug("media.empty_response", url=url)
        return None

    # Compute SHA-256 of raw bytes — the dedup key (criteria 4.4)
    content_hash = hashlib.sha256(data).hexdigest()

    ext = _extension_from_content_type(content_type, url)
    path = _storage_path(storage_root, topic_id, content_hash, ext)

    # Write to disk asynchronously (blocking I/O dispatched to thread pool)
    try:
        await asyncio.to_thread(_write_file, path, data)
    except Exception as exc:
        log.error("media.write_failed", path=str(path), error=str(exc))
        return None

    log.info(
        "media.downloaded",
        url=url,
        content_hash=content_hash,
        asset_type=asset_type,
        size_bytes=len(data),
        path=str(path),
    )
    return MediaDownloadResult(
        content_hash=content_hash,
        storage_path=str(path),
        asset_type=asset_type,
        file_size_bytes=len(data),
        original_url=url,
        content_type=content_type,
    )


def _write_file(path: Path, data: bytes) -> None:
    """Synchronous file write — called via asyncio.to_thread."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
