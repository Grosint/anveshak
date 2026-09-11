"""Unit tests: SDK media downloader.

Criteria 4.4: content_hash is SHA-256 of raw bytes (not text hash, not URL hash).
"""

import contextlib
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

_REAL_ASYNC_CLIENT = httpx.AsyncClient


@contextlib.contextmanager
def _served(handler):
    """Serve handler over MockTransport, with resolution fixed to a public address.

    The download runs through anveshak.net.safe_fetch, which resolves the host
    and connects to the address it approved, so a test must fix both the
    transport and the answer rather than stand in for the client wholesale.
    """

    def _factory(*args, **kwargs):
        return _REAL_ASYNC_CLIENT(*args, transport=httpx.MockTransport(handler), **kwargs)

    with (
        patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=_factory),
        patch(
            "anveshak.net.url_safety._resolve_host",
            new=AsyncMock(return_value=["93.184.216.34"]),
        ),
    ):
        yield


def _serving(content: bytes, content_type: str, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=content, headers={"content-type": content_type})

    return _served(handler)


class TestMediaDownloaderContentHash:
    @pytest.mark.unit
    async def test_content_hash_is_sha256_of_raw_bytes(self, tmp_path):
        """content_hash must be SHA-256 of raw file bytes (criteria 4.4)."""
        from anveshak.media.downloader import download_media_asset

        test_bytes = b"\x89PNG fake image bytes for testing"

        with _serving(test_bytes, "image/png"):
            result = await download_media_asset(
                url="http://example.com/image.png",
                topic_id="test-topic",
                storage_root=tmp_path,
                max_size_mb=10,
            )

        assert result is not None
        assert result.content_hash == hashlib.sha256(test_bytes).hexdigest()
        assert len(result.content_hash) == 64  # SHA-256 hex = 64 chars

    @pytest.mark.unit
    def test_content_hash_differs_from_text_hash(self, tmp_path):
        """SHA-256 of raw bytes ≠ SHA-256 of text string (bytes are the ground truth)."""

        # For binary data, the byte hash and text-decoded hash will differ
        raw_bytes = b"\xff\xd8\xff\xe0JPEG binary data"
        byte_hash = hashlib.sha256(raw_bytes).hexdigest()
        # Attempting to decode as utf-8 would fail for arbitrary bytes — confirmed different
        assert byte_hash != hashlib.sha256(raw_bytes.decode("latin-1").encode("utf-8")).hexdigest()

    @pytest.mark.unit
    async def test_returns_none_for_unsupported_content_type(self, tmp_path):
        """Returns None if content-type is not image/video/document."""
        from anveshak.media.downloader import download_media_asset

        with _serving(b"<html>not an image</html>", "text/html"):
            result = await download_media_asset(
                url="http://example.com/page.html",
                topic_id="test-topic",
                storage_root=tmp_path,
            )

        assert result is None

    @pytest.mark.unit
    async def test_returns_none_on_http_error(self, tmp_path):
        """Returns None (not exception) on HTTP failure."""
        from anveshak.media.downloader import download_media_asset

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        with _served(handler):
            result = await download_media_asset(
                url="http://unreachable.example.com/img.jpg",
                topic_id="t",
                storage_root=tmp_path,
            )

        assert result is None

    @pytest.mark.unit
    async def test_asset_type_detected_from_content_type(self, tmp_path):
        """asset_type is correctly inferred from MIME type."""
        from anveshak.media.downloader import download_media_asset

        for content_type, expected_type in [
            ("image/jpeg", "image"),
            ("image/png", "image"),
            ("video/mp4", "video"),
            ("application/pdf", "document"),
        ]:
            with _serving(b"fake bytes for " + content_type.encode(), content_type):
                result = await download_media_asset(
                    url="http://example.com/file",
                    topic_id="t",
                    storage_root=tmp_path,
                )

            assert result is not None
            assert result.asset_type == expected_type, (
                f"Expected {expected_type} for {content_type}"
            )


class TestMediaDownloadDestination:
    """A media URL is markup someone else wrote, so every hop is judged (#55)."""

    @pytest.mark.unit
    async def test_a_redirect_into_the_deployment_is_refused(self, tmp_path):
        from anveshak.media.downloader import download_media_asset

        requested: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(request.headers["host"])
            if request.headers["host"] == "example.com":
                return httpx.Response(302, headers={"location": "http://ollama:11434/api/tags"})
            return httpx.Response(200, content=b"internal", headers={"content-type": "image/png"})

        async def _external_only(hostname: str) -> list[str]:
            return ["172.28.0.9"] if hostname == "ollama" else ["93.184.216.34"]

        def _factory(*args, **kwargs):
            return _REAL_ASYNC_CLIENT(*args, transport=httpx.MockTransport(handler), **kwargs)

        with (
            patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=_factory),
            patch(
                "anveshak.net.url_safety._resolve_host", new=AsyncMock(side_effect=_external_only)
            ),
        ):
            result = await download_media_asset(
                url="http://example.com/image.png",
                topic_id="t",
                storage_root=tmp_path,
            )

        assert result is None
        assert requested == ["example.com"], "the internal hop must never be requested"

    @pytest.mark.unit
    async def test_a_document_past_the_size_cap_is_refused(self, tmp_path):
        from anveshak.media.downloader import download_media_asset

        with _serving(b"x" * (2 * 1024 * 1024), "image/png"):
            result = await download_media_asset(
                url="http://example.com/huge.png",
                topic_id="t",
                storage_root=tmp_path,
                max_size_mb=1,
            )

        assert result is None


class TestLocalFilePathSupport:
    """Phase 0: local file path support for pre-downloaded media (Telegram, WhatsApp)."""

    @pytest.mark.unit
    def test_local_file_returns_result(self, tmp_path):
        """Local .jpg file inside media volume returns valid MediaDownloadResult."""
        import asyncio

        from anveshak.media.downloader import download_media_asset

        # Setup: create a file inside storage_root/media/topic/...
        media_dir = tmp_path / "media" / "test-topic" / "2026" / "06" / "24"
        media_dir.mkdir(parents=True)
        img = media_dir / "abc123.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")

        result = asyncio.get_event_loop().run_until_complete(
            download_media_asset(
                url=str(img),
                topic_id="test-topic",
                storage_root=tmp_path,
            )
        )

        assert result is not None
        assert result.content_hash == hashlib.sha256(b"\xff\xd8\xff\xe0fake-jpeg-bytes").hexdigest()
        assert result.asset_type == "image"
        assert result.file_size_bytes == len(b"\xff\xd8\xff\xe0fake-jpeg-bytes")

    @pytest.mark.unit
    def test_local_file_not_found_returns_none(self, tmp_path):
        """Non-existent local path returns None."""
        import asyncio

        from anveshak.media.downloader import download_media_asset

        # Path inside volume but file doesn't exist
        fake_path = str(tmp_path / "media" / "test-topic" / "nonexistent.jpg")

        result = asyncio.get_event_loop().run_until_complete(
            download_media_asset(
                url=fake_path,
                topic_id="test-topic",
                storage_root=tmp_path,
            )
        )
        assert result is None

    @pytest.mark.unit
    def test_local_file_path_traversal_rejected(self, tmp_path):
        """Path traversal attempt (../../etc/passwd) returns None."""
        import asyncio

        from anveshak.media.downloader import download_media_asset

        # Create a file OUTSIDE the media volume
        outside = tmp_path / "outside" / "secret.jpg"
        outside.parent.mkdir(parents=True)
        outside.write_bytes(b"secret-data")

        # Try to access it via path traversal
        traversal_path = str(tmp_path / "media" / ".." / "outside" / "secret.jpg")

        result = asyncio.get_event_loop().run_until_complete(
            download_media_asset(
                url=traversal_path,
                topic_id="test-topic",
                storage_root=tmp_path,
            )
        )
        assert result is None

    @pytest.mark.unit
    def test_local_file_outside_volume_rejected(self, tmp_path):
        """File that exists but is outside storage_root returns None."""
        import asyncio
        import tempfile

        from anveshak.media.downloader import download_media_asset

        # Create file in a completely separate directory (outside storage_root)
        with tempfile.TemporaryDirectory() as other_dir:
            other = Path(other_dir) / "secret.jpg"
            other.write_bytes(b"not-in-volume")

            result = asyncio.get_event_loop().run_until_complete(
                download_media_asset(
                    url=str(other),
                    topic_id="test-topic",
                    storage_root=tmp_path,
                )
            )
        assert result is None

    @pytest.mark.unit
    def test_local_video_file_detected(self, tmp_path):
        """Local .mp4 file returns asset_type='video'."""
        import asyncio

        from anveshak.media.downloader import download_media_asset

        media_dir = tmp_path / "media" / "test-topic"
        media_dir.mkdir(parents=True)
        vid = media_dir / "clip.mp4"
        vid.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00" * 100)

        result = asyncio.get_event_loop().run_until_complete(
            download_media_asset(
                url=str(vid),
                topic_id="test-topic",
                storage_root=tmp_path,
            )
        )

        assert result is not None
        assert result.asset_type == "video"

    @pytest.mark.unit
    def test_local_file_directly_under_storage_root(self, tmp_path):
        """File at storage_root/group_id/date/hash.jpg (WhatsApp bridge pattern)."""
        import asyncio

        from anveshak.media.downloader import download_media_asset

        # WhatsApp bridge stores at /app/media/{group_id}/{date}/{hash}.jpg
        # NOT under /app/media/media/ subdirectory
        media_dir = tmp_path / "120363001234567890" / "2026" / "06" / "25"
        media_dir.mkdir(parents=True)
        img = media_dir / "abc123.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0whatsapp-image")

        result = asyncio.get_event_loop().run_until_complete(
            download_media_asset(
                url=str(img),
                topic_id="test-topic",
                storage_root=tmp_path,
            )
        )

        assert result is not None
        assert result.asset_type == "image"

    @pytest.mark.unit
    async def test_http_url_still_works(self, tmp_path):
        """An HTTP URL still goes out over the network path (no regression)."""
        from anveshak.media.downloader import download_media_asset

        requested: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(str(request.url))
            return httpx.Response(200, content=b"png-bytes", headers={"content-type": "image/png"})

        with _served(handler):
            result = await download_media_asset(
                url="http://example.com/image.png",
                topic_id="test-topic",
                storage_root=tmp_path,
            )

        assert result is not None
        assert len(requested) == 1
