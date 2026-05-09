"""PDF text extraction for the scraper service.

Uses PyMuPDF (fitz) to extract text from downloaded PDF files.
PDFs encountered during scraping are fetched, text extracted, and
inserted as content_items just like web page text.

CLAUDE.md rule 6: no hardcoded model/device choices.
"""
from __future__ import annotations

from typing import Optional

import structlog

log = structlog.get_logger(__name__)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None  # type: ignore[assignment]
    log.info("scraper.pymupdf_not_installed", hint="pip install pymupdf to enable PDF extraction")


def extract_pdf_text(pdf_bytes: bytes) -> Optional[str]:
    """Extract text from PDF bytes.

    Returns concatenated text from all pages, or None if extraction fails
    or PDF contains no text (e.g., scanned images only).
    """
    if fitz is None:
        log.warning("scraper.pdf_extract_unavailable", hint="pymupdf not installed")
        return None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages: list[str] = []
        for page in doc:
            text = page.get_text()
            if text and text.strip():
                pages.append(text.strip())
        doc.close()

        if not pages:
            return None
        return "\n\n".join(pages)
    except Exception as exc:
        log.warning("scraper.pdf_extract_failed", error=str(exc))
        return None


async def fetch_pdf_text(url: str, timeout: int = 30) -> Optional[str]:
    """Download a PDF from URL and extract its text.

    Returns None on fetch failure or empty PDF.
    """
    import httpx

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Anveshak/1.0)"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return extract_pdf_text(resp.content)
    except Exception as exc:
        log.warning("scraper.pdf_fetch_failed", url=url, error=str(exc))
        return None
