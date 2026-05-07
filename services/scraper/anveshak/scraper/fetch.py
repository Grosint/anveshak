"""URL fetch helpers — Crawl4AI primary, trafilatura fallback (criteria 1.2, 1.3, 1.10).

Browser reuse: create_shared_crawler() returns a context manager that spawns
one Chromium instance and reuses it for all URLs in a scrape_topic job.
"""
from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from urllib.parse import urljoin, urlparse

import structlog
import trafilatura

from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Shared browser context manager — one Chromium per job, not per URL
# ---------------------------------------------------------------------------

_crawler_instance = None  # module-level for reuse within a job
_run_cfg = None


@asynccontextmanager
async def create_shared_crawler():
    """Create a single AsyncWebCrawler instance for reuse across multiple URLs.

    Usage:
        async with create_shared_crawler() as crawler:
            text1 = await fetch_url_with_crawler(url1, crawler)
            text2 = await fetch_url_with_crawler(url2, crawler)
    """
    from crawl4ai import AsyncWebCrawler

    if not os.environ.get("HOME") or os.environ["HOME"] == "/nonexistent":
        os.environ["HOME"] = "/tmp"

    proxy_kwargs: dict = {}
    if settings.tor_proxy_url:
        proxy_kwargs["proxy"] = settings.tor_proxy_url

    try:
        from crawl4ai import BrowserConfig, CrawlerRunConfig

        try:
            browser_cfg = BrowserConfig(headless=True, enable_stealth=True, **proxy_kwargs)
        except TypeError:
            browser_cfg = BrowserConfig(headless=True, **proxy_kwargs)
        run_cfg = CrawlerRunConfig(
            page_timeout=settings.scraper_request_timeout_s * 1000,
        )
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            yield crawler, run_cfg
    except (ImportError, TypeError):
        async with AsyncWebCrawler(**proxy_kwargs) as crawler:
            yield crawler, None


def _extract_markdown(result) -> Optional[str]:
    """Extract clean text from a Crawl4AI result object."""
    if not result.success:
        return None
    markdown = result.markdown
    if markdown is None:
        return None
    if hasattr(markdown, "raw_markdown"):
        return markdown.raw_markdown or None
    return str(markdown) or None


async def fetch_url_with_crawler(
    url: str, crawler, run_cfg=None
) -> Optional[str]:
    """Fetch a URL using an existing shared crawler instance.

    Falls back to trafilatura if Crawl4AI returns empty.
    """
    try:
        if run_cfg is not None:
            result = await crawler.arun(url=url, config=run_cfg)
        else:
            result = await crawler.arun(url=url)
        clean = _extract_markdown(result)
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


async def fetch_url(url: str) -> Optional[str]:
    """Fetch and extract clean text from a URL (standalone, creates its own browser).

    1. Tries Crawl4AI (JS-rendered, full-page extraction).
    2. Falls back to trafilatura (fast HTML extraction via httpx) if Crawl4AI
       returns an empty body or raises.
    Returns None on complete fetch failure — caller logs and skips (criteria 1.9).
    """
    try:
        async with create_shared_crawler() as (crawler, run_cfg):
            return await fetch_url_with_crawler(url, crawler, run_cfg)
    except Exception as exc:
        log.warning("scraper.crawl4ai_error", url=url, error=str(exc))

    try:
        return await _trafilatura_fetch(url)
    except Exception as exc:
        log.warning("scraper.fetch_failed", url=url, error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Recursive link extraction (depth-1 only)
# ---------------------------------------------------------------------------

_SKIP_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".mp4", ".mp3", ".avi", ".mov", ".zip", ".tar", ".gz",
}


def extract_article_links(html: str, base_url: str) -> list[str]:
    """Extract article hyperlinks from HTML for depth-1 recursive scraping.

    Filters: same-domain only (if configured), skips media/binary links,
    caps at scraper_max_links_per_page.
    """
    from html.parser import HTMLParser

    base_parsed = urlparse(base_url)
    links: list[str] = []
    seen: set[str] = set()

    class _LinkExtractor(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
            if tag != "a":
                return
            href = dict(attrs).get("href")
            if not href or href.startswith("#") or href.startswith("javascript:"):
                return
            abs_url = urljoin(base_url, href)
            parsed = urlparse(abs_url)
            if parsed.scheme not in {"http", "https"}:
                return
            # Skip binary/media files
            ext = os.path.splitext(parsed.path)[1].lower()
            if ext in _SKIP_EXTENSIONS:
                return
            # Same-domain filter
            if settings.scraper_follow_same_domain and parsed.netloc != base_parsed.netloc:
                return
            # Skip the base URL itself
            if abs_url.rstrip("/") == base_url.rstrip("/"):
                return
            # Dedup
            canonical = abs_url.rstrip("/")
            if canonical in seen:
                return
            seen.add(canonical)
            links.append(abs_url)

    try:
        _LinkExtractor().feed(html)
    except Exception:
        pass

    return links[:settings.scraper_max_links_per_page]


async def fetch_html(url: str) -> Optional[str]:
    """Fetch raw HTML from a URL via httpx (for link extraction)."""
    import httpx

    try:
        async with httpx.AsyncClient(
            timeout=settings.scraper_request_timeout_s,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
    except Exception as exc:
        log.warning("scraper.html_fetch_failed", url=url, error=str(exc))
        return None


async def _trafilatura_fetch(
    url: str, *, proxy_url: Optional[str] = None
) -> Optional[str]:
    """Download raw HTML via httpx then extract with trafilatura.

    Args:
        proxy_url: Explicit proxy override. If None, falls back to settings.tor_proxy_url.
    """
    import httpx

    effective_proxy = proxy_url or settings.tor_proxy_url
    client_kwargs: dict = {
        "timeout": settings.scraper_request_timeout_s,
        "follow_redirects": True,
        "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"},
    }
    if effective_proxy:
        try:
            import inspect
            sig = inspect.signature(httpx.AsyncClient.__init__)
            if "proxy" in sig.parameters:
                client_kwargs["proxy"] = effective_proxy
            else:
                client_kwargs["proxies"] = {"all://": effective_proxy}
        except Exception:
            client_kwargs["proxy"] = effective_proxy

    async with httpx.AsyncClient(**client_kwargs) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
    return text or None


# ---------------------------------------------------------------------------
# Dark web (.onion) — Tor-forced fetching with DNS leak protection
# ---------------------------------------------------------------------------

def validate_onion_url(url: str) -> None:
    """Raise ValueError if URL is not a .onion address.

    DNS leak prevention: ensures .onion traffic is never sent to a clearnet
    DNS resolver. Called before every dark web fetch as defense in depth.
    """
    parsed = urlparse(url)
    if not parsed.netloc.endswith(".onion"):
        raise ValueError(
            f"DNS leak prevention: {url} is not a .onion URL — "
            "refusing to fetch via clearnet"
        )
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Dark web URL must use http:// or https:// scheme, got {parsed.scheme}"
        )


@asynccontextmanager
async def create_tor_crawler():
    """Create a Crawl4AI browser instance routed through the Tor SOCKS5 proxy.

    Always uses settings.darkweb_tor_proxy_url — never falls back to direct.
    Timeout is set to darkweb_request_timeout_s (default 90s).
    """
    from crawl4ai import AsyncWebCrawler

    if not os.environ.get("HOME") or os.environ["HOME"] == "/nonexistent":
        os.environ["HOME"] = "/tmp"

    proxy_kwargs: dict = {"proxy": settings.darkweb_tor_proxy_url}

    try:
        from crawl4ai import BrowserConfig, CrawlerRunConfig

        try:
            browser_cfg = BrowserConfig(headless=True, enable_stealth=True, **proxy_kwargs)
        except TypeError:
            browser_cfg = BrowserConfig(headless=True, **proxy_kwargs)
        run_cfg = CrawlerRunConfig(
            page_timeout=settings.darkweb_request_timeout_s * 1000,
        )
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            yield crawler, run_cfg
    except (ImportError, TypeError):
        async with AsyncWebCrawler(**proxy_kwargs) as crawler:
            yield crawler, None


async def fetch_url_via_tor(
    url: str, crawler, run_cfg=None
) -> Optional[str]:
    """Fetch a .onion URL through Tor. Validates URL before fetching.

    Unlike fetch_url_with_crawler, this function:
    - Validates the URL is .onion (DNS leak prevention)
    - Uses Tor-specific timeout
    - trafilatura fallback also routes through Tor proxy explicitly
    - Never falls back to direct (non-Tor) fetching
    """
    validate_onion_url(url)

    try:
        if run_cfg is not None:
            result = await crawler.arun(url=url, config=run_cfg)
        else:
            result = await crawler.arun(url=url)
        clean = _extract_markdown(result)
        if clean and len(clean.strip()) >= 50:
            return clean.strip()
        log.debug("scraper.darkweb_crawl4ai_empty", url=url)
    except Exception as exc:
        log.warning("scraper.darkweb_crawl4ai_error", url=url, error=str(exc))

    # Fallback: trafilatura via Tor proxy (explicitly passed, not optional)
    try:
        return await _trafilatura_fetch(
            url, proxy_url=settings.darkweb_tor_proxy_url
        )
    except Exception as exc:
        log.warning("scraper.darkweb_fetch_failed", url=url, error=str(exc))
        return None
