"""ARQ job definitions — Scraper service (criteria 1.1–1.10, 4.1).

WorkerSettings is the entry point for `arq services.scraper.jobs.WorkerSettings`.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, UTC
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import arq
from arq import cron
import asyncpg
import structlog
from arq.connections import RedisSettings

from anveshak.media.downloader import download_media_asset

import hashlib

from .clean import clean_extracted_text, compute_clean_hash, score_content_quality, extract_title
from .fetch import (
    fetch_url, fetch_url_with_crawler, create_shared_crawler,
    fetch_html, extract_article_links,
    create_tor_crawler, fetch_url_via_tor,
    check_robots_allowed,
)
from .health import run_all_health_checks
from .lang import detect_language
from .rate_limiter import DomainRateLimiter
from .rss import fetch_rss_items
from .metrics import (
    scraper_items_fetched_total, scraper_fetch_errors_total,
    scraper_fetch_duration_seconds, scraper_darkweb_fetch_duration_seconds,
    arq_jobs_failed_total, scraper_content_quality_total,
    scraper_url_seen_skip_total, scraper_links_discovered,
)
from .normalise import compute_content_hash
from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL — module-level constants (testable, consistent with patterns.md)
# ---------------------------------------------------------------------------

SQL_GET_TOPIC = "SELECT id, org_id FROM topics WHERE id = $1"

SQL_GET_WEB_SOURCES = """
    SELECT s.id, s.url_or_handle, s.credibility_score
    FROM sources s
    JOIN topic_sources ts ON ts.source_id = s.id
    WHERE ts.topic_id = $1
      AND s.is_active = TRUE AND s.platform = 'web'
      AND s.health_status != 'down'
"""

SQL_GET_RSS_SOURCES = """
    SELECT s.id, s.url_or_handle, s.credibility_score
    FROM sources s
    JOIN topic_sources ts ON ts.source_id = s.id
    WHERE ts.topic_id = $1
      AND s.is_active = TRUE AND s.platform = 'rss'
      AND s.health_status != 'down'
"""

SQL_INSERT_CONTENT = """
    INSERT INTO content_items (
        id, topic_id, source_id, raw_text, clean_text, language,
        content_hash, url, captured_at, credibility_score_at_capture,
        created_at, updated_at, labels,
        content_quality, clean_hash, title, org_id
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
            $14, $15, $16, $17)
    ON CONFLICT(content_hash) DO NOTHING
    RETURNING id
"""

SQL_INSERT_MEDIA_ASSET = """
    INSERT INTO media_assets (
        id, content_item_id, asset_type, storage_path, content_hash, labels
    )
    VALUES ($1, $2, $3, $4, $5,
            '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT (content_hash) DO NOTHING
"""

SQL_GET_DARKWEB_SOURCES = """
    SELECT s.id, s.url_or_handle, s.credibility_score
    FROM sources s
    JOIN topic_sources ts ON ts.source_id = s.id
    WHERE ts.topic_id = $1
      AND s.is_active = TRUE AND s.platform = 'darkweb'
      AND s.health_status != 'down'
"""

SQL_GET_MEDIA_ASSET_BY_HASH = "SELECT id FROM media_assets WHERE content_hash = $1"

_LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'
_DARKWEB_LABELS_JSON = '{"classification":"RESTRICTED","domain":"darkweb","owner_org":"anveshak"}'

_URL_SEEN_PREFIX = "scraper:seen:"


def _url_seen_key(url: str) -> str:
    """Redis key for URL-seen tracking."""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return f"{_URL_SEEN_PREFIX}{digest}"


async def _is_url_seen(redis, url: str) -> bool:
    """Return True if URL was fetched within the TTL window."""
    if not settings.scraper_url_seen_enabled:
        return False
    try:
        result = await redis.get(_url_seen_key(url))
        return result is not None
    except Exception as exc:
        log.warning("scraper.url_seen_check_failed", url=url, error=str(exc))
        return False  # fail open


async def _mark_url_seen(redis, url: str) -> None:
    """Record URL as seen with TTL. Errors are logged and ignored."""
    if not settings.scraper_url_seen_enabled:
        return
    try:
        await redis.set(_url_seen_key(url), "1", ex=settings.scraper_url_seen_ttl_s)
    except Exception as exc:
        log.warning("scraper.url_seen_mark_failed", url=url, error=str(exc))


# ---------------------------------------------------------------------------
# Media URL extraction from HTML (stdlib html.parser — no extra deps)
# ---------------------------------------------------------------------------

class _MediaURLExtractor(HTMLParser):
    """Extract absolute image and video source URLs from raw HTML."""

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag not in {"img", "video", "source"}:
            return
        attrs_dict = dict(attrs)
        raw = (
            attrs_dict.get("src")
            or attrs_dict.get("data-src")
            or attrs_dict.get("data-lazy-src")
        )
        if not raw:
            return
        abs_url = urljoin(self.base_url, raw)
        parsed = urlparse(abs_url)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            self.urls.append(abs_url)


def _extract_media_urls(html: str, base_url: str) -> list[str]:
    extractor = _MediaURLExtractor(base_url)
    extractor.feed(html)
    return extractor.urls[:20]  # cap at 20 media URLs per page


# ---------------------------------------------------------------------------
# ARQ job
# ---------------------------------------------------------------------------

async def scrape_topic(ctx: dict, topic_id: str) -> int:
    """Scrape all active web sources for a topic.

    Criteria 1.1: ARQ function exists.
    Criteria 1.4–1.9: hash, dedup, credibility snapshot, timeout, concurrency,
                       error isolation.
    Criteria 4.1: images on scraped pages downloaded → media_assets rows created.
    Returns the number of new content_items inserted (duplicates excluded).
    """
    db_pool: asyncpg.Pool = ctx["db_pool"]
    redis = ctx["redis"]   # ARQ Redis pool — used to dispatch vision jobs

    async with db_pool.acquire() as conn:
        topic = await conn.fetchrow(SQL_GET_TOPIC, topic_id)
        if not topic:
            log.warning("scraper.topic_not_found", topic_id=topic_id)
            return 0
        sources = await conn.fetch(SQL_GET_WEB_SOURCES, topic_id)

    if not sources:
        log.debug("scraper.no_sources", topic_id=topic_id)
        return 0

    semaphore = asyncio.Semaphore(settings.scraper_concurrency)  # criteria 1.8
    counter: dict[str, int] = {"inserted": 0}
    seen_media_urls: set[str] = set()  # URL-level dedup across pages in this job

    async def _insert_content(
        raw_text: str, url: str, source_id: str, credibility_score: float,
    ) -> Optional[str]:
        """Insert a content item, return content_item_id or None if dedup hit."""
        content_hash = compute_content_hash(raw_text)
        cleaned = clean_extracted_text(raw_text)
        effective_clean = cleaned or raw_text
        quality, gate = score_content_quality(raw_text, effective_clean)
        scraper_content_quality_total.labels(quality=quality, gate=gate).inc()
        c_hash = compute_clean_hash(effective_clean)
        title = extract_title(effective_clean)
        language = detect_language(effective_clean)
        now = datetime.now(UTC)
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                SQL_INSERT_CONTENT,
                str(uuid.uuid4()),
                topic_id,
                source_id,
                raw_text,
                effective_clean,
                language,
                content_hash,
                url,
                now,
                credibility_score,
                now,
                now,
                _LABELS_JSON,
                quality,
                c_hash,
                title,
                topic["org_id"],
            )
        if result is not None:
            content_item_id = result["id"]
            counter["inserted"] += 1
            scraper_items_fetched_total.labels(
                topic_id=topic_id, source_platform="web"
            ).inc()
            try:
                await redis.enqueue_job(
                    "analyse_content", content_item_id,
                    _queue_name="arq:analyst",
                )
            except Exception as exc:
                log.warning(
                    "scraper.enqueue_analyse_failed",
                    content_item_id=content_item_id,
                    error=str(exc),
                )
            return content_item_id
        return None

    domain_limiter = DomainRateLimiter()

    async def _process(source: asyncpg.Record, crawler, run_cfg) -> None:
        async with semaphore:
            url: str = source["url_or_handle"]
            source_id: str = source["id"]
            cred_score = float(source["credibility_score"])
            try:
                # Enforce robots.txt (criteria 1.11)
                if not await check_robots_allowed(url):
                    return

                if settings.scraper_follow_links:
                    # --- Link-following mode: source page is for discovery only ---
                    # Fetch source page HTML once for link extraction (NOT stored as content)
                    html = await fetch_html(url)
                    if not html:
                        log.info("scraper.source_page_empty", url=url)
                        return
                    article_links = extract_article_links(html, url)
                    scraper_links_discovered.observe(len(article_links))
                    log.debug(
                        "scraper.links_discovered",
                        url=url,
                        count=len(article_links),
                    )
                    for link_url in article_links:
                        try:
                            # URL-seen check — skip if already fetched within TTL
                            if await _is_url_seen(redis, link_url):
                                log.debug("scraper.url_seen_skip", url=link_url)
                                scraper_url_seen_skip_total.inc()
                                continue
                            # Per-domain rate limiting
                            await domain_limiter.wait(link_url)
                            link_fetched = await asyncio.wait_for(
                                fetch_url_with_crawler(link_url, crawler, run_cfg),
                                timeout=settings.scraper_request_timeout_s,
                            )
                            if link_fetched:
                                content_item_id = await _insert_content(
                                    link_fetched, link_url, source_id, cred_score,
                                )
                                await _mark_url_seen(redis, link_url)
                                if content_item_id and settings.media_download_enabled:
                                    await _download_page_media(
                                        page_url=link_url,
                                        topic_id=topic_id,
                                        content_item_id=content_item_id,
                                        db_pool=db_pool,
                                        redis=redis,
                                        seen_media_urls=seen_media_urls,
                                    )
                        except asyncio.TimeoutError:
                            log.debug("scraper.link_timeout", url=link_url)
                        except Exception as exc:
                            log.debug("scraper.link_failed", url=link_url, error=str(exc))
                else:
                    # --- Direct article mode: source URL IS the content ---
                    import time as _time
                    _t0 = _time.monotonic()
                    fetched_text = await asyncio.wait_for(
                        fetch_url_with_crawler(url, crawler, run_cfg),
                        timeout=settings.scraper_request_timeout_s,
                    )
                    scraper_fetch_duration_seconds.observe(_time.monotonic() - _t0)
                    if not fetched_text:
                        return

                    content_item_id = await _insert_content(fetched_text, url, source_id, cred_score)

                    # Politeness delay between fetches (criteria 1.11)
                    if settings.scraper_default_delay_s > 0:
                        await asyncio.sleep(settings.scraper_default_delay_s)

                    if content_item_id and settings.media_download_enabled:
                        await _download_page_media(
                            page_url=url,
                            topic_id=topic_id,
                            content_item_id=content_item_id,
                            db_pool=db_pool,
                            redis=redis,
                            seen_media_urls=seen_media_urls,
                        )

            except asyncio.TimeoutError:
                scraper_fetch_errors_total.labels(error_type="TimeoutError").inc()
                log.warning("scraper.source_timeout", url=url)
            except Exception as exc:
                scraper_fetch_errors_total.labels(
                    error_type=type(exc).__name__
                ).inc()
                log.warning("scraper.source_failed", url=url, error=str(exc))

    # Shared browser instance — one Chromium for the entire job
    try:
        async with create_shared_crawler() as (crawler, run_cfg):
            await asyncio.gather(*[_process(s, crawler, run_cfg) for s in sources])
    except Exception as exc:
        log.error("scraper.browser_launch_failed", error=str(exc))
        # Fallback: process without shared browser (uses trafilatura only)
        async def _process_fallback(source: asyncpg.Record) -> None:
            async with semaphore:
                url = source["url_or_handle"]
                try:
                    if not await check_robots_allowed(url):
                        return
                    fetched_text = await fetch_url(url)
                    if fetched_text:
                        await _insert_content(
                            fetched_text, url, source["id"],
                            float(source["credibility_score"]),
                        )
                        if settings.scraper_default_delay_s > 0:
                            await asyncio.sleep(settings.scraper_default_delay_s)
                except Exception as exc:
                    log.warning("scraper.fallback_failed", url=url, error=str(exc))
        await asyncio.gather(*[_process_fallback(s) for s in sources])

    log.info(
        "scraper.job_done",
        topic_id=topic_id,
        total_sources=len(sources),
        inserted=counter["inserted"],
    )
    return counter["inserted"]


async def poll_rss_sources(ctx: dict, topic_id: str) -> int:
    """Poll all active RSS sources and ingest new entries for a topic.

    Each feed entry is deduplicated by content_hash (SHA-256 of normalised text).
    Full article text is fetched when the feed summary is too short (< rss_full_text_min_chars).
    Returns the number of new content_items inserted.
    """
    db_pool: asyncpg.Pool = ctx["db_pool"]
    redis = ctx["redis"]   # ARQ Redis pool — enqueue analyse_content

    async with db_pool.acquire() as conn:
        topic = await conn.fetchrow(SQL_GET_TOPIC, topic_id)
        if not topic:
            log.warning("rss.topic_not_found", topic_id=topic_id)
            return 0
        sources = await conn.fetch(SQL_GET_RSS_SOURCES, topic_id)

    if not sources:
        log.debug("rss.no_sources", topic_id=topic_id)
        return 0

    semaphore = asyncio.Semaphore(settings.scraper_concurrency)
    counter: dict[str, int] = {"inserted": 0}

    async def _process_feed(source: asyncpg.Record) -> None:
        async with semaphore:
            feed_url: str = source["url_or_handle"]
            try:
                items = await fetch_rss_items(feed_url)
                for item in items:
                    try:
                        content_hash = compute_content_hash(item.raw_text)
                        cleaned = clean_extracted_text(item.raw_text)
                        effective_clean = cleaned or item.raw_text
                        quality, gate = score_content_quality(item.raw_text, effective_clean)
                        scraper_content_quality_total.labels(quality=quality, gate=gate).inc()
                        c_hash = compute_clean_hash(effective_clean)
                        title = extract_title(effective_clean)
                        rss_language = detect_language(effective_clean)
                        now = datetime.now(UTC)

                        async with db_pool.acquire() as conn:
                            result = await conn.fetchrow(
                                SQL_INSERT_CONTENT,
                                str(uuid.uuid4()),
                                topic_id,
                                source["id"],
                                item.raw_text,              # raw_text (preserved as-is)
                                effective_clean,            # clean_text (cleaned)
                                rss_language,               # language — detected at scrape time
                                content_hash,
                                item.url,
                                item.published_at,  # captured_at = article publish time
                                float(source["credibility_score"]),
                                now,                # created_at
                                now,                # updated_at
                                _LABELS_JSON,
                                quality,
                                c_hash,
                                title,
                                topic["org_id"],
                            )

                        if result is not None:
                            rss_item_id = result["id"]
                            counter["inserted"] += 1
                            scraper_items_fetched_total.labels(
                                topic_id=topic_id, source_platform="rss"
                            ).inc()
                            try:
                                await redis.enqueue_job(
                                    "analyse_content", rss_item_id,
                                    _queue_name="arq:analyst",
                                )
                            except Exception as enq_exc:
                                log.warning(
                                    "rss.enqueue_analyse_failed",
                                    content_item_id=rss_item_id,
                                    error=str(enq_exc),
                                )
                            log.debug(
                                "rss.item_inserted",
                                topic_id=topic_id,
                                url=item.url,
                                title=item.title[:60],
                            )
                    except Exception as exc:
                        log.warning("rss.item_failed", url=item.url, error=str(exc))

            except Exception as exc:
                scraper_fetch_errors_total.labels(error_type=type(exc).__name__).inc()
                log.warning("rss.feed_failed", feed_url=feed_url, error=str(exc))

    await asyncio.gather(*[_process_feed(s) for s in sources])
    log.info(
        "rss.job_done",
        topic_id=topic_id,
        total_feeds=len(sources),
        inserted=counter["inserted"],
    )
    return counter["inserted"]


async def scrape_darkweb_topic(ctx: dict, topic_id: str) -> int:
    """Scrape all active dark web (.onion) sources for a topic via Tor.

    Routes all traffic through the Tor SOCKS5 proxy with DNS leak protection.
    Uses lower concurrency and higher timeouts than clearnet scraping.
    No recursive link following or media download (Phase 1 safety).
    Returns the number of new content_items inserted.
    """
    db_pool: asyncpg.Pool = ctx["db_pool"]
    redis = ctx["redis"]   # ARQ Redis pool — enqueue analyse_content

    async with db_pool.acquire() as conn:
        topic = await conn.fetchrow(SQL_GET_TOPIC, topic_id)
        if not topic:
            log.warning("darkweb.topic_not_found", topic_id=topic_id)
            return 0
        sources = await conn.fetch(SQL_GET_DARKWEB_SOURCES, topic_id)

    if not sources:
        log.debug("darkweb.no_sources", topic_id=topic_id)
        return 0

    semaphore = asyncio.Semaphore(settings.darkweb_concurrency)
    counter: dict[str, int] = {"inserted": 0}

    async def _insert_darkweb_content(
        raw_text: str, url: str, source_id: str, credibility_score: float,
    ) -> Optional[str]:
        """Insert a dark web content item with RESTRICTED labels."""
        content_hash = compute_content_hash(raw_text)
        cleaned = clean_extracted_text(raw_text)
        effective_clean = cleaned or raw_text
        quality, gate = score_content_quality(raw_text, effective_clean)
        scraper_content_quality_total.labels(quality=quality, gate=gate).inc()
        c_hash = compute_clean_hash(effective_clean)
        title = extract_title(effective_clean)
        dw_language = detect_language(effective_clean)
        now = datetime.now(UTC)
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                SQL_INSERT_CONTENT,
                str(uuid.uuid4()),
                topic_id,
                source_id,
                raw_text,
                effective_clean,
                dw_language,
                content_hash,
                url,
                now,
                credibility_score,
                now,
                now,
                _DARKWEB_LABELS_JSON,
                quality,
                c_hash,
                title,
                topic["org_id"],
            )
        if result is not None:
            content_item_id = result["id"]
            counter["inserted"] += 1
            scraper_items_fetched_total.labels(
                topic_id=topic_id, source_platform="darkweb"
            ).inc()
            try:
                await redis.enqueue_job(
                    "analyse_content", content_item_id,
                    _queue_name="arq:analyst",
                )
            except Exception as exc:
                log.warning(
                    "darkweb.enqueue_analyse_failed",
                    content_item_id=content_item_id,
                    error=str(exc),
                )
            return content_item_id
        return None

    async def _process_onion(source: asyncpg.Record, crawler, run_cfg) -> None:
        async with semaphore:
            url: str = source["url_or_handle"]
            source_id: str = source["id"]
            cred_score = float(source["credibility_score"])
            try:
                import time as _time
                _t0 = _time.monotonic()
                fetched_text = await asyncio.wait_for(
                    fetch_url_via_tor(url, crawler, run_cfg),
                    timeout=settings.darkweb_request_timeout_s,
                )
                scraper_darkweb_fetch_duration_seconds.observe(
                    _time.monotonic() - _t0
                )
                if not fetched_text:
                    return
                await _insert_darkweb_content(
                    fetched_text, url, source_id, cred_score
                )
            except asyncio.TimeoutError:
                scraper_fetch_errors_total.labels(
                    error_type="DarkwebTimeoutError"
                ).inc()
                log.warning("darkweb.source_timeout", url=url)
            except ValueError as exc:
                # DNS leak prevention — should never happen if sources are validated
                log.error("darkweb.dns_leak_blocked", url=url, error=str(exc))
            except Exception as exc:
                scraper_fetch_errors_total.labels(
                    error_type=type(exc).__name__
                ).inc()
                log.warning("darkweb.source_failed", url=url, error=str(exc))

    try:
        async with create_tor_crawler() as (crawler, run_cfg):
            await asyncio.gather(
                *[_process_onion(s, crawler, run_cfg) for s in sources]
            )
    except Exception as exc:
        log.error("darkweb.tor_crawler_failed", error=str(exc))
        # Fallback: trafilatura-only via Tor (no browser)
        from .fetch import _trafilatura_fetch

        async def _fallback(source: asyncpg.Record) -> None:
            async with semaphore:
                url = source["url_or_handle"]
                try:
                    from .fetch import validate_onion_url
                    validate_onion_url(url)
                    fetched_text = await _trafilatura_fetch(
                        url, proxy_url=settings.darkweb_tor_proxy_url
                    )
                    if fetched_text:
                        await _insert_darkweb_content(
                            fetched_text, url, source["id"],
                            float(source["credibility_score"]),
                        )
                except Exception as exc:
                    log.warning(
                        "darkweb.fallback_failed", url=url, error=str(exc)
                    )

        await asyncio.gather(*[_fallback(s) for s in sources])

    log.info(
        "darkweb.job_done",
        topic_id=topic_id,
        total_sources=len(sources),
        inserted=counter["inserted"],
    )
    return counter["inserted"]


async def _download_page_media(
    page_url: str,
    topic_id: str,
    content_item_id: str,
    db_pool: asyncpg.Pool,
    redis,
    seen_media_urls: set[str] | None = None,
) -> None:
    """Download images/videos linked from a scraped page.

    Criteria 4.1: images from scraped pages saved to media/{topic_id}/{date}/{hash}.ext
    Criteria 4.3–4.4: media_assets rows created with content_hash of raw bytes.
    Errors never propagate — media failure never aborts content ingestion.
    """
    try:
        import httpx
        async with httpx.AsyncClient(
            timeout=settings.scraper_request_timeout_s,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Anveshak/1.0)"},
        ) as client:
            resp = await client.get(page_url)
            resp.raise_for_status()
            html = resp.text
    except Exception as exc:
        log.debug("scraper.media_page_fetch_failed", url=page_url, error=str(exc))
        return

    media_urls = _extract_media_urls(html, page_url)
    if not media_urls:
        return

    from .url_safety import validate_external_url

    for media_url in media_urls:
        if not validate_external_url(media_url):
            continue
        if seen_media_urls is not None:
            if media_url in seen_media_urls:
                continue
            seen_media_urls.add(media_url)
        try:
            dl = await download_media_asset(
                url=media_url,
                topic_id=topic_id,
                storage_root=settings.media_storage_root,
                max_size_mb=settings.media_max_size_mb,
                timeout_s=settings.scraper_request_timeout_s,
            )
            if dl is None:
                continue

            # Insert media_assets row — ON CONFLICT(content_hash) DO NOTHING (criteria 4.34)
            async with db_pool.acquire() as conn:
                await conn.execute(
                    SQL_INSERT_MEDIA_ASSET,
                    str(uuid.uuid4()),
                    content_item_id,
                    dl.asset_type,
                    dl.storage_path,
                    dl.content_hash,
                )
                row = await conn.fetchrow(SQL_GET_MEDIA_ASSET_BY_HASH, dl.content_hash)

            if row:
                await redis.enqueue_job("run_vision_analysis", row["id"], _queue_name="arq:vision")
                log.debug(
                    "scraper.vision_dispatched",
                    media_asset_id=row["id"],
                    asset_type=dl.asset_type,
                )

        except Exception as exc:
            log.debug("scraper.media_download_failed", url=media_url, error=str(exc))


# ---------------------------------------------------------------------------
# ARQ worker lifecycle
# ---------------------------------------------------------------------------

async def check_all_source_health(ctx: dict) -> int:
    """Daily health check for all active web and RSS sources.

    Updates health_status, consecutive_failures, health_error, last_checked_at
    for every active source. Staggered 1s between checks to avoid hammering.
    Returns count of sources checked.
    """
    db_pool: asyncpg.Pool = ctx["db_pool"]
    checked = await run_all_health_checks(db_pool)
    log.info("health.daily_check_done", sources_checked=checked)
    return checked


async def on_startup(ctx: dict) -> None:
    ctx["db_pool"] = await asyncpg.create_pool(
        settings.postgres_url, min_size=2, max_size=5
    )
    log.info("scraper_worker.ready", concurrency=settings.scraper_concurrency)


async def on_shutdown(ctx: dict) -> None:
    await ctx["db_pool"].close()
    log.info("scraper_worker.stopped")


async def on_job_result(ctx: dict, result) -> None:  # type: ignore[type-arg]
    """8A.19 — increment failure counter when an ARQ job exhausts all retries."""
    if getattr(result, "success", True) is False:
        job_name = getattr(result, "function", "unknown")
        arq_jobs_failed_total.labels(job_name=job_name).inc()
        log.warning("scraper_worker.job_failed", job=job_name)


class WorkerSettings:
    """Entry point: arq services.scraper.jobs.WorkerSettings"""

    queue_name = "arq:scraper"   # Isolated queue — avoids cross-worker job theft

    functions = [
        # 8C.5 — scrape_topic: ON CONFLICT DO NOTHING makes it safe to retry
        arq.func(scrape_topic, max_tries=2),
        arq.func(poll_rss_sources, max_tries=2),
        arq.func(scrape_darkweb_topic, max_tries=2),
        arq.func(check_all_source_health, max_tries=1),
    ]
    cron_jobs = [
        # Daily health check at 02:00 UTC — low traffic window
        cron(check_all_source_health, hour=2, minute=0),
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    on_job_result = on_job_result
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = settings.scraper_concurrency
    job_timeout = settings.scraper_job_timeout_s  # default 300s (5 min)
    keep_result = 3600   # 8C.6 — keep results 1h
