"""News source adapter for RSS and Atom collection - issues #43, #42.

An outlet is configuration: a feed URL on a Source row. Feed autodiscovery is
deliberately absent, because several surveyed outlets publish feeds that no
document links to.

Body per entry:
  1. Parse the feed via feedparser (sync, run in executor).
  2. Read every body the entry offers - each content element and the summary -
     as text, and keep the longest. An element's presence is never taken as the
     presence of text: one surveyed outlet emits a content element on every item
     and never fills it, and its empty wrapper is longer in markup than the
     threshold it has to clear in words.
  3. Below rss_full_text_min_chars of text, fetch the article from the
     publisher, subject to robots.txt and the per-domain gap a crawl would give.
  4. A failed or paywalled fetch falls back to the feed body. An entry is never
     discarded while it still has text, and never stored while it has none.

Publication Time per entry:
  1. The date the feed states, ``published`` first and ``updated`` second.
     An Atom outlet that emits only ``updated`` is not an undated outlet.
  2. Otherwise the extraction library reads the article document.
  3. Otherwise None. Unknown stays unknown - writing the collection time here is
     what made Capture Time unusable as a timeline in the first place.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

import httpx
import structlog
from bs4 import BeautifulSoup

from .clean import is_paywall_page
from .fetch import FetchedArticle, check_robots_allowed, fetch_article, fetch_html
from .publication_time import (
    SIGNAL_FEED_PUBLISHED,
    SIGNAL_FEED_UPDATED,
    extract_publication_time,
    source_config_for,
)
from .rate_limiter import DomainRateLimiter
from .settings import settings
from .url_safety import validate_external_url_resolved

log = structlog.get_logger(__name__)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Every reader here is bounded, because a feed is adversarial input and its
# publisher chooses the size of everything in it. Each bound reports itself, so
# a truncated read does not read downstream as an outlet that publishes little.

# One wrapper element is enough to make a parse arbitrarily expensive.
_MAX_BODY_FRAGMENT_CHARS = 512 * 1024
# Per entry, because the fragment bound alone still lets one entry carry a
# thousand fragments.
_MAX_BODY_BLOCKS = 8
# Read after decompression, so a small compressed response that expands without
# limit is refused rather than buffered. A feed far past this is not a feed.
_MAX_FEED_BYTES = 16 * 1024 * 1024
# The article document the date is read from. extract_publication_time asks its
# caller for this, because the fetcher is what knows how much it fetched.
_MAX_ARTICLE_DOCUMENT_CHARS = 4 * 1024 * 1024


class _RateLimiter(Protocol):
    """The per-domain gap enforcer. DomainRateLimiter satisfies this."""

    async def wait(self, url: str) -> None: ...


@dataclass(frozen=True)
class RssItem:
    url: str
    title: str
    raw_text: str  # feed body or fetched article, always text and never markup
    # Publication time in UTC, or None when neither the feed nor the article
    # document asserted one.
    published_at: Optional[datetime] = None
    # Which evidence produced published_at, so an analyst can weigh it. None
    # exactly when published_at is None.
    published_at_signal: Optional[str] = None


# ---------------------------------------------------------------------------
# Feed parsing
# ---------------------------------------------------------------------------


def _fragment_text(fragment: str, url: str) -> str:
    """Return the readable text of an HTML feed fragment.

    Feeds carry bodies as escaped HTML. Its tags are not content, and counting
    them as length is what lets an empty wrapper pass for an article.
    """
    if not fragment:
        return ""
    if len(fragment) > _MAX_BODY_FRAGMENT_CHARS:
        log.warning(
            "rss.body_fragment_too_large",
            url=url,
            size=len(fragment),
            limit=_MAX_BODY_FRAGMENT_CHARS,
        )
        fragment = fragment[:_MAX_BODY_FRAGMENT_CHARS]
    text = BeautifulSoup(fragment, "lxml").get_text(separator=" ")
    # A non-breaking space is markup padding, not a word.
    return " ".join(text.replace("\xa0", " ").split())


def _entry_body(entry: Mapping[str, Any], url: str) -> str:
    """Return the richest body the entry offers, as text.

    Every candidate is measured after the markup comes off, and the longest
    wins. Preferring content over summary by position instead would hand the
    corpus an empty string from the one outlet that always emits an empty
    content element.
    """
    candidates: list[str] = []

    for block in (entry.get("content") or ())[:_MAX_BODY_BLOCKS]:
        value = block.get("value") if isinstance(block, Mapping) else None
        if value:
            candidates.append(_fragment_text(value, url))

    summary = entry.get("summary")
    if summary:
        candidates.append(_fragment_text(summary, url))

    if not candidates:
        return ""
    return max(candidates, key=len)


def _entry_published_at(
    entry: Mapping[str, Any],
) -> tuple[Optional[datetime], Optional[str]]:
    """Return the date the feed stated and the signal that produced it.

    feedparser exposes a parsed struct only when the entry carried a parseable
    date, and normalises it to UTC. ``updated`` is read after ``published``
    because an Atom outlet that emits only ``updated`` would otherwise read as
    an outlet that publishes no dates at all.
    """
    for key, signal in (
        ("published_parsed", SIGNAL_FEED_PUBLISHED),
        ("updated_parsed", SIGNAL_FEED_UPDATED),
    ):
        parsed = entry.get(key)
        if not parsed:
            continue
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc), signal
        except (TypeError, ValueError):
            continue
    return None, None


def parse_feed_items(
    xml_bytes: bytes,
    feed_url: str,
    *,
    limit: Optional[int] = None,
) -> list[RssItem]:
    """Parse RSS/Atom XML bytes with feedparser (blocking - call via executor).

    limit caps the entries read. It defaults to the poll cycle's cap, and the
    Backfill passes its own: a historic walk reads a page of archive at a time
    and has no reason to be bounded by what one live poll should collect.
    """
    import feedparser  # lazy import — only used here

    feed = feedparser.parse(xml_bytes)
    items: list[RssItem] = []
    effective_limit = settings.rss_max_items_per_fetch if limit is None else limit

    for entry in feed.entries[:effective_limit]:
        url: str = entry.get("link", "").strip()
        if not url:
            continue

        published_at, signal = _entry_published_at(entry)
        items.append(
            RssItem(
                url=url,
                title=entry.get("title", "").strip(),
                raw_text=_entry_body(entry, url),
                published_at=published_at,
                published_at_signal=signal,
            )
        )

    return items


# ---------------------------------------------------------------------------
# Article fetch
# ---------------------------------------------------------------------------


async def _fetch_feed_xml(feed_url: str) -> Optional[bytes]:
    """Fetch the feed document, up to the byte bound. None on any failure.

    Streamed rather than buffered whole, and measured after decompression. A
    ten megabyte gzip response expanding to gigabytes is one request, and
    ``resp.content`` would have it resident before anything could object.
    """
    try:
        async with httpx.AsyncClient(
            timeout=settings.scraper_request_timeout_s,
            follow_redirects=True,
            headers={"User-Agent": _BROWSER_UA},
        ) as client:
            async with client.stream("GET", feed_url) as resp:
                resp.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > _MAX_FEED_BYTES:
                        log.warning(
                            "rss.feed_too_large",
                            url=feed_url,
                            limit=_MAX_FEED_BYTES,
                        )
                        return None
                    chunks.append(chunk)
                return b"".join(chunks)
    except Exception as exc:
        log.warning("rss.feed_fetch_failed", url=feed_url, error=str(exc))
        return None


async def _fetch_article(
    url: str,
    limiter: _RateLimiter,
    *,
    document_only: bool = False,
) -> FetchedArticle:
    """Fetch one article link, under SSRF validation, robots.txt and the gap.

    The link is chosen by the feed, not by the operator, so it is validated
    before any request leaves - including the robots.txt request, which is made
    to a host the feed named and would otherwise be the unguarded one.

    The per-domain gap is taken before robots.txt for the same reason: an entry
    list naming a hundred hosts would otherwise issue a hundred unthrottled
    requests and only then start being polite.

    document_only fetches the markup without a browser. It is the path for an
    entry whose body is fine and whose date is not, where rendering buys
    nothing and a browser per entry is what an undated feed would cost.

    Returns an empty FetchedArticle rather than raising, because a body we
    could not fetch is a degraded entry and not a failed feed.
    """
    try:
        if not await validate_external_url_resolved(url):
            log.warning("rss.article_fetch_refused", url=url, reason="not an external address")
            return FetchedArticle(text=None, html=None)
        await limiter.wait(url)
        if not await check_robots_allowed(url):
            log.info("rss.article_fetch_disallowed", url=url, reason="robots.txt")
            return FetchedArticle(text=None, html=None)
        if document_only:
            return FetchedArticle(text=None, html=await fetch_html(url))
        return await fetch_article(url)
    except Exception as exc:
        log.debug("rss.article_fetch_failed", url=url, error=str(exc))
        return FetchedArticle(text=None, html=None)


def _body_from_article(article: FetchedArticle, url: str) -> Optional[str]:
    """Return the fetched body if it is usable, else None.

    A paywall interstitial is longer than the threshold and is not the article,
    so it is refused here rather than stored as one.
    """
    text = (article.text or "").strip()
    if len(text) < settings.rss_full_text_min_chars:
        return None
    if is_paywall_page(text):
        log.warning("rss.paywall_detected", url=url)
        return None
    return text


def _date_from_article(
    article: FetchedArticle, url: str
) -> tuple[Optional[datetime], Optional[str]]:
    """Read the Publication Time the article document asserts, if any."""
    if not article.html:
        log.info("rss.publication_time_unknown", url=url, reason="no document fetched")
        return None, None

    extracted = extract_publication_time(
        article.html,
        source_config_for(url),
        max_document_chars=_MAX_ARTICLE_DOCUMENT_CHARS,
    )
    if extracted is None:
        log.info("rss.publication_time_unknown", url=url, reason="no signal in document")
        return None, None
    return extracted.instant, extracted.signal


async def _resolve_item(item: RssItem, limiter: _RateLimiter) -> Optional[RssItem]:
    """Complete one entry: fetch its body and its date only where needed.

    Returns None when the entry has no text at all, which is the one case where
    an entry is dropped. Everything else degrades to what the feed gave.
    """
    body = item.raw_text
    published_at, signal = item.published_at, item.published_at_signal

    needs_body = len(body) < settings.rss_full_text_min_chars
    needs_date = published_at is None

    if needs_body or needs_date:
        article = await _fetch_article(item.url, limiter, document_only=not needs_body)
        if needs_body:
            fetched = _body_from_article(article, item.url)
            if fetched is not None:
                body = fetched
        if needs_date:
            published_at, signal = _date_from_article(article, item.url)

    body = body or item.title
    if not body.strip():
        log.info("rss.item_empty", url=item.url, reason="no body in feed or article")
        return None

    return RssItem(
        url=item.url,
        title=item.title,
        raw_text=body,
        published_at=published_at,
        published_at_signal=signal,
    )


async def fetch_rss_items(
    feed_url: str,
    *,
    limiter: Optional[_RateLimiter] = None,
) -> list[RssItem]:
    """Fetch and parse an RSS or Atom feed.

    Returns up to rss_max_items_per_fetch items, each carrying text rather than
    markup and a Publication Time wherever one is recoverable.

    limiter is the per-domain gap shared across the feeds of one poll cycle. A
    caller polling several feeds passes one, so two feeds from the same
    publisher do not each get their own allowance.

    Never raises — returns [] on any feed-level failure.
    """
    xml_bytes = await _fetch_feed_xml(feed_url)
    if xml_bytes is None:
        return []

    try:
        loop = asyncio.get_event_loop()
        items = await loop.run_in_executor(None, parse_feed_items, xml_bytes, feed_url)
    except Exception as exc:
        log.warning("rss.feed_parse_failed", url=feed_url, error=str(exc))
        return []

    if not items:
        log.debug("rss.feed_empty", url=feed_url)
        return []

    effective_limiter = limiter if limiter is not None else DomainRateLimiter()

    resolved: list[RssItem] = []
    for item in items:
        completed = await _resolve_item(item, effective_limiter)
        if completed is not None:
            resolved.append(completed)

    undated = sum(1 for item in resolved if item.published_at is None)
    if undated:
        log.info("rss.items_undated", feed_url=feed_url, count=undated, total=len(resolved))

    log.debug("rss.items_fetched", feed_url=feed_url, count=len(resolved))
    return resolved
