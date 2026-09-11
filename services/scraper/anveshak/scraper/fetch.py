"""URL fetch helpers — Crawl4AI primary, trafilatura fallback (criteria 1.2, 1.3, 1.10).

Browser reuse: create_shared_crawler() returns a context manager that spawns
one Chromium instance and reuses it for all URLs in a scrape_topic job.
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import structlog
import trafilatura
from anveshak.net.safe_fetch import DEFAULT_MAX_BYTES, Guard, fetch_bytes, fetch_text
from anveshak.net.url_safety import (
    ResolvedTarget,
    resolve_external_target,
    validate_external_url,
)

from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# robots.txt enforcement — cached per domain, TTL 1 hour
# ---------------------------------------------------------------------------

_robots_cache: dict[str, tuple[RobotFileParser | None, float]] = {}
_ROBOTS_CACHE_TTL = 3600  # 1 hour
# The key is a host named by scraped content, so the number of distinct keys is
# not ours to choose. Oldest entries go first once the cache is full, which
# costs a re-fetch and bounds the worker's memory.
_ROBOTS_CACHE_MAX_ENTRIES = 2048

# One User-Agent for every outbound fetch in this service, so a site sees one
# client rather than three, and a change of story is made in one place.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# A fetched document is served by whoever scraped content pointed us at, so its
# size is theirs to choose and ours to bound. Measured after decompression.
_MAX_DOCUMENT_BYTES = DEFAULT_MAX_BYTES

# robots.txt is a rules file, and one this size is not one. It is fetched from a
# host scraped content named, so it is bounded like everything else from there.
_MAX_ROBOTS_BYTES = 1024 * 1024


# ---------------------------------------------------------------------------
# Fetch guards — what each outbound path is allowed to reach
# ---------------------------------------------------------------------------

# A degraded guard says so once per process rather than once per request, which
# would bury the line under the fetch traffic it is describing.
_degradations_logged: set[str] = set()


def _log_degradation_once(reason: str, **fields: object) -> None:
    if reason in _degradations_logged:
        return
    _degradations_logged.add(reason)
    log.info("scraper.fetch_guard_degraded", reason=reason, **fields)


async def proxied_guard(url: str) -> Optional[ResolvedTarget]:
    """Judge a URL fetched through a proxy, which resolves the name itself.

    Nothing is resolved here, deliberately. Resolving a .onion name on this side
    is the DNS leak the Tor path exists to avoid, and resolving a clearnet name
    we are not going to connect to ourselves answers a question about our
    resolver rather than about the proxy's. What is left is the written form,
    plus the rule that a .onion fetch stays on .onion. The address inside the
    deployment is unreachable from the proxy anyway, which is the real control.
    """
    try:
        hostname = urlparse(url).hostname or ""
    except ValueError as exc:
        # "http://[::1/" and friends. A guard that throws is a guard the caller
        # has to defend against; this one refuses instead.
        log.warning("scraper.fetch_refused", url=url[:128], reason=f"unparseable url: {exc}")
        return None
    if hostname.endswith(".onion"):
        try:
            validate_onion_url(url)
        except ValueError as exc:
            log.warning("scraper.fetch_refused", url=url, reason=str(exc))
            return None
        _log_degradation_once("tor resolves the onion name, so no address is pinned")
        return ResolvedTarget(url=url, hostname=hostname, address=None)
    if not validate_external_url(url):
        return None
    _log_degradation_once("proxy resolves the name, so no address is pinned")
    return ResolvedTarget(url=url, hostname=hostname, address=None)


# A page pulls scripts, styles and images from the same few hosts, so a verdict
# is kept per host rather than taken per asset. Bounded, because the hosts are
# named by the page and their number is not ours to choose.
_BROWSER_VERDICT_MAX_ENTRIES = 1024

# Schemes the page answers itself. Nothing leaves the process for these, so
# there is no address to judge and refusing them only breaks inline images.
_INERT_SCHEMES = ("data:", "blob:", "about:", "chrome:", "chrome-extension:")


def browser_route_guard(guard: Guard) -> Callable[..., Awaitable[None]]:
    """Return a Playwright route handler that refuses non-external addresses.

    Crawl4AI navigates on its own: it resolves the name, follows the redirect
    and pulls every subresource without the httpx path ever seeing it. This is
    the one place inside the process where those requests can be judged, so the
    same guard the fetch path uses is applied to each of them.

    It narrows rather than closes: Chromium resolves the name again when it
    connects, so a name answering differently the second time is still fetched.
    Egress policy is what closes that. See docs/adr/0005-outbound-fetch-guard.md.
    """
    verdicts: dict[str, bool] = {}

    async def handle(route: Any, request: Any = None) -> None:
        target = request if request is not None else getattr(route, "request", None)
        url = getattr(target, "url", "") or ""
        if url.startswith(_INERT_SCHEMES):
            await route.continue_()
            return

        try:
            parsed = urlparse(url)
        except ValueError:
            log.warning("scraper.browser_request_blocked", url=url[:128], reason="unparseable url")
            await route.abort()
            return
        key = f"{parsed.scheme}://{parsed.netloc}"
        allowed = verdicts.get(key)
        if allowed is None:
            allowed = await guard(url) is not None
            if len(verdicts) >= _BROWSER_VERDICT_MAX_ENTRIES:
                verdicts.clear()
            verdicts[key] = allowed

        if not allowed:
            log.warning("scraper.browser_request_blocked", url=url)
            try:
                await route.abort()
            except Exception as exc:  # page closed mid-flight
                log.debug("scraper.browser_route_abort_failed", url=url, error=str(exc))
            return

        try:
            await route.continue_()
        except Exception as exc:  # page closed mid-flight
            log.debug("scraper.browser_route_continue_failed", url=url, error=str(exc))

    return handle


# Registering a service worker is the one way a page moves its requests out of
# reach of route interception. Removing the entry point is cheaper than chasing
# the requests, and a scraped page has no legitimate use for one.
_BLOCK_SERVICE_WORKERS_JS = (
    "Object.defineProperty(navigator, 'serviceWorker', { get: () => undefined });"
)


def _browser_websocket_guard(guard: Guard) -> Callable[..., Awaitable[None]]:
    """Return a handler that closes a WebSocket to an address the guard refuses."""

    async def handle(ws: Any) -> None:
        url = getattr(ws, "url", "") or ""
        if await guard(url) is not None:
            connect = getattr(ws, "connect_to_server", None)
            if connect is not None:
                connect()
            return
        log.warning("scraper.browser_websocket_blocked", url=url)
        try:
            close = getattr(ws, "close", None)
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result
        except Exception as exc:
            log.debug("scraper.browser_websocket_close_failed", url=url, error=str(exc))

    return handle


async def install_browser_address_guard(crawler: Any, guard: Guard) -> bool:
    """Route every browser request through guard. False when it could not be.

    Returning False is not a quiet failure: the deployment is then relying on
    egress policy alone for the browser, and the log line says so.
    """
    if not settings.scraper_browser_address_guard:
        log.info(
            "scraper.browser_address_guard_disabled",
            reason="scraper_browser_address_guard is false, egress policy is the only control",
        )
        return False

    set_hook = getattr(getattr(crawler, "crawler_strategy", None), "set_hook", None)
    if set_hook is None:
        log.warning(
            "scraper.browser_address_guard_unavailable",
            reason="this crawl4ai build exposes no page hook",
        )
        return False

    handler = browser_route_guard(guard)

    async def on_page_context_created(page: Any = None, context: Any = None, **kwargs: Any) -> Any:
        # The context covers every page opened under it, including a popup the
        # page opens itself, which a page-level route would miss.
        target = context if context is not None else page
        if target is None:
            log.warning("scraper.browser_address_guard_not_attached", reason="no page or context")
            return page
        try:
            await target.route("**/*", handler)
        except Exception as exc:
            log.warning("scraper.browser_address_guard_not_attached", error=str(exc))
            return page

        # A request a service worker makes bypasses route interception entirely,
        # so the page is stopped from registering one. Nothing we collect needs
        # offline caching, and an unrouted request is an unjudged address.
        try:
            await target.add_init_script(_BLOCK_SERVICE_WORKERS_JS)
        except Exception as exc:
            log.warning("scraper.browser_service_workers_not_blocked", error=str(exc))

        # Route interception does not cover WebSockets either. Where the
        # Playwright build can intercept them, the same guard decides.
        route_web_socket = getattr(target, "route_web_socket", None)
        if route_web_socket is None:
            log.info(
                "scraper.browser_websockets_unguarded",
                reason="this playwright build cannot intercept websockets",
            )
            return page
        try:
            await route_web_socket("**/*", _browser_websocket_guard(guard))
        except Exception as exc:
            log.warning("scraper.browser_websockets_unguarded", error=str(exc))
        return page

    try:
        set_hook("on_page_context_created", on_page_context_created)
    except Exception as exc:
        log.warning("scraper.browser_address_guard_unavailable", error=str(exc))
        return False
    return True


def guard_for(proxy_url: Optional[str]) -> Guard:
    """Return the guard that suits the path: resolved direct, written via proxy."""
    return proxied_guard if proxy_url else resolve_external_target


def _cache_robots(domain: str, entry: tuple[RobotFileParser | None, float]) -> None:
    """Store a robots.txt result, evicting the oldest entry when full."""
    if domain not in _robots_cache and len(_robots_cache) >= _ROBOTS_CACHE_MAX_ENTRIES:
        oldest = min(_robots_cache, key=lambda key: _robots_cache[key][1])
        del _robots_cache[oldest]
        log.debug("scraper.robots_cache_evicted", domain=oldest)
    _robots_cache[domain] = entry


# ---------------------------------------------------------------------------
# PDF URL detection
# ---------------------------------------------------------------------------


def is_pdf_url(url: str) -> bool:
    """Return True if the URL likely points to a PDF file."""
    path = urlparse(url).path.lower()
    return path.endswith(".pdf")


async def _fetch_robots_txt(robots_url: str) -> Optional[str]:
    """Fetch robots.txt through the guarded path. Returns None on failure.

    The host is one scraped content named, so this request is guarded like the
    article fetch it is about to permit. A robots.txt that redirects gets every
    hop validated rather than the first.
    """
    result = await fetch_bytes(
        robots_url,
        timeout=10,
        max_redirects=settings.scraper_max_redirects,
        limit=_MAX_ROBOTS_BYTES,
        expect_ok=False,
    )
    if result is None or result.status != 200:
        return None
    return result.body.decode(result.encoding or "utf-8", errors="replace")


async def check_robots_allowed(url: str) -> bool:
    """Check if URL is allowed by the site's robots.txt.

    Returns True (allow) when:
    - settings.respect_robots_txt is False
    - URL is a .onion address (no robots.txt on dark web)
    - robots.txt cannot be fetched (permissive default)
    - robots.txt allows the path

    Returns False when robots.txt explicitly disallows the path.
    """
    if not settings.respect_robots_txt:
        return True

    parsed = urlparse(url)
    if parsed.netloc.endswith(".onion"):
        return True

    domain = f"{parsed.scheme}://{parsed.netloc}"
    now = time.monotonic()

    # Check cache
    if domain in _robots_cache:
        parser, cached_at = _robots_cache[domain]
        if now - cached_at < _ROBOTS_CACHE_TTL:
            if parser is None:
                return True  # unreachable robots.txt → allow
            return parser.can_fetch("*", url)

    # Fetch and parse robots.txt
    robots_url = f"{domain}/robots.txt"
    content = await _fetch_robots_txt(robots_url)

    if content is None:
        _cache_robots(domain, (None, now))
        log.debug("scraper.robots_unreachable", domain=domain)
        return True

    parser = RobotFileParser()
    parser.parse(content.splitlines())
    _cache_robots(domain, (parser, now))

    allowed = parser.can_fetch("*", url)
    if not allowed:
        log.info("scraper.robots_blocked", url=url, domain=domain)
    return allowed


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
        # crawl4ai/Playwright needs a writable HOME; container user has none
        os.environ["HOME"] = "/tmp"  # nosec B108

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
            await install_browser_address_guard(crawler, guard_for(settings.tor_proxy_url))
            yield crawler, run_cfg
    except (ImportError, TypeError):
        async with AsyncWebCrawler(**proxy_kwargs) as crawler:
            await install_browser_address_guard(crawler, guard_for(settings.tor_proxy_url))
            yield crawler, None


@dataclass(frozen=True)
class FetchedArticle:
    """An article body together with the document it was extracted from.

    text is the readable body, or None when nothing was extracted.

    html is that same document as served, kept so a caller needing a signal the
    body does not carry reads it from this fetch rather than requesting the page
    a second time. A Publication Time lives in markup - JSON-LD, a meta tag, a
    time element - all of which extraction has already discarded by the time it
    returns text. None means the fetch path surfaced no document, and a caller
    that needs one treats that as a miss rather than as an outlet publishing no
    date.
    """

    text: Optional[str]
    html: Optional[str]


def _result_html(result: Any) -> Optional[str]:
    """Return the raw HTML a Crawl4AI result carried, or None."""
    html = getattr(result, "html", None)
    return html if isinstance(html, str) and html else None


def _extract_markdown(result: Any) -> Optional[str]:
    """Extract clean text from a Crawl4AI result object."""
    if not result.success:
        return None
    markdown = result.markdown
    if markdown is None:
        return None
    if hasattr(markdown, "raw_markdown"):
        return markdown.raw_markdown or None
    return str(markdown) or None


async def fetch_article_with_crawler(url: str, crawler, run_cfg=None) -> FetchedArticle:
    """Fetch an article using an existing shared crawler instance.

    The address is judged here, before the browser is handed it. The route guard
    judges it too, and that is the point: the route guard is conditional on a
    setting, on this crawl4ai build exposing a hook, and on the route attaching,
    and each of those failing leaves the navigation itself unchecked otherwise.

    Falls back to trafilatura if Crawl4AI returns empty.
    """
    if await guard_for(settings.tor_proxy_url)(url) is None:
        log.warning("scraper.fetch_refused", url=url, reason="not an external address")
        return FetchedArticle(text=None, html=None)

    try:
        if run_cfg is not None:
            result = await crawler.arun(url=url, config=run_cfg)
        else:
            result = await crawler.arun(url=url)
        clean = _extract_markdown(result)
        if clean and len(clean.strip()) >= 50:
            return FetchedArticle(text=clean.strip(), html=_result_html(result))
        log.debug("scraper.crawl4ai_empty", url=url)
    except Exception as exc:
        log.warning("scraper.crawl4ai_error", url=url, error=str(exc))

    try:
        return await _trafilatura_fetch_article(url)
    except Exception as exc:
        log.warning("scraper.fetch_failed", url=url, error=str(exc))
        return FetchedArticle(text=None, html=None)


async def fetch_url_with_crawler(url: str, crawler, run_cfg=None) -> Optional[str]:
    """Fetch a URL using an existing shared crawler instance, returning body text."""
    return (await fetch_article_with_crawler(url, crawler, run_cfg)).text


async def fetch_article(url: str) -> FetchedArticle:
    """Fetch an article standalone, returning its body and its document.

    Same path as fetch_url: Crawl4AI first, trafilatura second. The difference
    is only what survives the return, and a caller wanting the document asks
    for it here rather than fetching the page twice.
    """
    try:
        async with create_shared_crawler() as (crawler, run_cfg):
            return await fetch_article_with_crawler(url, crawler, run_cfg)
    except Exception as exc:
        log.warning("scraper.crawl4ai_error", url=url, error=str(exc))

    try:
        return await _trafilatura_fetch_article(url)
    except Exception as exc:
        log.warning("scraper.fetch_failed", url=url, error=str(exc))
        return FetchedArticle(text=None, html=None)


async def fetch_url(url: str) -> Optional[str]:
    """Fetch and extract clean text from a URL (standalone, creates its own browser).

    1. Tries Crawl4AI (JS-rendered, full-page extraction).
    2. Falls back to trafilatura (fast HTML extraction via httpx) if Crawl4AI
       returns an empty body or raises.
    Returns None on complete fetch failure — caller logs and skips (criteria 1.9).
    """
    return (await fetch_article(url)).text


# ---------------------------------------------------------------------------
# Recursive link extraction (depth-1 only)
# ---------------------------------------------------------------------------

_SKIP_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".mp4",
    ".mp3",
    ".avi",
    ".mov",
    ".zip",
    ".tar",
    ".gz",
}
# Note: .pdf removed — PDFs are now fetched and text-extracted by pdf_extract.py


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

    return links[: settings.scraper_max_links_per_page]


async def fetch_html(url: str) -> Optional[str]:
    """Fetch raw HTML from a URL through the guarded path, up to the byte bound.

    Every redirect hop is revalidated and the connection is made to the address
    that was validated, because the page is named by scraped content and a 302
    into the deployment is the shape of the attack.

    The document is bounded and measured after decompression, because the page
    is served by whoever the scraped content pointed us at and its size is
    therefore not ours to choose.
    """
    return await fetch_text(
        url,
        timeout=settings.scraper_request_timeout_s,
        headers={"User-Agent": BROWSER_UA},
        max_redirects=settings.scraper_max_redirects,
        limit=_MAX_DOCUMENT_BYTES,
    )


async def _trafilatura_fetch(url: str, *, proxy_url: Optional[str] = None) -> Optional[str]:
    """Download raw HTML via httpx then extract with trafilatura.

    Args:
        proxy_url: Explicit proxy override. If None, falls back to settings.tor_proxy_url.
    """
    return (await _trafilatura_fetch_article(url, proxy_url=proxy_url)).text


async def _trafilatura_fetch_article(
    url: str, *, proxy_url: Optional[str] = None
) -> FetchedArticle:
    """Download raw HTML through the guarded path, then extract with trafilatura.

    Args:
        proxy_url: Explicit proxy override. If None, falls back to settings.tor_proxy_url.
    """
    effective_proxy = proxy_url or settings.tor_proxy_url
    html = await fetch_text(
        url,
        timeout=settings.scraper_request_timeout_s,
        headers={"User-Agent": BROWSER_UA},
        guard=guard_for(effective_proxy),
        max_redirects=settings.scraper_max_redirects,
        limit=_MAX_DOCUMENT_BYTES,
        proxy=effective_proxy,
    )
    if html is None:
        return FetchedArticle(text=None, html=None)

    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
    return FetchedArticle(text=text or None, html=html or None)


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
            f"DNS leak prevention: {url} is not a .onion URL — refusing to fetch via clearnet"
        )
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Dark web URL must use http:// or https:// scheme, got {parsed.scheme}")


@asynccontextmanager
async def create_tor_crawler():
    """Create a Crawl4AI browser instance routed through the Tor SOCKS5 proxy.

    Always uses settings.darkweb_tor_proxy_url — never falls back to direct.
    Timeout is set to darkweb_request_timeout_s (default 90s).
    """
    from crawl4ai import AsyncWebCrawler

    if not os.environ.get("HOME") or os.environ["HOME"] == "/nonexistent":
        # crawl4ai/Playwright needs a writable HOME; container user has none
        os.environ["HOME"] = "/tmp"  # nosec B108

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
            await install_browser_address_guard(crawler, proxied_guard)
            yield crawler, run_cfg
    except (ImportError, TypeError):
        async with AsyncWebCrawler(**proxy_kwargs) as crawler:
            await install_browser_address_guard(crawler, proxied_guard)
            yield crawler, None


async def fetch_url_via_tor(url: str, crawler, run_cfg=None) -> Optional[str]:
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
        return await _trafilatura_fetch(url, proxy_url=settings.darkweb_tor_proxy_url)
    except Exception as exc:
        log.warning("scraper.darkweb_fetch_failed", url=url, error=str(exc))
        return None
