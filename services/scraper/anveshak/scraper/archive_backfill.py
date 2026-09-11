"""Archive Backfill discovery and article body fetch - issue #44.

No feed reaches back far enough to collect a narrative that began months ago.
Across the surveyed outlets the deepest feed covers about seven weeks and most
cover less than a day, so recency-only collection can never analyse a story
that started before we knew to look for it.

This module is the historic route: it discovers article URLs by date, then
fetches their bodies. An outlet is configuration, not code.

Three discovery mechanisms, each verified to reach the required window:

  1. Monthly archive sitemaps, where the date is encoded in the URL path and
     nothing has to be fetched to filter a month by date.
  2. Paginated feeds, where a page parameter walks backwards through history.
  3. Topic or tag feeds, where the outlet has them and they paginate.

At least one surveyed topic feed serves page one again once its real depth is
exhausted, with a 200 status and real items. Nothing about that response says
stop, so the walk fingerprints each page's URL set and stops when one repeats.
Without that a crawler loops forever, re-ingesting the same items.

Path date formats differ across outlets - unpadded numeric, zero-padded
numeric, abbreviated month name, and a date appended to the slug as a suffix -
so one pattern cannot serve. The format is per-outlet configuration, and a
wrong declaration reads as no date rather than as a wrong date.

Bodies are fetched from the publisher. A client error falls back to archive
rehydration, which is also the better evidence: it returns the article as
published, so a later silent edit does not change what we hold. A server error
is the publisher failing rather than the article being gone, and is left to a
retry instead.

Archive rehydration discloses which URLs are being collected to the archive
operator, who is outside the deployment boundary. That is a disclosure of
collection targets - which outlets, which stories, which dates - and it is the
reason the route is a setting rather than an assumption. It is on by default,
because the corpus this was built for needs articles their publishers no longer
serve, and an operator who cannot accept the disclosure turns it off and
collects only what publishers still serve. Nothing but the URL is sent.

Archive capture time is never a Publication Time. Measured gaps between
publication and first capture on this corpus ranged from minutes to more than a
day. The capture is used only as the impossibility check the extraction library
already implements: an archive cannot capture a page before it exists.

Publication Time precedence for a Backfilled item:

  1. The date a feed stated, where the item was discovered through one.
  2. The article document, through the extraction library.
  3. The date encoded in the URL path, under the outlet's format. Day-granular,
     recorded as such, and refused unless the outlet has declared what zone its
     naive values mean.
  4. Otherwise None. Unknown stays unknown.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from functools import partial
from html import unescape
from typing import Any, Optional, Protocol, TypeVar
from urllib.parse import urlencode, urlparse

import httpx
import structlog
import trafilatura
from bs4 import BeautifulSoup

from .clean import is_paywall_page
from .fetch import check_robots_allowed
from .publication_time import (
    SIGNAL_URL_PATH_DATE,
    extract_publication_time,
    resolve_path_date,
    source_config_for,
)
from .rate_limiter import DomainRateLimiter
from .rss import parse_feed_items
from .settings import settings
from .url_safety import validate_external_url_resolved

log = structlog.get_logger(__name__)

_T = TypeVar("_T")

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Which mechanism found an item. Recorded on the item, because the mechanisms
# do not carry the same date quality: a sitemap gives a day, a feed gives an
# instant the outlet asserted.
DISCOVERY_ARCHIVE_SITEMAP = "archive_sitemap"
DISCOVERY_PAGINATED_FEED = "paginated_feed"
DISCOVERY_TOPIC_FEED = "topic_feed"

# Where the body came from. An archive body is the article as published, which
# is a stronger evidence claim than a body fetched today.
BODY_PUBLISHER = "publisher"
BODY_ARCHIVE = "archive"

# Every response here is chosen by an outlet or an archive, so its size is
# theirs to choose and ours to bound. Each bound reports itself, so a truncated
# read does not read downstream as an outlet with little history.
#
# A monthly sitemap of a national daily runs to a few megabytes at most.
_MAX_SITEMAP_BYTES = 32 * 1024 * 1024
_MAX_FEED_BYTES = 16 * 1024 * 1024
# The same figure the extraction library is given below, rather than a larger
# one: a document read past the limit extraction will parse is a document whose
# body is read and whose date silently is not.
_MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
# The CDX answer is a single row once filtered and limited.
_MAX_CDX_BYTES = 256 * 1024
# Passed to the extraction library, which asks its caller for this because the
# fetcher is what knows how much it fetched.
_MAX_ARTICLE_DOCUMENT_CHARS = 4 * 1024 * 1024
# Locations in one sitemap. Past this the document is not a monthly archive.
_MAX_SITEMAP_LOCATIONS = 50_000
# One URL. Past this it is a payload wearing a URL's shape, and it would travel
# into DNS resolution, the log pipeline and the corpus.
_MAX_URL_CHARS = 2048
# Redirect hops followed. Each is revalidated, so the cost of a hop is a DNS
# round trip and the chain has to end.
_MAX_REDIRECTS = 5

# The character class matters. A lazy ``.*?`` under DOTALL rescans to the end of
# the document at every unclosed ``<loc>``, which is quadratic: 160 KB of them
# measured at 35 seconds, and the byte bound above permits two hundred times
# that. Excluding ``<`` from the match makes it linear, and the length bound
# stops one location from being the whole document.
_LOC_RE = re.compile(r"<loc>([^<]{0,4096})</loc>", re.I)

# The archive addressing modifier that returns the markup as served, without
# the archive's own banner or link rewriting. Extraction reads the outlet's
# document, not the archive's copy of it.
_ARCHIVE_RAW_MODIFIER = "id_"


class _RateLimiter(Protocol):
    """The per-domain gap enforcer. DomainRateLimiter satisfies this."""

    async def wait(self, url: str) -> None: ...


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DateWindow:
    """The publication dates a Backfill is asked for, both ends inclusive."""

    start: date
    end: date

    def __post_init__(self) -> None:
        # A reversed window discovers nothing and reports no error, which reads
        # as an outlet with no history rather than as a caller's mistake.
        if self.start > self.end:
            raise ValueError(f"window starts after it ends: {self.start} to {self.end}")

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def months(self) -> list[tuple[int, int]]:
        """Every (year, month) the window touches, oldest first."""
        months: list[tuple[int, int]] = []
        year, month = self.start.year, self.start.month
        while (year, month) <= (self.end.year, self.end.month):
            months.append((year, month))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return months


# ---------------------------------------------------------------------------
# Per-outlet path date formats
# ---------------------------------------------------------------------------

_MONTH_NAMES = {
    name: number
    for number, names in enumerate(
        (
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ),
        start=1,
    )
    for name in names
}


@dataclass(frozen=True)
class PathDateFormat:
    """How one outlet encodes a publication date in its URL path.

    pattern captures year, month and day in that order, except where order is
    reversed by the encoding, which ``group_order`` records. month_is_name
    marks the one format whose month group is a word rather than a number.
    """

    name: str
    pattern: re.Pattern[str]
    description: str
    group_order: tuple[str, str, str] = ("year", "month", "day")
    month_is_name: bool = False

    def parse(self, path: str) -> Optional[date]:
        match = self.pattern.search(path)
        if not match:
            return None
        parts = dict(zip(self.group_order, match.groups()))
        month_raw = parts["month"]
        if self.month_is_name:
            month = _MONTH_NAMES.get(month_raw.lower())
            if month is None:
                return None
        else:
            month = int(month_raw)
        try:
            return date(int(parts["year"]), month, int(parts["day"]))
        except ValueError:
            # A path that reads as a date and is not one is no date at all.
            return None


# Every encoding seen across the surveyed outlets. An outlet declares one of
# these by name; it is never guessed, because guessing across formats turns a
# twentieth-of-July article into a seventh-of-something, and a whole-day error
# moves an item into the wrong bucket on every timeline that reads it.
PATH_DATE_FORMATS: dict[str, PathDateFormat] = {
    "numeric_unpadded": PathDateFormat(
        name="numeric_unpadded",
        pattern=re.compile(r"/(\d{4})/(\d{1,2})/(\d{1,2})(?:/|$|[^\d])"),
        description="/2026/7/20/slug",
    ),
    "numeric_padded": PathDateFormat(
        name="numeric_padded",
        pattern=re.compile(r"/(\d{4})/(\d{2})/(\d{2})(?:/|$|[^\d])"),
        description="/2026/07/20/slug",
    ),
    "month_name": PathDateFormat(
        name="month_name",
        pattern=re.compile(r"/(\d{4})/([A-Za-z]{3,9})/(\d{1,2})(?:/|$|[^\d])"),
        description="/2026/jul/20/slug",
        month_is_name=True,
    ),
    "suffix_ddmmyyyy": PathDateFormat(
        name="suffix_ddmmyyyy",
        pattern=re.compile(r"[-_/](\d{2})(\d{2})(\d{4})(?:\.[A-Za-z0-9]+)?$"),
        description="/news/slug-20072026",
        group_order=("day", "month", "year"),
    ),
    "suffix_yyyymmdd": PathDateFormat(
        name="suffix_yyyymmdd",
        pattern=re.compile(r"[-_/](\d{4})(\d{2})(\d{2})(?:\.[A-Za-z0-9]+)?$"),
        description="/news/slug-20260720.html",
    ),
}


def parse_path_date(url: str, format_name: str) -> Optional[date]:
    """Read the date an outlet encoded in a URL path, under its declared format.

    Returns None when the path carries no date in that format, which includes
    the case of a section or subscription page that carries no date at all.
    """
    fmt = PATH_DATE_FORMATS.get(format_name)
    if fmt is None:
        log.warning("backfill.unknown_path_date_format", url=url, format=format_name)
        return None
    return fmt.parse(urlparse(url).path)


# ---------------------------------------------------------------------------
# Per-outlet discovery configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutletBackfill:
    """How one outlet exposes its history.

    Templates are formatted with ``year`` and ``month`` for a sitemap and with
    ``page`` for a feed, so an outlet writing an unpadded month declares
    ``{month}`` and one writing a padded month declares ``{month:02d}``.

    reason records why the outlet is configured the way it is, because a
    declaration without one cannot be reviewed later.
    """

    host: str
    path_date_format: str
    archive_sitemap_template: Optional[str] = None
    paginated_feed_template: Optional[str] = None
    topic_feed_templates: tuple[str, ...] = field(default_factory=tuple)
    first_page: int = 1
    reason: str = ""


# Deny by default, in the shape the timezone registry in publication_time.py
# uses. An outlet absent from here has no historic route, which surfaces the
# gap rather than quietly discovering nothing. Entries are added as outlets
# enter the corpus, each recording the survey observation that justifies it.
OUTLET_BACKFILL: dict[str, OutletBackfill] = {}


def outlet_backfill_for(
    url: str,
    registry: Optional[dict[str, OutletBackfill]] = None,
) -> Optional[OutletBackfill]:
    """Return the Backfill configuration for a URL's outlet, or None.

    Lookup is by host, lowercased and with a leading ``www.`` removed, because
    an outlet serves the same history under both.
    """
    outlets = OUTLET_BACKFILL if registry is None else registry
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    outlet = outlets.get(host)
    if outlet is None:
        log.info(
            "backfill.outlet_not_configured",
            url=url,
            host=host,
            reason="no entry in OUTLET_BACKFILL",
        )
    return outlet


def belongs_to_outlet(url: str, outlet: OutletBackfill) -> bool:
    """Return True when a discovered URL is the outlet's own.

    A sitemap or feed lists whatever its publisher put in it, and a Backfill
    fetches every entry. Without this the worker is a general-purpose fetcher
    for anyone who can get a URL into an outlet's sitemap, and third-party
    content enters the corpus attributed to the outlet - which inflates the
    independent source count that Signals fire on.

    A subdomain is the outlet: publishers serve articles from a separate
    hostname and the same organisation stands behind both.
    """
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    configured = outlet.host.lower().removeprefix("www.")
    return host == configured or host.endswith(f".{configured}")


# ---------------------------------------------------------------------------
# What discovery and body fetch return
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveredUrl:
    """An article URL a discovery mechanism found, with whatever date it came with.

    path_date is day-granular by construction: a path carries no time and no
    zone. feed_published_at is an instant the outlet asserted, which is a
    stronger claim, and is carried so the body fetch does not re-derive it.
    """

    url: str
    discovery: str
    title: str = ""
    path_date: Optional[date] = None
    feed_published_at: Optional[datetime] = None
    feed_published_at_signal: Optional[str] = None

    def known_date(self) -> Optional[date]:
        if self.feed_published_at is not None:
            return self.feed_published_at.date()
        return self.path_date


@dataclass(frozen=True)
class BackfillItem:
    """One historic article, with its body and the provenance of both."""

    url: str
    title: str
    raw_text: str
    discovery: str
    body_source: str
    published_at: Optional[datetime] = None
    # Which evidence produced published_at. None exactly when published_at is.
    published_at_signal: Optional[str] = None


@dataclass(frozen=True)
class FeedDepth:
    """How far back a feed actually reaches, evergreen items excluded."""

    newest: datetime
    oldest: datetime
    span: timedelta
    evergreen_excluded: int


# ---------------------------------------------------------------------------
# Guarded fetching
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Document:
    """A fetched response: the status the server gave, and the markup if any.

    status is None when no response was obtained at all - refused before the
    request, or a transport failure. That is distinct from a status in the 400s,
    which is the publisher saying the article is not there and is the one case
    the archive answers.
    """

    status: Optional[int]
    html: Optional[str]


async def _in_executor(func: Callable[..., _T], *args: Any) -> _T:
    """Run a blocking parser off the event loop.

    feedparser, trafilatura and BeautifulSoup are all C-backed and all read
    megabyte-scale adversarial input. Called inline they stall every other job
    on this worker for as long as the slowest outlet takes to parse.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)


async def _guard(url: str, limiter: _RateLimiter) -> bool:
    """Validate and throttle before a request leaves, in the scraper's order.

    The URL is chosen by an outlet's sitemap or feed rather than by the
    operator, so it is validated before anything is sent, including the
    robots.txt request, which goes to a host the outlet named. The per-domain
    gap is taken before that request for the same reason.
    """
    if len(url) > _MAX_URL_CHARS:
        log.warning("backfill.fetch_refused", url=url[:128], reason="url past the length bound")
        return False
    if not await validate_external_url_resolved(url):
        log.warning("backfill.fetch_refused", url=url, reason="not an external address")
        return False
    await limiter.wait(url)
    if not await check_robots_allowed(url):
        log.info("backfill.fetch_disallowed", url=url, reason="robots.txt")
        return False
    return True


async def _read_bounded(resp: httpx.Response, url: str, limit: int) -> Optional[bytes]:
    """Read a streamed response up to limit, measured after decompression.

    A small compressed response that expands without limit is refused rather
    than buffered, which ``resp.content`` would have already done by the time
    anything could object.
    """
    chunks: list[bytes] = []
    total = 0
    async for chunk in resp.aiter_bytes():
        total += len(chunk)
        if total > limit:
            log.warning("backfill.response_too_large", url=url, limit=limit)
            return None
        chunks.append(chunk)
    return b"".join(chunks)


@dataclass(frozen=True)
class _Response:
    """One fetched response, after redirects have been followed and revalidated."""

    status: Optional[int]
    body: Optional[bytes]
    encoding: Optional[str] = None


async def _request(url: str, limiter: _RateLimiter, *, limit: int) -> _Response:
    """Fetch one URL, revalidating every redirect hop against the SSRF guard.

    Redirects are followed here rather than by the client, because a client
    following them decides the final host on its own. Every URL reaching this
    module is chosen by an outlet's sitemap or feed, so a 302 to an address
    inside the deployment is the shape of the attack, and the address the guard
    approved is then not the address fetched.

    Each hop goes through the same guard as the first: length bound, resolved
    SSRF check, per-domain gap, robots.txt. The chain is bounded, so a redirect
    loop ends rather than running to the job timeout.
    """
    current = url
    for hop in range(_MAX_REDIRECTS + 1):
        if not await _guard(current, limiter):
            return _Response(status=None, body=None)
        try:
            async with httpx.AsyncClient(
                timeout=settings.scraper_request_timeout_s,
                follow_redirects=False,
                headers={"User-Agent": _BROWSER_UA},
            ) as client:
                async with client.stream("GET", current) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            log.warning("backfill.redirect_without_location", url=current)
                            return _Response(status=resp.status_code, body=None)
                        current = str(httpx.URL(current).join(location))
                        continue
                    body = await _read_bounded(resp, current, limit)
                    return _Response(status=resp.status_code, body=body, encoding=resp.encoding)
        except Exception as exc:
            log.warning("backfill.fetch_failed", url=current, error=str(exc))
            return _Response(status=None, body=None)

    log.warning("backfill.redirect_chain_too_long", url=url, limit=_MAX_REDIRECTS, last=current)
    return _Response(status=None, body=None)


async def _fetch_bytes(url: str, limiter: _RateLimiter, *, limit: int) -> Optional[bytes]:
    """Fetch a sitemap, feed page or CDX answer. None on any failure."""
    response = await _request(url, limiter, limit=limit)
    if response.body is None:
        return None
    if response.status is not None and response.status >= 400:
        log.warning("backfill.fetch_failed", url=url, status=response.status)
        return None
    return response.body


async def _fetch_document(url: str, limiter: _RateLimiter) -> _Document:
    """Fetch an article document, keeping the status a failure came with.

    A body is never raised for: a client error is data the caller acts on, and
    a transport failure is a degraded item rather than a failed Backfill.
    """
    response = await _request(url, limiter, limit=_MAX_DOCUMENT_BYTES)
    if response.body is None or (response.status is not None and response.status >= 400):
        return _Document(status=response.status, html=None)
    return _Document(
        status=response.status,
        html=response.body.decode(response.encoding or "utf-8", errors="replace"),
    )


# ---------------------------------------------------------------------------
# Discovery: monthly archive sitemaps
# ---------------------------------------------------------------------------


def _sitemap_locations(xml: bytes, url: str) -> list[str]:
    """Return the locations a sitemap lists, bounded.

    Read with a regex rather than an XML parser: a sitemap is a flat list of
    locations from an adversarial host, and an entity-expanding parser on one
    is a cost we have no reason to take.
    """
    text = xml.decode("utf-8", errors="replace")
    # Unescaped, because the sitemap grammar requires an ampersand in a location
    # to be written as an entity. Read literally, every article URL carrying a
    # query string is reconstructed as a different URL and quietly discovers
    # nothing.
    found = [
        unescape(match.strip())
        for match in _LOC_RE.findall(text)
        if 0 < len(match.strip()) <= _MAX_URL_CHARS
    ]
    if len(found) > _MAX_SITEMAP_LOCATIONS:
        log.warning(
            "backfill.sitemap_too_many_locations",
            url=url,
            count=len(found),
            limit=_MAX_SITEMAP_LOCATIONS,
        )
        found = found[:_MAX_SITEMAP_LOCATIONS]
    return found


async def discover_archive_sitemap(
    outlet: OutletBackfill,
    window: DateWindow,
    *,
    limiter: Optional[_RateLimiter] = None,
    limit: Optional[int] = None,
) -> list[DiscoveredUrl]:
    """Discover article URLs from the outlet's monthly archive sitemaps.

    The date is in the path, so a month is filtered to the window without
    fetching a single article. This is the cheapest of the three mechanisms and
    the only one that is exact at the day.
    """
    if not outlet.archive_sitemap_template:
        log.info(
            "backfill.discovery_unavailable",
            host=outlet.host,
            mechanism=DISCOVERY_ARCHIVE_SITEMAP,
            reason="outlet declares no archive sitemap template",
        )
        return []

    effective = limiter if limiter is not None else DomainRateLimiter()
    budget = settings.archive_backfill_max_urls_per_outlet if limit is None else limit
    found: list[DiscoveredUrl] = []
    seen: set[str] = set()

    for year, month in window.months():
        if len(found) >= budget:
            log.warning(
                "backfill.url_budget_reached",
                host=outlet.host,
                mechanism=DISCOVERY_ARCHIVE_SITEMAP,
                limit=budget,
                reason="months after this one were not fetched",
            )
            break
        sitemap_url = outlet.archive_sitemap_template.format(year=year, month=month)
        xml = await _fetch_bytes(sitemap_url, effective, limit=_MAX_SITEMAP_BYTES)
        if xml is None:
            continue
        undated = 0
        offsite = 0
        for location in _sitemap_locations(xml, sitemap_url):
            if not belongs_to_outlet(location, outlet):
                offsite += 1
                continue
            day = parse_path_date(location, outlet.path_date_format)
            if day is None:
                undated += 1
                continue
            if not window.contains(day) or location in seen:
                continue
            seen.add(location)
            found.append(
                DiscoveredUrl(
                    url=location,
                    discovery=DISCOVERY_ARCHIVE_SITEMAP,
                    path_date=day,
                )
            )
        log.info(
            "backfill.sitemap_month_read",
            url=sitemap_url,
            year=year,
            month=month,
            in_window=len(found),
            without_path_date=undated,
            offsite=offsite,
        )

    return found


# ---------------------------------------------------------------------------
# Discovery: paginated feeds and topic feeds
# ---------------------------------------------------------------------------


async def _walk_paginated_feed(
    template: str,
    outlet: OutletBackfill,
    window: DateWindow,
    discovery: str,
    limiter: _RateLimiter,
    budget: int,
) -> list[DiscoveredUrl]:
    """Walk a feed backwards by its page parameter until it stops giving history.

    Three stop conditions, only one of which is an error:

      1. The page could not be fetched or parsed.
      2. The page brought no URL that had not already been seen. This is what a
         feed does once its real depth is exhausted: at least one surveyed topic
         feed serves page one again, with a 200 and real items, and nothing
         about that response says stop. Repeated content is the only signal.
      3. Every dated item on the page predates the window, so the walk has
         reached the date it was asked for.

    Content repetition is judged on the set of URLs rather than on the bytes,
    because an outlet varies a build timestamp or an ad slot between two renders
    of the same page. Partial overlap is not a wrap and does not stop the walk:
    it is what a page boundary shifting under a crawl looks like when the outlet
    publishes something new midway through.

    The page cap is the backstop, not the mechanism.
    """
    found: list[DiscoveredUrl] = []
    seen_urls: set[str] = set()

    for offset in range(settings.archive_backfill_max_feed_pages):
        if len(found) >= budget:
            log.warning(
                "backfill.url_budget_reached",
                host=outlet.host,
                mechanism=discovery,
                limit=budget,
                reason="pages after this one were not fetched",
            )
            break
        page = outlet.first_page + offset
        page_url = template.format(page=page)
        xml = await _fetch_bytes(page_url, limiter, limit=_MAX_FEED_BYTES)
        if xml is None:
            break

        try:
            parsed = await _in_executor(
                partial(
                    parse_feed_items,
                    xml,
                    page_url,
                    limit=settings.archive_backfill_max_items_per_page,
                )
            )
            items = [
                item
                for item in parsed
                if len(item.url) <= _MAX_URL_CHARS and belongs_to_outlet(item.url, outlet)
            ]
        except Exception as exc:
            log.warning("backfill.feed_parse_failed", url=page_url, error=str(exc))
            break
        if not items:
            log.info("backfill.pagination_exhausted", url=page_url, reason="page carried no items")
            break

        new_items = [item for item in items if item.url not in seen_urls]
        if not new_items:
            log.info(
                "backfill.pagination_wrapped",
                url=page_url,
                page=page,
                reason="page brought no url that had not already been read",
            )
            break

        dated = [item.published_at for item in new_items if item.published_at is not None]
        for item in new_items:
            seen_urls.add(item.url)
            day = item.published_at.date() if item.published_at else None
            if day is not None and not window.contains(day):
                continue
            found.append(
                DiscoveredUrl(
                    url=item.url,
                    discovery=discovery,
                    title=item.title,
                    path_date=parse_path_date(item.url, outlet.path_date_format),
                    feed_published_at=item.published_at,
                    feed_published_at_signal=item.published_at_signal,
                )
            )

        if dated and all(published_at.date() < window.start for published_at in dated):
            log.info(
                "backfill.pagination_reached_window",
                url=page_url,
                page=page,
                window_start=window.start.isoformat(),
            )
            break
    else:
        log.warning(
            "backfill.pagination_cap_reached",
            template=template,
            limit=settings.archive_backfill_max_feed_pages,
            reason="walk stopped on the page cap rather than on the window",
        )

    return found


async def discover_paginated_feed(
    outlet: OutletBackfill,
    window: DateWindow,
    *,
    limiter: Optional[_RateLimiter] = None,
    limit: Optional[int] = None,
) -> list[DiscoveredUrl]:
    """Discover article URLs by walking the outlet's main feed backwards."""
    if not outlet.paginated_feed_template:
        log.info(
            "backfill.discovery_unavailable",
            host=outlet.host,
            mechanism=DISCOVERY_PAGINATED_FEED,
            reason="outlet declares no paginated feed template",
        )
        return []
    effective = limiter if limiter is not None else DomainRateLimiter()
    return await _walk_paginated_feed(
        outlet.paginated_feed_template,
        outlet,
        window,
        DISCOVERY_PAGINATED_FEED,
        effective,
        settings.archive_backfill_max_urls_per_outlet if limit is None else limit,
    )


async def discover_topic_feeds(
    outlet: OutletBackfill,
    window: DateWindow,
    *,
    limiter: Optional[_RateLimiter] = None,
    limit: Optional[int] = None,
) -> list[DiscoveredUrl]:
    """Discover article URLs by walking the outlet's topic or tag feeds.

    A narrower subject than the main feed, and on several outlets the only
    route that reaches a date months back.
    """
    if not outlet.topic_feed_templates:
        log.info(
            "backfill.discovery_unavailable",
            host=outlet.host,
            mechanism=DISCOVERY_TOPIC_FEED,
            reason="outlet declares no topic feed templates",
        )
        return []

    effective = limiter if limiter is not None else DomainRateLimiter()
    budget = settings.archive_backfill_max_urls_per_outlet if limit is None else limit
    found: list[DiscoveredUrl] = []
    for template in outlet.topic_feed_templates:
        found.extend(
            await _walk_paginated_feed(
                template,
                outlet,
                window,
                DISCOVERY_TOPIC_FEED,
                effective,
                budget - len(found),
            )
        )
    return found


async def discover_urls(
    outlet: OutletBackfill,
    window: DateWindow,
    *,
    limiter: Optional[_RateLimiter] = None,
) -> list[DiscoveredUrl]:
    """Run every mechanism the outlet declares, and return one deduplicated list.

    The sitemap runs first, so where an article is reachable both ways the entry
    kept is the one whose date needed no fetch.
    """
    effective = limiter if limiter is not None else DomainRateLimiter()
    budget = settings.archive_backfill_max_urls_per_outlet
    deduplicated: dict[str, DiscoveredUrl] = {}

    for discover in (discover_archive_sitemap, discover_paginated_feed, discover_topic_feeds):
        remaining = budget - len(deduplicated)
        if remaining <= 0:
            break
        for item in await discover(outlet, window, limiter=effective, limit=remaining):
            deduplicated.setdefault(item.url, item)

    return list(deduplicated.values())[:budget]


# ---------------------------------------------------------------------------
# Archive rehydration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Rehydration:
    """An archived copy of a document, and when the archive first captured it."""

    html: Optional[str]
    first_capture: Optional[datetime]


def _first_capture_timestamp(payload: bytes, url: str) -> Optional[str]:
    """Read the first capture timestamp from a CDX answer, or None."""
    try:
        rows = json.loads(payload.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, ValueError):
        log.warning("backfill.cdx_unparseable", url=url)
        return None
    # Row zero is the field header. An article the archive has never captured
    # returns the header alone, or nothing at all.
    if not isinstance(rows, list) or len(rows) < 2:
        log.info("backfill.archive_no_capture", url=url)
        return None
    first = rows[1]
    if not isinstance(first, list) or not first or not isinstance(first[0], str):
        log.warning("backfill.cdx_unexpected_shape", url=url)
        return None
    return first[0]


def _capture_instant(timestamp: str, url: str) -> Optional[datetime]:
    """Parse a CDX timestamp, which is UTC and has no separators."""
    try:
        return datetime.strptime(timestamp, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        log.warning("backfill.cdx_unparseable_timestamp", url=url, timestamp=timestamp[:32])
        return None


async def rehydrate_from_archive(url: str, limiter: _RateLimiter) -> _Rehydration:
    """Fetch the archived copy of a document, and when it was first captured.

    The capture time is returned for the impossibility check only. It is never
    a Publication Time: measured gaps between publication and first capture on
    this corpus ran from minutes to more than a day.
    """
    if not settings.archive_backfill_enabled:
        log.info(
            "backfill.archive_disabled",
            url=url,
            reason="BACKFILL_ARCHIVE_ENABLED is false",
        )
        return _Rehydration(html=None, first_capture=None)

    query = urlencode(
        {
            "url": url,
            "output": "json",
            "fl": "timestamp,original",
            "filter": "statuscode:200",
            "limit": 1,
        }
    )
    payload = await _fetch_bytes(
        f"{settings.archive_backfill_cdx_url}?{query}", limiter, limit=_MAX_CDX_BYTES
    )
    if payload is None:
        return _Rehydration(html=None, first_capture=None)

    timestamp = _first_capture_timestamp(payload, url)
    if timestamp is None:
        return _Rehydration(html=None, first_capture=None)

    # Parsed before it is interpolated, not after. The value is a third party's
    # string, and a string that is not a capture timestamp has no business being
    # built into a URL we then fetch.
    first_capture = _capture_instant(timestamp, url)
    if first_capture is None:
        return _Rehydration(html=None, first_capture=None)

    snapshot_url = f"{settings.archive_backfill_base_url}/{timestamp}{_ARCHIVE_RAW_MODIFIER}/{url}"
    document = await _fetch_document(snapshot_url, limiter)
    if document.html is None:
        log.warning("backfill.archive_fetch_failed", url=url, status=document.status)
    return _Rehydration(html=document.html, first_capture=first_capture)


# ---------------------------------------------------------------------------
# Body fetch
# ---------------------------------------------------------------------------


async def _body_text(html: Optional[str], url: str) -> Optional[str]:
    """Extract the readable body of a document, or None when it is not usable.

    A paywall interstitial clears the length threshold and is not the article,
    so it is refused here rather than stored as one.
    """
    if not html:
        return None

    def extractor(document: str) -> Optional[str]:
        return trafilatura.extract(document, url=url, include_comments=False, include_tables=True)

    try:
        text = await _in_executor(extractor, html)
    except Exception as exc:
        log.warning("backfill.extract_failed", url=url, error=str(exc))
        return None
    text = (text or "").strip()
    if len(text) < settings.archive_backfill_body_min_chars:
        return None
    if is_paywall_page(text):
        log.warning("backfill.paywall_detected", url=url)
        return None
    return text


def _title_of(html: str) -> str:
    title = BeautifulSoup(html, "lxml").title
    return title.get_text(strip=True) if title and title.get_text(strip=True) else ""


async def _document_title(html: Optional[str]) -> str:
    """Read the document's own title, for an item discovered without one."""
    if not html:
        return ""
    return await _in_executor(_title_of, html)


async def _publication_time(
    discovered: DiscoveredUrl,
    html: Optional[str],
    first_capture: Optional[datetime],
) -> tuple[Optional[datetime], Optional[str]]:
    """Resolve the Publication Time for one item, in the documented order.

    A feed's date is an assertion by the outlet and is taken as given. The
    document comes next, through the single extraction path. The path date is
    last because it is day-granular, and it is recorded under its own signal so
    an analyst reading a timeline knows the difference.
    """
    if discovered.feed_published_at is not None:
        return discovered.feed_published_at, discovered.feed_published_at_signal

    source = source_config_for(discovered.url)
    if html:
        extracted = await _in_executor(
            partial(
                extract_publication_time,
                html,
                source,
                first_archive_capture=first_capture,
                max_document_chars=_MAX_ARTICLE_DOCUMENT_CHARS,
            )
        )
        if extracted is not None:
            return extracted.instant, extracted.signal

    if discovered.path_date is not None:
        instant = resolve_path_date(discovered.path_date, source)
        if instant is not None:
            return instant, SIGNAL_URL_PATH_DATE

    log.info(
        "backfill.publication_time_unknown",
        url=discovered.url,
        reason="no signal in feed, document or path",
    )
    return None, None


async def fetch_backfill_item(
    discovered: DiscoveredUrl,
    outlet: OutletBackfill,
    *,
    limiter: Optional[_RateLimiter] = None,
) -> Optional[BackfillItem]:
    """Fetch one discovered article, from the publisher or from the archive.

    The publisher is asked first. A client error means the article is not there
    any more, and the archive is asked instead - as it is for a body that comes
    back paywalled or too short to be the article, where what the publisher
    serves today is not what it published. A server error is the publisher
    failing rather than the article being gone, and is left for a retry.

    Returns None when no usable body was obtained, because a Backfilled item
    with no body is not evidence of anything.
    """
    if limiter is None:
        log.info(
            "backfill.limiter_not_shared",
            url=discovered.url,
            reason="caller passed no limiter, so this fetch has its own per-domain gap",
        )
    effective = limiter if limiter is not None else DomainRateLimiter()

    document = await _fetch_document(discovered.url, effective)
    html = document.html
    text = await _body_text(html, discovered.url)
    body_source = BODY_PUBLISHER
    first_capture: Optional[datetime] = None

    publisher_refused = document.status is not None and 400 <= document.status < 500
    if text is None and (publisher_refused or html is not None):
        rehydration = await rehydrate_from_archive(discovered.url, effective)
        first_capture = rehydration.first_capture
        archived_text = await _body_text(rehydration.html, discovered.url)
        if archived_text is not None:
            html, text, body_source = rehydration.html, archived_text, BODY_ARCHIVE

    if text is None:
        log.info(
            "backfill.item_dropped",
            url=discovered.url,
            status=document.status,
            reason="no usable body from the publisher or the archive",
        )
        return None

    published_at, signal = await _publication_time(discovered, html, first_capture)

    return BackfillItem(
        url=discovered.url,
        title=discovered.title or await _document_title(html),
        raw_text=text,
        discovery=discovered.discovery,
        body_source=body_source,
        published_at=published_at,
        published_at_signal=signal,
    )


async def backfill_outlet(
    outlet: OutletBackfill,
    window: DateWindow,
    *,
    limiter: Optional[_RateLimiter] = None,
) -> list[BackfillItem]:
    """Discover and fetch one outlet's history across the window.

    An item whose Publication Time turns out to be outside the window is
    dropped here rather than at discovery, because until the body is fetched
    the only date some mechanisms have is the day the path encodes.
    """
    effective = limiter if limiter is not None else DomainRateLimiter()
    discovered = await discover_urls(outlet, window, limiter=effective)

    items: list[BackfillItem] = []
    outside = 0
    for candidate in discovered:
        item = await fetch_backfill_item(candidate, outlet, limiter=effective)
        if item is None:
            continue
        if item.published_at is not None and not window.contains(item.published_at.date()):
            outside += 1
            continue
        items.append(item)

    log.info(
        "backfill.outlet_done",
        host=outlet.host,
        discovered=len(discovered),
        collected=len(items),
        outside_window=outside,
        undated=sum(1 for item in items if item.published_at is None),
    )
    return items


# ---------------------------------------------------------------------------
# Feed depth
# ---------------------------------------------------------------------------


def measure_feed_depth(published_at: Sequence[Optional[datetime]]) -> Optional[FeedDepth]:
    """Measure how far back a feed reaches, excluding evergreen items.

    A naive measure reports years of history that does not exist, because feeds
    carry newsletter and app promotion items dated to whenever they were
    written. Those items sit behind a gap no real publication run contains, so
    the walk stops at the first gap wider than the configured one and counts
    what is left as evergreen.

    Returns None for a feed that dates nothing, because unknown depth is not a
    depth of zero, and the difference decides whether the outlet needs a
    historic route at all.
    """
    dated = sorted((value for value in published_at if value is not None), reverse=True)
    if not dated:
        log.info("backfill.feed_depth_unknown", reason="no item carried a date")
        return None

    max_gap = timedelta(days=settings.archive_backfill_feed_depth_max_gap_days)
    oldest = dated[0]
    excluded = 0
    for index, current in enumerate(dated[1:], start=1):
        if dated[index - 1] - current > max_gap:
            # Everything from here down sits behind a gap no publication run
            # contains, so it is promotional rather than historic.
            excluded = len(dated) - index
            break
        oldest = current

    return FeedDepth(
        newest=dated[0],
        oldest=oldest,
        span=dated[0] - oldest,
        evergreen_excluded=excluded,
    )
