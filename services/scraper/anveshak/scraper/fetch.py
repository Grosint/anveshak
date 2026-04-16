"""URL fetch helpers — Crawl4AI primary, trafilatura fallback (criteria 1.2, 1.3, 1.10)."""
from __future__ import annotations

from typing import Optional

import structlog
import trafilatura

from .settings import settings

log = structlog.get_logger(__name__)


async def fetch_url(url: str) -> Optional[str]:
    """Fetch and extract clean text from a URL.

    1. Tries Crawl4AI (JS-rendered, full-page extraction).
    2. Falls back to trafilatura (fast HTML extraction via httpx) if Crawl4AI
       returns an empty body or raises.
    Returns None on complete fetch failure — caller logs and skips (criteria 1.9).
    """
    try:
        clean = await _crawl4ai_fetch(url)
        if clean and len(clean.strip()) >= 50:
            return clean.strip()
        log.debug("scraper.crawl4ai_empty", url=url)
    except Exception as exc:
        log.warning("scraper.crawl4ai_error", url=url, error=str(exc))

    try:
        return await _trafilatura_fetch(url)
    except Exception as exc:
        log.warning("scraper.fetch_failed", url=url, error=str(exc))
        return None


async def _crawl4ai_fetch(url: str) -> Optional[str]:
    """Use Crawl4AI's headless browser to fetch the page."""
    import os
    from crawl4ai import AsyncWebCrawler

    # Ensure HOME is set — Chromium writes user-data-dir relative to HOME.
    if not os.environ.get("HOME") or os.environ["HOME"] == "/nonexistent":
        os.environ["HOME"] = "/tmp"

    proxy_kwargs: dict = {}
    if settings.tor_proxy_url:
        proxy_kwargs["proxy"] = settings.tor_proxy_url

    # Support both Crawl4AI ≥0.4 (BrowserConfig/CrawlerRunConfig) and older API.
    try:
        from crawl4ai import BrowserConfig, CrawlerRunConfig

        try:
            browser_cfg = BrowserConfig(headless=True, enable_stealth=True, **proxy_kwargs)
        except TypeError:
            # Older Crawl4AI versions do not support enable_stealth — degrade silently.
            browser_cfg = BrowserConfig(headless=True, **proxy_kwargs)
        run_cfg = CrawlerRunConfig(
            page_timeout=settings.scraper_request_timeout_s * 1000,
        )
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)
    except (ImportError, TypeError):
        # Older Crawl4AI API
        async with AsyncWebCrawler(**proxy_kwargs) as crawler:
            result = await crawler.arun(url=url)

    if not result.success:
        return None

    markdown = result.markdown
    if markdown is None:
        return None
    # Crawl4AI ≥0.4 returns a MarkdownGenerationResult object.
    if hasattr(markdown, "raw_markdown"):
        return markdown.raw_markdown or None
    return str(markdown) or None


async def _trafilatura_fetch(url: str) -> Optional[str]:
    """Download raw HTML via httpx then extract with trafilatura."""
    import httpx

    client_kwargs: dict = {
        "timeout": settings.scraper_request_timeout_s,
        "follow_redirects": True,
        "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"},
    }
    if settings.tor_proxy_url:
        # httpx ≥0.27 uses `proxy=` (single URL); older versions used `proxies=` dict.
        try:
            import inspect
            sig = inspect.signature(httpx.AsyncClient.__init__)
            if "proxy" in sig.parameters:
                client_kwargs["proxy"] = settings.tor_proxy_url
            else:
                client_kwargs["proxies"] = {"all://": settings.tor_proxy_url}
        except Exception:
            client_kwargs["proxy"] = settings.tor_proxy_url

    async with httpx.AsyncClient(**client_kwargs) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
    return text or None
