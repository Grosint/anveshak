"""Media asset file I/O and EXIF/pHash extraction.

Criteria 4.5: EXIF extracted via Pillow (or exiftool if EXIF_BACKEND=exiftool)
Criteria 4.6: pHash computed using imagehash library (bigint stored in DB)
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
from pathlib import Path
from typing import Optional

import structlog

from .settings import settings

log = structlog.get_logger(__name__)

# EXIF fields of intelligence interest — GPS, device info, AI software signatures
_EXIF_INTEREST_KEYS: frozenset[str] = frozenset({
    "GPSLatitude", "GPSLongitude", "GPSAltitude",
    "GPSDateStamp", "GPSTimeStamp",
    "Make", "Model",
    "Software",
    "DateTime", "DateTimeOriginal",
    "ImageDescription",
    "Artist", "Copyright",
})

# Software strings that suggest AI generation
_AI_SOFTWARE_SIGNATURES: tuple[str, ...] = (
    "stable diffusion", "midjourney", "dall-e", "dalle",
    "firefly", "runway", "pika", "gen-2", "imagen",
    "deepfake", "faceswap", "realesrgan",
)


def read_media_bytes(storage_path: str) -> bytes:
    """Read media bytes from disk. Raises FileNotFoundError if missing."""
    path = Path(storage_path)
    if not path.exists():
        raise FileNotFoundError(f"Media asset not found: {storage_path}")
    return path.read_bytes()


def compute_phash(image_bytes: bytes) -> Optional[int]:
    """Compute perceptual hash of an image.

    Returns integer representation of the pHash (stored as BIGINT in DB).
    Returns None if image cannot be decoded.

    Criteria 4.6: pHash for near-duplicate detection via Hamming distance.
    """
    try:
        import imagehash
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        h = imagehash.phash(img)
        # imagehash returns an ImageHash object; convert to Python int.
        # Cast to signed int64 so it fits PostgreSQL BIGINT (max 2^63-1).
        unsigned = int(str(h), 16)
        return unsigned - (1 << 64) if unsigned >= (1 << 63) else unsigned
    except Exception as exc:
        log.warning("vision.phash.failed", error=str(exc))
        return None


def extract_exif(image_bytes: bytes, backend: str = "pillow") -> Optional[dict]:
    """Extract EXIF metadata from image bytes.

    Args:
        image_bytes: raw image bytes
        backend:     "pillow" (pure Python) or "exiftool" (requires binary on PATH)

    Returns:
        dict of EXIF key→value (strings), or None on failure.
        Keys are filtered to intelligence-relevant fields only.

    Criteria 4.5: stored in media_assets.exif_data JSONB.
    """
    if backend == "exiftool":
        return _exif_exiftool(image_bytes)
    return _exif_pillow(image_bytes)


def _exif_pillow(image_bytes: bytes) -> Optional[dict]:
    """Extract EXIF using Pillow (pure Python, no external binary needed)."""
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS

        img = Image.open(io.BytesIO(image_bytes))
        raw = img._getexif()  # returns {tag_id: value} or None
        if not raw:
            return {"ai_software_detected": False}

        result: dict = {}
        for tag_id, value in raw.items():
            tag_name = TAGS.get(tag_id, str(tag_id))
            if tag_name in _EXIF_INTEREST_KEYS:
                try:
                    result[tag_name] = str(value)
                except Exception:
                    pass

        # Flag AI-generation software signatures
        software = result.get("Software", "").lower()
        result["ai_software_detected"] = any(
            sig in software for sig in _AI_SOFTWARE_SIGNATURES
        )
        return result

    except Exception as exc:
        log.debug("vision.exif.pillow_failed", error=str(exc))
        return {}


def _exif_exiftool(image_bytes: bytes) -> Optional[dict]:
    """Extract EXIF using exiftool binary — more comprehensive than Pillow."""
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["exiftool", "-json", "-g1", tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            log.warning("vision.exif.exiftool_error", stderr=result.stderr[:200])
            return {}
        data = json.loads(result.stdout)
        if not data:
            return {}
        flat = {}
        for group in data[0].values():
            if isinstance(group, dict):
                flat.update(group)
            else:
                flat["_"] = group

        # Filter to interest keys and add AI detection flag
        filtered = {k: str(v) for k, v in flat.items() if k in _EXIF_INTEREST_KEYS}
        software = filtered.get("Software", "").lower()
        filtered["ai_software_detected"] = any(
            sig in software for sig in _AI_SOFTWARE_SIGNATURES
        )
        return filtered
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as exc:
        log.warning("vision.exif.exiftool_failed", error=str(exc))
        return {}
    finally:
        os.unlink(tmp_path)


def is_video_path(storage_path: str) -> bool:
    """Determine if the asset at storage_path is a video based on extension."""
    _VIDEO_EXTS: frozenset[str] = frozenset({".mp4", ".avi", ".mov", ".webm", ".mkv"})
    return Path(storage_path).suffix.lower() in _VIDEO_EXTS
