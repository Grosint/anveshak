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
    from crawl4ai import AsyncWebCrawler

    proxy_kwargs: dict = {}
    if settings.tor_proxy_url:
        proxy_kwargs["proxy"] = settings.tor_proxy_url

    # Support both Crawl4AI ≥0.4 (BrowserConfig/CrawlerRunConfig) and older API.
    try:
        from crawl4ai import BrowserConfig, CrawlerRunConfig

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

    proxies: dict = {}
    if settings.tor_proxy_url:
        proxies = {"all://": settings.tor_proxy_url}

    async with httpx.AsyncClient(
        timeout=settings.scraper_request_timeout_s,
        follow_redirects=True,
        proxies=proxies if proxies else None,
        headers={"User-Agent": "Mozilla/5.0 (compatible; Anveshak/1.0)"},
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
    return text or None
