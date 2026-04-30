"""RSS/Atom feed fetcher for Anveshak scraper.

Fetch strategy per entry:
  1. Parse feed via feedparser (sync, run in executor).
  2. If entry summary >= rss_full_text_min_chars  → use summary as content.
  3. If entry summary <  rss_full_text_min_chars  → fetch full article via fetch_url()
     (Crawl4AI → trafilatura fallback already handled there).
  4. If full fetch fails → fall back to summary anyway — never discard an entry.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog

from .clean import is_paywall_page
from .fetch import fetch_url
from .settings import settings

log = structlog.get_logger(__name__)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class RssItem:
    url: str
    title: str
    raw_text: str          # summary or full article text
    published_at: datetime  # always timezone-aware


def _parse_feed_sync(xml_bytes: bytes, feed_url: str) -> list[RssItem]:
    """Parse RSS/Atom XML bytes with feedparser (blocking — call via executor)."""
    import feedparser  # lazy import — only used here

    feed = feedparser.parse(xml_bytes)
    items: list[RssItem] = []

    for entry in feed.entries[: settings.rss_max_items_per_fetch]:
        url: str = entry.get("link", "").strip()
        if not url:
            continue

        title: str = entry.get("title", "").strip()

        # Prefer content over summary (content is fuller on some feeds)
        raw_summary = ""
        if entry.get("content"):
            raw_summary = entry["content"][0].get("value", "")
        if not raw_summary:
            raw_summary = entry.get("summary", "")
        raw_summary = raw_summary.strip()

        # Published datetime — fall back to now if unparseable
        published_at: datetime
        published_parsed = entry.get("published_parsed")
        if published_parsed:
            published_at = datetime(*published_parsed[:6], tzinfo=timezone.utc)
        else:
            published_at = datetime.now(timezone.utc)

        items.append(RssItem(
            url=url,
            title=title,
            raw_text=raw_summary,
            published_at=published_at,
        ))

    return items


async def fetch_rss_items(feed_url: str) -> list[RssItem]:
    """Fetch and parse an RSS/Atom feed.

    Returns a list of RssItem — up to rss_max_items_per_fetch entries.
    Each item's raw_text is either the feed summary (if long enough) or
    the full article fetched via fetch_url().
    Never raises — returns [] on any feed-level failure.
    """
    # Step 1: Fetch the raw feed XML
    try:
        async with httpx.AsyncClient(
            timeout=settings.scraper_request_timeout_s,
            follow_redirects=True,
            headers={"User-Agent": _BROWSER_UA},
        ) as client:
            resp = await client.get(feed_url)
            resp.raise_for_status()
            xml_bytes = resp.content
    except Exception as exc:
        log.warning("rss.feed_fetch_failed", url=feed_url, error=str(exc))
        return []

    # Step 2: Parse (feedparser is sync — run in thread executor)
    try:
        loop = asyncio.get_event_loop()
        items = await loop.run_in_executor(None, _parse_feed_sync, xml_bytes, feed_url)
    except Exception as exc:
        log.warning("rss.feed_parse_failed", url=feed_url, error=str(exc))
        return []

    if not items:
        log.debug("rss.feed_empty", url=feed_url)
        return []

    # Step 3: Enrich short summaries with full article text
    enriched: list[RssItem] = []
    for item in items:
        if len(item.raw_text) >= settings.rss_full_text_min_chars:
            enriched.append(item)
            continue

        # Summary too short — fetch full article
        try:
            full_text = await fetch_url(item.url)
            if full_text and len(full_text.strip()) >= settings.rss_full_text_min_chars:
                stripped = full_text.strip()
                if is_paywall_page(stripped):
                    log.warning("rss.paywall_detected", url=item.url)
                else:
                    enriched.append(RssItem(
                        url=item.url,
                        title=item.title,
                        raw_text=stripped,
                        published_at=item.published_at,
                    ))
                    continue
        except Exception as exc:
            log.debug("rss.full_fetch_failed", url=item.url, error=str(exc))

        # Full fetch failed or still too short — keep summary if it has any content
        if item.raw_text or item.title:
            enriched.append(RssItem(
                url=item.url,
                title=item.title,
                raw_text=item.raw_text or item.title,
                published_at=item.published_at,
            ))

    log.debug("rss.items_fetched", feed_url=feed_url, count=len(enriched))
    return enriched
