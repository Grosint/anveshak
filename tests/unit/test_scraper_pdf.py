"""Unit tests for scraper PDF text extraction.

Tests:
  - extract_pdf_text returns text from a PDF byte stream
  - Empty/corrupt PDF returns None
  - PDF text is cleaned (whitespace normalised)
  - fetch_pdf_text fetches + extracts in one step

pytest.mark.unit — uses mock bytes, no real PDFs.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestExtractPdfText:
    """extract_pdf_text extracts text from PDF bytes."""

    def test_returns_text_from_valid_pdf(self):
        """Valid PDF bytes → extracted text string."""
        from anveshak.scraper.pdf_extract import extract_pdf_text

        # Create a fake PDF with pymupdf mock
        with patch("anveshak.scraper.pdf_extract.fitz") as mock_fitz:
            mock_page = MagicMock()
            mock_page.get_text.return_value = "Intelligence report content here."
            mock_doc = MagicMock()
            mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
            mock_doc.__enter__ = MagicMock(return_value=mock_doc)
            mock_doc.__exit__ = MagicMock(return_value=False)
            mock_fitz.open.return_value = mock_doc

            result = extract_pdf_text(b"%PDF-fake-content")
            assert result == "Intelligence report content here."

    def test_empty_pdf_returns_none(self):
        """PDF with no text pages → None."""
        from anveshak.scraper.pdf_extract import extract_pdf_text

        with patch("anveshak.scraper.pdf_extract.fitz") as mock_fitz:
            mock_page = MagicMock()
            mock_page.get_text.return_value = ""
            mock_doc = MagicMock()
            mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
            mock_doc.__enter__ = MagicMock(return_value=mock_doc)
            mock_doc.__exit__ = MagicMock(return_value=False)
            mock_fitz.open.return_value = mock_doc

            result = extract_pdf_text(b"%PDF-empty")
            assert result is None

    def test_corrupt_pdf_returns_none(self):
        """Corrupt/invalid PDF bytes → None, no crash."""
        from anveshak.scraper.pdf_extract import extract_pdf_text

        with patch("anveshak.scraper.pdf_extract.fitz") as mock_fitz:
            mock_fitz.open.side_effect = RuntimeError("corrupt PDF")

            result = extract_pdf_text(b"not-a-pdf")
            assert result is None

    def test_multipage_text_concatenated(self):
        """Multiple pages → text concatenated with newlines."""
        from anveshak.scraper.pdf_extract import extract_pdf_text

        with patch("anveshak.scraper.pdf_extract.fitz") as mock_fitz:
            page1 = MagicMock()
            page1.get_text.return_value = "Page one content."
            page2 = MagicMock()
            page2.get_text.return_value = "Page two content."
            mock_doc = MagicMock()
            mock_doc.__iter__ = MagicMock(return_value=iter([page1, page2]))
            mock_doc.__enter__ = MagicMock(return_value=mock_doc)
            mock_doc.__exit__ = MagicMock(return_value=False)
            mock_fitz.open.return_value = mock_doc

            result = extract_pdf_text(b"%PDF-multi")
            assert "Page one content." in result
            assert "Page two content." in result


class TestFetchPdfText:
    """fetch_pdf_text downloads and extracts text from a PDF URL."""

    @pytest.mark.asyncio
    async def test_fetches_and_extracts(self):
        from anveshak.scraper.pdf_extract import fetch_pdf_text

        import httpx as real_httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"%PDF-data"
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("anveshak.scraper.pdf_extract.extract_pdf_text") as mock_extract:
            mock_extract.return_value = "Extracted PDF text."

            result = await fetch_pdf_text("https://example.com/report.pdf")
            assert result == "Extracted PDF text."

    @pytest.mark.asyncio
    async def test_fetch_failure_returns_none(self):
        from anveshak.scraper.pdf_extract import fetch_pdf_text

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("network error"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await fetch_pdf_text("https://example.com/report.pdf")
            assert result is None
