"""PDF text extraction for the scraper service.

Uses PyMuPDF (fitz) to extract text from downloaded PDF files.
PDFs encountered during scraping are fetched, text extracted, and
inserted as content_items just like web page text.

AGENTS.md rule 6: no hardcoded model/device choices.
"""

from __future__ import annotations

from typing import Optional

import structlog
from anveshak.net.safe_fetch import fetch_bytes

log = structlog.get_logger(__name__)

# A PDF is served by whoever the scraped page linked to, so its size is theirs
# to choose and ours to bound. Measured after decompression.
_MAX_PDF_BYTES = 32 * 1024 * 1024

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
            # get_text() returns str, list or dict depending on the option arg.
            # With no arg it is str, but narrow rather than assume.
            text = page.get_text()
            if isinstance(text, str) and text.strip():
                pages.append(text.strip())
        doc.close()

        if not pages:
            return None
        return "\n\n".join(pages)
    except Exception as exc:
        log.warning("scraper.pdf_extract_failed", error=str(exc))
        return None


async def fetch_pdf_text(url: str, timeout: int = 30) -> Optional[str]:
    """Download a PDF through the guarded path and extract its text.

    The URL is a link found in scraped markup, so the destination is validated
    at every redirect hop and the document is bounded rather than buffered
    whole. Returns None on fetch failure or empty PDF.
    """
    result = await fetch_bytes(
        url,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 (compatible; Anveshak/1.0)"},
        limit=_MAX_PDF_BYTES,
    )
    if result is None:
        log.warning("scraper.pdf_fetch_failed", url=url)
        return None
    return extract_pdf_text(result.body)
