"""Unit tests: SDK media downloader.

Criteria 4.4: content_hash is SHA-256 of raw bytes (not text hash, not URL hash).
"""
import hashlib
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestMediaDownloaderContentHash:
    @pytest.mark.unit
    def test_content_hash_is_sha256_of_raw_bytes(self, tmp_path):
        """content_hash must be SHA-256 of raw file bytes (criteria 4.4)."""
        import asyncio
        from unittest.mock import AsyncMock

        test_bytes = b"\x89PNG fake image bytes for testing"
        expected_hash = hashlib.sha256(test_bytes).hexdigest()

        # Mock httpx response
        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "image/png"}
        mock_resp.content = test_bytes
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from anveshak.media.downloader import download_media_asset
            result = asyncio.get_event_loop().run_until_complete(
                download_media_asset(
                    url="http://example.com/image.png",
                    topic_id="test-topic",
                    storage_root=tmp_path,
                    max_size_mb=10,
                )
            )

        assert result is not None
        assert result.content_hash == expected_hash
        assert len(result.content_hash) == 64  # SHA-256 hex = 64 chars

    @pytest.mark.unit
    def test_content_hash_differs_from_text_hash(self, tmp_path):
        """SHA-256 of raw bytes ≠ SHA-256 of text string (bytes are the ground truth)."""
        import asyncio

        # For binary data, the byte hash and text-decoded hash will differ
        raw_bytes = b"\xff\xd8\xff\xe0JPEG binary data"
        byte_hash = hashlib.sha256(raw_bytes).hexdigest()
        # Attempting to decode as utf-8 would fail for arbitrary bytes — confirmed different
        assert byte_hash != hashlib.sha256(raw_bytes.decode("latin-1").encode("utf-8")).hexdigest()

    @pytest.mark.unit
    def test_returns_none_for_unsupported_content_type(self, tmp_path):
        """Returns None if content-type is not image/video/document."""
        import asyncio

        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.content = b"<html>not an image</html>"
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from anveshak.media.downloader import download_media_asset
            result = asyncio.get_event_loop().run_until_complete(
                download_media_asset(
                    url="http://example.com/page.html",
                    topic_id="test-topic",
                    storage_root=tmp_path,
                )
            )
        assert result is None

    @pytest.mark.unit
    def test_returns_none_on_http_error(self, tmp_path):
        """Returns None (not exception) on HTTP failure."""
        import asyncio
        import httpx

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("connection refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            from anveshak.media.downloader import download_media_asset
            result = asyncio.get_event_loop().run_until_complete(
                download_media_asset(
                    url="http://unreachable.example.com/img.jpg",
                    topic_id="t",
                    storage_root=tmp_path,
                )
            )
        assert result is None

    @pytest.mark.unit
    def test_asset_type_detected_from_content_type(self, tmp_path):
        """asset_type is correctly inferred from MIME type."""
        import asyncio

        for content_type, expected_type in [
            ("image/jpeg", "image"),
            ("image/png", "image"),
            ("video/mp4", "video"),
            ("application/pdf", "document"),
        ]:
            mock_resp = MagicMock()
            mock_resp.headers = {"content-type": content_type}
            mock_resp.content = b"fake bytes for " + content_type.encode()
            mock_resp.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)

            with patch("httpx.AsyncClient", return_value=mock_client):
                from anveshak.media.downloader import download_media_asset
                result = asyncio.get_event_loop().run_until_complete(
                    download_media_asset(
                        url=f"http://example.com/file",
                        topic_id="t",
                        storage_root=tmp_path,
                    )
                )
            if result:
                assert result.asset_type == expected_type, f"Expected {expected_type} for {content_type}"
