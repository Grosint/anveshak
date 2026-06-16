"""MIME type validation via magic bytes for uploaded files.

Rejects files whose actual content doesn't match an allowed image/video
MIME type — regardless of the filename extension provided by the user.
Prevents upload of .php, .html, .svg, or other dangerous file types
disguised with media extensions.
"""
from __future__ import annotations

import mimetypes

import structlog

log = structlog.get_logger(__name__)

# Known magic byte signatures → MIME types
_MAGIC_SIGNATURES: list[tuple[bytes, int, str]] = [
    # (signature, offset, mime_type)
    (b"\xff\xd8\xff", 0, "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    (b"GIF87a", 0, "image/gif"),
    (b"GIF89a", 0, "image/gif"),
    (b"RIFF", 0, "image/webp"),     # RIFF....WEBP — check WEBP at offset 8
    (b"BM", 0, "image/bmp"),
]

# Video signatures need offset-aware checking
_VIDEO_SIGNATURES: list[tuple[bytes, int, str]] = [
    (b"ftyp", 4, "video/mp4"),      # MP4/M4V: offset 4 = "ftyp"
    (b"\x1a\x45\xdf\xa3", 0, "video/webm"),  # WebM/MKV (EBML)
    (b"\x00\x00\x00\x1c\x66\x74\x79\x70", 0, "video/mp4"),  # MP4 with box size
    (b"RIFF", 0, "video/avi"),       # AVI: RIFF....AVI — checked after WEBP
]

# All MIME types we accept
_ALLOWED_MIMES: frozenset[str] = frozenset({
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp",
    "video/mp4", "video/avi", "video/webm", "video/x-msvideo",
    "video/x-matroska", "video/quicktime",
})


class UnsafeMimeError(ValueError):
    """Raised when uploaded file content doesn't match an allowed MIME type."""


def _detect_mime(data: bytes) -> str | None:
    """Detect MIME type from magic bytes. Returns None if unrecognized."""
    if len(data) < 8:
        return None

    # Check image signatures
    for sig, offset, mime in _MAGIC_SIGNATURES:
        if data[offset:offset + len(sig)] == sig:
            # RIFF can be WEBP or AVI — disambiguate
            if sig == b"RIFF" and len(data) > 12:
                if data[8:12] == b"WEBP":
                    return "image/webp"
                if data[8:12] == b"AVI ":
                    return "video/avi"
                continue  # Unknown RIFF subtype
            return mime

    # Check video signatures
    for sig, offset, mime in _VIDEO_SIGNATURES:
        if len(data) > offset + len(sig) and data[offset:offset + len(sig)] == sig:
            if sig == b"RIFF":
                continue  # Already handled above
            return mime

    return None


def validate_upload_mime(data: bytes, filename: str) -> tuple[str, str]:
    """Validate file content by magic bytes, return (mime_type, safe_extension).

    Args:
        data: Raw file bytes (at least first 2048 bytes needed).
        filename: Original filename from upload (used only as fallback hint).

    Returns:
        Tuple of (detected_mime_type, safe_extension).

    Raises:
        UnsafeMimeError: If the file content doesn't match any allowed MIME type.
    """
    if not data:
        raise UnsafeMimeError("Empty file — cannot determine MIME type")

    detected = _detect_mime(data)

    if detected is None or detected not in _ALLOWED_MIMES:
        raise UnsafeMimeError(
            f"Unsupported file type: detected={detected!r} from magic bytes. "
            f"Allowed: image/video only. Filename: {filename!r}"
        )

    # Derive safe extension from detected MIME, NOT from user-provided filename
    ext = mimetypes.guess_extension(detected) or ".bin"
    # mimetypes returns .jpe for jpeg on some systems
    if detected == "image/jpeg" and ext not in (".jpg", ".jpeg"):
        ext = ".jpg"

    log.debug("vision.mime_validated", detected=detected, ext=ext, filename=filename)
    return detected, ext
