"""Unit tests for vision upload MIME validation.

Critical fix: analyse_upload accepts any file extension from the user
without validating actual file content. A .php disguised as .jpg must
be rejected based on magic bytes, not filename.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# Minimal valid file headers (magic bytes)
JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 100
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
GIF_MAGIC = b"GIF89a" + b"\x00" * 100
WEBP_MAGIC = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 100
MP4_MAGIC = b"\x00\x00\x00\x1c" + b"ftyp" + b"isom" + b"\x00" * 100
PHP_CONTENT = b"<?php echo 'pwned'; ?>"
HTML_CONTENT = b"<html><body><script>alert('xss')</script></body></html>"
RANDOM_BYTES = b"\x00\x01\x02\x03" * 30


class TestValidateUploadMime:
    """validate_upload_mime must check magic bytes, not filename extension."""

    def test_accepts_jpeg(self):
        from anveshak.vision.mime_check import validate_upload_mime

        mime, ext = validate_upload_mime(JPEG_MAGIC, "photo.jpg")
        assert mime == "image/jpeg"
        assert ext in (".jpg", ".jpeg")

    def test_accepts_png(self):
        from anveshak.vision.mime_check import validate_upload_mime

        mime, ext = validate_upload_mime(PNG_MAGIC, "screenshot.png")
        assert mime == "image/png"
        assert ext == ".png"

    def test_accepts_gif(self):
        from anveshak.vision.mime_check import validate_upload_mime

        mime, ext = validate_upload_mime(GIF_MAGIC, "animation.gif")
        assert mime == "image/gif"
        assert ext == ".gif"

    def test_accepts_mp4(self):
        from anveshak.vision.mime_check import validate_upload_mime

        mime, ext = validate_upload_mime(MP4_MAGIC, "video.mp4")
        assert "video" in mime or "mp4" in mime.lower() or mime == "video/mp4"

    def test_rejects_php_disguised_as_jpg(self):
        from anveshak.vision.mime_check import UnsafeMimeError, validate_upload_mime

        with pytest.raises(UnsafeMimeError):
            validate_upload_mime(PHP_CONTENT, "exploit.jpg")

    def test_rejects_html_disguised_as_png(self):
        from anveshak.vision.mime_check import UnsafeMimeError, validate_upload_mime

        with pytest.raises(UnsafeMimeError):
            validate_upload_mime(HTML_CONTENT, "page.png")

    def test_rejects_empty_bytes(self):
        from anveshak.vision.mime_check import UnsafeMimeError, validate_upload_mime

        with pytest.raises(UnsafeMimeError):
            validate_upload_mime(b"", "empty.jpg")

    def test_rejects_unknown_binary(self):
        from anveshak.vision.mime_check import UnsafeMimeError, validate_upload_mime

        with pytest.raises(UnsafeMimeError):
            validate_upload_mime(RANDOM_BYTES, "unknown.bin")

    def test_uses_magic_bytes_not_extension(self):
        """JPEG magic bytes with .php extension → still accepted as image/jpeg."""
        from anveshak.vision.mime_check import validate_upload_mime

        mime, ext = validate_upload_mime(JPEG_MAGIC, "exploit.php")
        assert mime == "image/jpeg"
        # Extension should be overridden based on actual MIME
        assert ext in (".jpg", ".jpeg")
