"""Archive Backfill discovery and body fetch - issue #44.

Tested at the HTTP boundary: every sitemap, feed page, publisher document, CDX
query and archive rehydration is served by an httpx.MockTransport, so the whole
suite runs on CPU with no network.

The failures these pin, each seen while surveying the outlets the corpus is
built from:

  1. No feed reaches far enough back. Discovery has to come from a monthly
     archive sitemap, a paginated feed, or a topic feed, and the date has to be
     readable without fetching every article.
  2. A topic feed serves page one again once its real depth runs out, with a
     200 status. A walk that stops only on an error never terminates.
  3. Outlets encode the path date four different ways, so one pattern cannot
     serve and the format is per-outlet configuration.
  4. A publisher returns a client error for an article that exists in the
     archive. The body comes from the archive, and the capture time never
     becomes the Publication Time.
  5. A feed measured naively looks years deep because it carries evergreen
     newsletter and app promotion items with old dates.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

pytestmark = pytest.mark.unit

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "archive_backfill"

_REAL_ASYNC_CLIENT = httpx.AsyncClient

_WINDOW_START = date(2026, 7, 10)
_WINDOW_END = date(2026, 7, 31)


def _fixture(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


def _window():
    from anveshak.scraper.archive_backfill import DateWindow

    return DateWindow(start=_WINDOW_START, end=_WINDOW_END)


def _routed_client(routes: dict[str, httpx.Response], record: list[str] | None = None):
    """Build a client factory serving responses by URL, over MockTransport.

    A real client rather than a stand-in, so the streamed, size-bounded reads
    the module performs are exercised rather than mocked past. An unrouted URL
    is a 404, because that is what an outlet gives for a page it does not have.
    """

    def _factory(*args, **kwargs):
        def _handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if record is not None:
                record.append(url)
            for pattern, response in routes.items():
                if pattern in url:
                    return httpx.Response(
                        status_code=response.status_code,
                        content=response.content,
                        headers=response.headers,
                    )
            return httpx.Response(status_code=404, content=b"not found")

        # The client's own keyword arguments are passed through, so a test sees
        # the redirect policy the module actually asked for rather than the
        # transport's default.
        return _REAL_ASYNC_CLIENT(*args, transport=httpx.MockTransport(_handler), **kwargs)

    return _factory


async def _approve_as_written(url: str):
    """Approve a URL without resolving it, and pin no address.

    The guarded fetch path connects to the address its guard returned, so a test
    that wants the request to arrive at the host in the URL must hand back a
    target with no address rather than a fixed one.
    """
    from anveshak.net.url_safety import ResolvedTarget

    return ResolvedTarget(url=url, hostname=httpx.URL(url).host, address=None)


def _allow_fetch():
    """Patch the SSRF and robots gates open, so a test asserts on the walk."""
    return (
        patch(
            "anveshak.scraper.archive_backfill.resolve_external_target",
            new=AsyncMock(side_effect=_approve_as_written),
        ),
        patch(
            "anveshak.scraper.archive_backfill.check_robots_allowed",
            new=AsyncMock(return_value=True),
        ),
    )


def _kolkata(host: str):
    """Declare one host's naive timestamps as IST, as a real outlet entry would."""
    from anveshak.scraper.publication_time import (
        NAIVE_TIMESTAMP_ZONES,
        SourceTimezonePolicy,
    )

    return patch.dict(
        NAIVE_TIMESTAMP_ZONES,
        {host: SourceTimezonePolicy(zone="Asia/Kolkata", reason="fixture outlet")},
    )


# ---------------------------------------------------------------------------
# Per-outlet path date formats
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("format_name", "url", "expected"),
    [
        ("numeric_unpadded", "https://o.example.in/2026/7/20/slug", date(2026, 7, 20)),
        ("numeric_padded", "https://o.example.in/2026/07/20/slug", date(2026, 7, 20)),
        ("month_name", "https://o.example.in/2026/jul/20/slug", date(2026, 7, 20)),
        ("month_name", "https://o.example.in/2026/july/20/slug", date(2026, 7, 20)),
        ("suffix_ddmmyyyy", "https://o.example.in/news/slug-20072026", date(2026, 7, 20)),
        ("suffix_yyyymmdd", "https://o.example.in/news/slug-20260720.html", date(2026, 7, 20)),
    ],
)
def test_path_date_formats_are_per_outlet(format_name: str, url: str, expected: date):
    """Each surveyed encoding parses under the format its outlet declares."""
    from anveshak.scraper.archive_backfill import parse_path_date

    assert parse_path_date(url, format_name) == expected


def test_path_date_format_does_not_match_another_outlets_encoding():
    """A format reads its own encoding only - a wrong declaration returns None.

    Guessing across formats is what turns a twentieth-of-July article into a
    seventh-of-something, which is a whole-day error on a timeline.
    """
    from anveshak.scraper.archive_backfill import parse_path_date

    assert parse_path_date("https://o.example.in/news/slug-20072026", "numeric_padded") is None
    assert parse_path_date("https://o.example.in/2026/07/20/slug", "suffix_ddmmyyyy") is None


def test_path_date_rejects_an_impossible_day():
    """A path that reads as a date and is not one is no date at all."""
    from anveshak.scraper.archive_backfill import parse_path_date

    assert parse_path_date("https://o.example.in/2026/02/31/slug", "numeric_padded") is None


def test_unknown_outlet_has_no_backfill_configuration():
    """The registry denies by default, as the timezone registry does.

    An outlet absent from it is a configuration gap that gets reported, not an
    outlet that silently discovers nothing.
    """
    from anveshak.scraper.archive_backfill import outlet_backfill_for

    assert outlet_backfill_for("https://never-surveyed.example.in/article") is None


# ---------------------------------------------------------------------------
# Monthly archive sitemap discovery
# ---------------------------------------------------------------------------


def _sitemap_outlet():
    from anveshak.scraper.archive_backfill import OutletBackfill

    return OutletBackfill(
        host="sitemap.example.in",
        path_date_format="numeric_unpadded",
        archive_sitemap_template="https://sitemap.example.in/archive/{year}/{month}.xml",
        reason="fixture outlet",
    )


async def test_sitemap_discovery_filters_by_path_date_without_fetching_articles():
    """The path date filters the month, so an out-of-window article is never fetched."""
    from anveshak.scraper.archive_backfill import discover_archive_sitemap

    requested: list[str] = []
    client = _routed_client(
        {
            "/archive/2026/7.xml": httpx.Response(
                200, content=_fixture("01_monthly_archive_sitemap.xml")
            )
        },
        record=requested,
    )
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        found = await discover_archive_sitemap(_sitemap_outlet(), _window())

    urls = [item.url for item in found]
    assert urls == [
        "https://sitemap.example.in/2026/7/20/police-clear-the-parliament-approach-road",
        "https://sitemap.example.in/2026/7/18/organisers-publish-the-march-route",
    ]
    assert all(item.path_date is not None for item in found)
    assert all("/archive/" in url for url in requested), "No article was fetched to read its date"


async def test_sitemap_discovery_reports_an_outlet_with_no_sitemap():
    """An outlet with no sitemap template discovers nothing here, and says so."""
    from anveshak.scraper.archive_backfill import OutletBackfill, discover_archive_sitemap

    outlet = OutletBackfill(
        host="nosite.example.in",
        path_date_format="numeric_padded",
        reason="fixture outlet",
    )
    assert await discover_archive_sitemap(outlet, _window()) == []


# ---------------------------------------------------------------------------
# Paginated feed discovery
# ---------------------------------------------------------------------------


def _paged_outlet():
    from anveshak.scraper.archive_backfill import OutletBackfill

    return OutletBackfill(
        host="paged.example.in",
        path_date_format="numeric_padded",
        paginated_feed_template="https://paged.example.in/feed?paged={page}",
        reason="fixture outlet",
    )


async def test_paginated_feed_walks_backwards_through_pages():
    """Page two is reached, and its items carry the date the feed stated."""
    from anveshak.scraper.archive_backfill import DISCOVERY_PAGINATED_FEED, discover_paginated_feed
    from anveshak.scraper.publication_time import SIGNAL_FEED_PUBLISHED

    client = _routed_client(
        {
            "paged=1": httpx.Response(200, content=_fixture("02_paginated_feed_page_1.xml")),
            "paged=2": httpx.Response(200, content=_fixture("03_paginated_feed_page_2.xml")),
            "paged=3": httpx.Response(
                200, content=_fixture("06_paginated_feed_page_before_window.xml")
            ),
        }
    )
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        found = await discover_paginated_feed(_paged_outlet(), _window())

    urls = [item.url for item in found]
    assert "https://paged.example.in/2026/07/15/teachers-unions-join-the-call" in urls
    assert all(item.discovery == DISCOVERY_PAGINATED_FEED for item in found)
    assert found[0].feed_published_at == datetime(2026, 7, 20, 13, 10, tzinfo=UTC)
    assert found[0].feed_published_at_signal == SIGNAL_FEED_PUBLISHED


async def test_paginated_feed_stops_when_a_page_repeats_its_predecessor():
    """A feed that wraps to page one is detected and the walk stops.

    The wrapped page is served with a 200 and real items, so nothing about the
    response says stop. Only the repeated content does.
    """
    from anveshak.scraper.archive_backfill import discover_paginated_feed

    requested: list[str] = []
    client = _routed_client(
        {
            "paged=1": httpx.Response(200, content=_fixture("02_paginated_feed_page_1.xml")),
            "paged=2": httpx.Response(200, content=_fixture("03_paginated_feed_page_2.xml")),
            "paged=3": httpx.Response(200, content=_fixture("04_paginated_feed_wraparound.xml")),
            "paged=4": httpx.Response(200, content=_fixture("04_paginated_feed_wraparound.xml")),
        },
        record=requested,
    )
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        found = await discover_paginated_feed(_paged_outlet(), _window())

    assert "paged=3" in " ".join(requested), "The wrap is only visible once page three is read"
    assert "paged=4" not in " ".join(requested), "The walk continued past a repeated page"
    assert len(found) == len({item.url for item in found}), "A wrapped page was ingested twice"


async def test_paginated_feed_stops_once_a_page_predates_the_window():
    """Reaching the requested date ends the walk, well before the page cap."""
    from anveshak.scraper.archive_backfill import discover_paginated_feed

    requested: list[str] = []
    client = _routed_client(
        {
            "paged=1": httpx.Response(200, content=_fixture("02_paginated_feed_page_1.xml")),
            "paged=2": httpx.Response(
                200, content=_fixture("06_paginated_feed_page_before_window.xml")
            ),
            "paged=3": httpx.Response(200, content=_fixture("03_paginated_feed_page_2.xml")),
        },
        record=requested,
    )
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        found = await discover_paginated_feed(_paged_outlet(), _window())

    assert "paged=3" not in " ".join(requested)
    assert all(item.feed_published_at.date() >= _WINDOW_START for item in found)


async def test_topic_feed_discovery_is_labelled_as_its_own_route():
    """A tag feed is a third route, and an analyst can tell which one found an item."""
    from anveshak.scraper.archive_backfill import (
        DISCOVERY_TOPIC_FEED,
        OutletBackfill,
        discover_topic_feeds,
    )

    outlet = OutletBackfill(
        host="topic.example.in",
        path_date_format="suffix_ddmmyyyy",
        topic_feed_templates=("https://topic.example.in/education/feed?paged={page}",),
        reason="fixture outlet",
    )
    client = _routed_client(
        {"paged=1": httpx.Response(200, content=_fixture("05_topic_feed_page_1.xml"))}
    )
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        found = await discover_topic_feeds(outlet, _window())

    assert [item.discovery for item in found] == [DISCOVERY_TOPIC_FEED]
    assert found[0].path_date == date(2026, 7, 20)


# ---------------------------------------------------------------------------
# Body fetch, and the archive fallback
# ---------------------------------------------------------------------------


def _discovered(url: str, **kwargs):
    from anveshak.scraper.archive_backfill import DISCOVERY_ARCHIVE_SITEMAP, DiscoveredUrl

    kwargs.setdefault("discovery", DISCOVERY_ARCHIVE_SITEMAP)
    return DiscoveredUrl(url=url, **kwargs)


_CDX_FIRST_CAPTURE = (
    b'[["timestamp","original"],'
    b'["20260721043000","https://sitemap.example.in/2026/7/20/police-clear"]]'
)


async def test_publisher_client_error_triggers_archive_rehydration():
    """A 404 at the publisher is answered from the archive, not dropped."""
    from anveshak.scraper.archive_backfill import BODY_ARCHIVE, fetch_backfill_item

    client = _routed_client(
        {
            "cdx/search/cdx": httpx.Response(200, content=_CDX_FIRST_CAPTURE),
            "web.archive.org/web/": httpx.Response(
                200, content=_fixture("07_archive_snapshot.html")
            ),
            "sitemap.example.in": httpx.Response(404, content=b"gone"),
        }
    )
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        item = await fetch_backfill_item(
            _discovered("https://sitemap.example.in/2026/7/20/police-clear"),
            _sitemap_outlet(),
        )

    assert item is not None
    assert item.body_source == BODY_ARCHIVE
    assert "Forty marchers were detained" in item.raw_text
    assert item.published_at == datetime(2026, 7, 20, 13, 10, tzinfo=UTC)


async def test_publisher_server_error_is_not_an_archive_fallback():
    """A 500 is the publisher failing, and is retried later rather than archived around."""
    from anveshak.scraper.archive_backfill import fetch_backfill_item

    requested: list[str] = []
    client = _routed_client(
        {"sitemap.example.in": httpx.Response(500, content=b"upstream error")},
        record=requested,
    )
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        item = await fetch_backfill_item(
            _discovered("https://sitemap.example.in/2026/7/20/police-clear"),
            _sitemap_outlet(),
        )

    assert item is None
    assert not any("web.archive.org" in url for url in requested)


async def test_archive_capture_time_is_never_a_publication_time():
    """A rehydrated document asserting no date is stored with a null date.

    The capture time is known here - it is how the rehydration was addressed -
    and it is still not evidence of when the outlet published.
    """
    from anveshak.scraper.archive_backfill import fetch_backfill_item

    client = _routed_client(
        {
            "cdx/search/cdx": httpx.Response(200, content=_CDX_FIRST_CAPTURE),
            "web.archive.org/web/": httpx.Response(
                200, content=_fixture("08_undated_archive_snapshot.html")
            ),
            "sitemap.example.in": httpx.Response(410, content=b"gone"),
        }
    )
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        item = await fetch_backfill_item(
            _discovered("https://sitemap.example.in/undated-article"),
            _sitemap_outlet(),
        )

    assert item is not None
    assert item.published_at is None
    assert item.published_at_signal is None


async def test_path_date_is_used_only_where_the_document_asserts_nothing():
    """A path date is day-granular, recorded as such, and subject to the zone policy."""
    from anveshak.scraper.archive_backfill import fetch_backfill_item
    from anveshak.scraper.publication_time import SIGNAL_URL_PATH_DATE

    client = _routed_client(
        {
            "cdx/search/cdx": httpx.Response(200, content=_CDX_FIRST_CAPTURE),
            "web.archive.org/web/": httpx.Response(
                200, content=_fixture("08_undated_archive_snapshot.html")
            ),
            "sitemap.example.in": httpx.Response(404, content=b"gone"),
        }
    )
    ssrf, robots = _allow_fetch()
    with (
        ssrf,
        robots,
        _kolkata("sitemap.example.in"),
        patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client),
    ):
        item = await fetch_backfill_item(
            _discovered(
                "https://sitemap.example.in/2026/7/20/organisers-publish",
                path_date=date(2026, 7, 20),
            ),
            _sitemap_outlet(),
        )

    assert item is not None
    assert item.published_at_signal == SIGNAL_URL_PATH_DATE
    # Local midnight in the zone the outlet declared, not midnight UTC.
    assert item.published_at == datetime(2026, 7, 19, 18, 30, tzinfo=UTC)


async def test_robots_disallow_stops_the_body_fetch():
    """Discovery names the URL; robots still decides whether it is fetched."""
    from anveshak.scraper.archive_backfill import fetch_backfill_item

    requested: list[str] = []
    client = _routed_client({}, record=requested)
    with (
        patch(
            "anveshak.scraper.archive_backfill.resolve_external_target",
            new=AsyncMock(side_effect=_approve_as_written),
        ),
        patch(
            "anveshak.scraper.archive_backfill.check_robots_allowed",
            new=AsyncMock(return_value=False),
        ),
        patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client),
    ):
        item = await fetch_backfill_item(
            _discovered("https://sitemap.example.in/2026/7/20/police-clear"),
            _sitemap_outlet(),
        )

    assert item is None
    assert requested == []


async def test_feed_dated_item_keeps_the_feeds_date():
    """A feed stating a date is a publication assertion, and it is not re-derived."""
    from anveshak.scraper.archive_backfill import (
        DISCOVERY_PAGINATED_FEED,
        DiscoveredUrl,
        fetch_backfill_item,
    )
    from anveshak.scraper.publication_time import SIGNAL_FEED_PUBLISHED

    stated = datetime(2026, 7, 20, 13, 10, tzinfo=UTC)
    client = _routed_client(
        {
            "sitemap.example.in": httpx.Response(
                200, content=_fixture("08_undated_archive_snapshot.html")
            )
        }
    )
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        item = await fetch_backfill_item(
            DiscoveredUrl(
                url="https://sitemap.example.in/2026/7/20/police-clear",
                discovery=DISCOVERY_PAGINATED_FEED,
                feed_published_at=stated,
                feed_published_at_signal=SIGNAL_FEED_PUBLISHED,
            ),
            _sitemap_outlet(),
        )

    assert item is not None
    assert item.published_at == stated
    assert item.published_at_signal == SIGNAL_FEED_PUBLISHED


# ---------------------------------------------------------------------------
# Feed depth
# ---------------------------------------------------------------------------


def test_feed_depth_excludes_evergreen_items():
    """A promotion item dated years back does not become the feed's depth.

    Measured naively this feed reads as four years deep. Its real history is
    ten days, and that is the number a discovery decision has to be made on.
    """
    from anveshak.scraper.archive_backfill import measure_feed_depth

    newest = datetime(2026, 7, 20, tzinfo=UTC)
    dates = [
        newest,
        newest - timedelta(days=3),
        newest - timedelta(days=6),
        newest - timedelta(days=10),
        # "Subscribe to our newsletter", carried on every page since 2022.
        newest - timedelta(days=1500),
    ]

    depth = measure_feed_depth(dates)

    assert depth is not None
    assert depth.span == timedelta(days=10)
    assert depth.evergreen_excluded == 1


def test_feed_depth_is_unknown_for_an_undated_feed():
    """No date means no depth, rather than a depth of zero."""
    from anveshak.scraper.archive_backfill import measure_feed_depth

    assert measure_feed_depth([None, None]) is None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def test_discover_urls_keeps_the_entry_whose_date_needed_no_fetch():
    """An article reachable both ways is discovered once, through the sitemap."""
    from anveshak.scraper.archive_backfill import (
        DISCOVERY_ARCHIVE_SITEMAP,
        OutletBackfill,
        discover_urls,
    )

    shared = "https://paged.example.in/2026/07/20/police-clear-the-approach-road"
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset><url><loc>{shared}</loc></url></urlset>""".encode()
    outlet = OutletBackfill(
        host="paged.example.in",
        path_date_format="numeric_padded",
        archive_sitemap_template="https://paged.example.in/archive/{year}/{month:02d}.xml",
        paginated_feed_template="https://paged.example.in/feed?paged={page}",
        reason="fixture outlet",
    )
    client = _routed_client(
        {
            "/archive/2026/07.xml": httpx.Response(200, content=sitemap),
            "paged=1": httpx.Response(200, content=_fixture("02_paginated_feed_page_1.xml")),
            "paged=2": httpx.Response(
                200, content=_fixture("06_paginated_feed_page_before_window.xml")
            ),
        }
    )
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        found = await discover_urls(outlet, _window())

    urls = [item.url for item in found]
    assert urls.count(shared) == 1
    kept = next(item for item in found if item.url == shared)
    assert kept.discovery == DISCOVERY_ARCHIVE_SITEMAP


async def test_backfill_outlet_drops_an_item_published_outside_the_window():
    """A path date can put an item in the window that its document puts outside.

    The document is the stronger signal, so the item is dropped once its body is
    fetched rather than carried into a corpus it does not belong to.
    """
    from anveshak.scraper.archive_backfill import backfill_outlet

    in_window = "https://sitemap.example.in/2026/7/20/police-clear"
    # The path says the twentieth; the document says the second, which is before
    # the window starts. One outlet republishes under a fresh path this way.
    republished = "https://sitemap.example.in/2026/7/19/republished"
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset>
      <url><loc>{in_window}</loc></url>
      <url><loc>{republished}</loc></url>
    </urlset>""".encode()
    older_document = _fixture("07_archive_snapshot.html").replace(
        b"2026-07-20T18:40:00+05:30", b"2026-07-02T18:40:00+05:30"
    )
    client = _routed_client(
        {
            "/archive/2026/7.xml": httpx.Response(200, content=sitemap),
            "/2026/7/20/police-clear": httpx.Response(
                200, content=_fixture("07_archive_snapshot.html")
            ),
            "/2026/7/19/republished": httpx.Response(200, content=older_document),
        }
    )
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        items = await backfill_outlet(_sitemap_outlet(), _window())

    assert [item.url for item in items] == [in_window]
    assert items[0].published_at == datetime(2026, 7, 20, 13, 10, tzinfo=UTC)


async def test_an_article_the_archive_never_captured_is_dropped():
    """A CDX answer carrying only its header is no capture, and no body."""
    from anveshak.scraper.archive_backfill import fetch_backfill_item

    client = _routed_client(
        {
            "cdx/search/cdx": httpx.Response(200, content=b'[["timestamp","original"]]'),
            "sitemap.example.in": httpx.Response(404, content=b"gone"),
        }
    )
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        item = await fetch_backfill_item(
            _discovered("https://sitemap.example.in/2026/7/20/police-clear"),
            _sitemap_outlet(),
        )

    assert item is None


async def test_archive_fallback_can_be_turned_off():
    """The archive route is a setting, and its absence is reported rather than silent."""
    from anveshak.scraper.archive_backfill import fetch_backfill_item

    requested: list[str] = []
    client = _routed_client(
        {"sitemap.example.in": httpx.Response(404, content=b"gone")}, record=requested
    )
    ssrf, robots = _allow_fetch()
    with (
        ssrf,
        robots,
        patch("anveshak.scraper.archive_backfill.settings.archive_backfill_enabled", new=False),
        patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client),
    ):
        item = await fetch_backfill_item(
            _discovered("https://sitemap.example.in/2026/7/20/police-clear"),
            _sitemap_outlet(),
        )

    assert item is None
    assert not any("web.archive.org" in url for url in requested)


def test_an_unknown_path_date_format_reads_as_no_date():
    """A misconfigured outlet discovers nothing, rather than dating items wrongly."""
    from anveshak.scraper.archive_backfill import parse_path_date

    assert parse_path_date("https://o.example.in/2026/07/20/slug", "not_a_format") is None


def test_feed_depth_counts_a_contiguous_run_in_full():
    """A feed with no evergreen items excludes nothing."""
    from anveshak.scraper.archive_backfill import measure_feed_depth

    newest = datetime(2026, 7, 20, tzinfo=UTC)
    depth = measure_feed_depth([newest, newest - timedelta(days=8), newest - timedelta(days=16)])

    assert depth is not None
    assert depth.evergreen_excluded == 0
    assert depth.span == timedelta(days=16)


# ---------------------------------------------------------------------------
# Hardening: the URL a sitemap or a redirect chooses
# ---------------------------------------------------------------------------


async def test_sitemap_locations_off_the_outlets_host_are_refused():
    """A sitemap lists whatever its publisher put in it, and it is not all theirs.

    Fetching an off-site location makes the worker a general fetcher for anyone
    who can reach an outlet's sitemap, and files the result under that outlet,
    which inflates the independent source count Signals fire on.
    """
    from anveshak.scraper.archive_backfill import discover_archive_sitemap

    sitemap = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset>
      <url><loc>https://sitemap.example.in/2026/7/20/ours</loc></url>
      <url><loc>https://attacker.example.net/2026/7/20/theirs</loc></url>
      <url><loc>https://news.sitemap.example.in/2026/7/20/our-subdomain</loc></url>
    </urlset>"""
    client = _routed_client({"/archive/2026/7.xml": httpx.Response(200, content=sitemap)})
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        found = await discover_archive_sitemap(_sitemap_outlet(), _window())

    assert [item.url for item in found] == [
        "https://sitemap.example.in/2026/7/20/ours",
        "https://news.sitemap.example.in/2026/7/20/our-subdomain",
    ]


async def test_sitemap_location_entities_are_unescaped():
    """The sitemap grammar escapes an ampersand, so a literal read fetches elsewhere."""
    from anveshak.scraper.archive_backfill import discover_archive_sitemap

    sitemap = (
        b'<?xml version="1.0" encoding="UTF-8"?><urlset><url><loc>'
        b"https://sitemap.example.in/2026/7/20/story?id=4&amp;page=2"
        b"</loc></url></urlset>"
    )
    client = _routed_client({"/archive/2026/7.xml": httpx.Response(200, content=sitemap)})
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        found = await discover_archive_sitemap(_sitemap_outlet(), _window())

    assert [item.url for item in found] == [
        "https://sitemap.example.in/2026/7/20/story?id=4&page=2"
    ]


async def test_a_location_longer_than_a_url_is_not_a_url():
    """One location is not allowed to be the whole document."""
    from anveshak.scraper.archive_backfill import discover_archive_sitemap

    padded = "https://sitemap.example.in/2026/7/20/" + ("a" * 4000)
    sitemap = f"<urlset><url><loc>{padded}</loc></url></urlset>".encode()
    client = _routed_client({"/archive/2026/7.xml": httpx.Response(200, content=sitemap)})
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        found = await discover_archive_sitemap(_sitemap_outlet(), _window())

    assert found == []


def test_unclosed_location_tags_do_not_make_the_read_quadratic():
    """A lazy match under DOTALL rescans to the end at every unclosed tag.

    Measured at 35 seconds for 160 KB of them, against a byte bound two hundred
    times larger, on the event loop. The bounded read is linear and returns
    nothing, because an unclosed tag is not a location.
    """
    import time

    from anveshak.scraper.archive_backfill import _sitemap_locations

    hostile = b"<loc>" * 40_000
    started = time.monotonic()
    found = _sitemap_locations(hostile, "https://sitemap.example.in/archive/2026/7.xml")
    elapsed = time.monotonic() - started

    assert found == []
    assert elapsed < 2.0, f"read took {elapsed:.1f}s, which is the quadratic shape"


async def test_a_redirect_to_an_internal_address_is_refused():
    """The guard approves the address asked for; a redirect chooses another.

    Inside a compose deployment every dangerous address has a name, so a feed
    link that redirects to one reaches an internal port with the first check
    fully satisfied.
    """
    from anveshak.scraper.archive_backfill import fetch_backfill_item

    requested: list[str] = []
    client = _routed_client(
        {
            "sitemap.example.in": httpx.Response(
                302, headers={"location": "http://ollama:11434/api/tags"}
            )
        },
        record=requested,
    )

    async def _external_only(url: str):
        if "ollama" in url:
            return None
        return await _approve_as_written(url)

    with (
        patch(
            "anveshak.scraper.archive_backfill.resolve_external_target",
            new=AsyncMock(side_effect=_external_only),
        ),
        patch(
            "anveshak.scraper.archive_backfill.check_robots_allowed",
            new=AsyncMock(return_value=True),
        ),
        patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client),
    ):
        item = await fetch_backfill_item(
            _discovered("https://sitemap.example.in/2026/7/20/police-clear"),
            _sitemap_outlet(),
        )

    assert item is None
    assert not any("ollama" in url for url in requested)


async def test_a_redirect_loop_ends():
    """A chain that never resolves stops at the hop bound, not at the job timeout."""
    from anveshak.scraper.archive_backfill import fetch_backfill_item
    from anveshak.scraper.settings import settings

    requested: list[str] = []

    def _factory(*args, **kwargs):
        def _handler(request: httpx.Request) -> httpx.Response:
            requested.append(str(request.url))
            return httpx.Response(302, headers={"location": f"/hop-{len(requested)}"})

        return _REAL_ASYNC_CLIENT(*args, transport=httpx.MockTransport(_handler), **kwargs)

    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=_factory):
        item = await fetch_backfill_item(
            _discovered("https://sitemap.example.in/2026/7/20/police-clear"),
            _sitemap_outlet(),
        )

    assert item is None
    assert len(requested) == settings.scraper_max_redirects + 1


async def test_a_cdx_timestamp_that_is_not_one_is_never_put_in_a_url():
    """The archive's answer is a third party's string, parsed before it is used."""
    from anveshak.scraper.archive_backfill import fetch_backfill_item

    requested: list[str] = []
    client = _routed_client(
        {
            "cdx/search/cdx": httpx.Response(
                200, content=b'[["timestamp","original"],["../../etc/passwd","x"]]'
            ),
            "sitemap.example.in": httpx.Response(404, content=b"gone"),
        },
        record=requested,
    )
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        item = await fetch_backfill_item(
            _discovered("https://sitemap.example.in/2026/7/20/police-clear"),
            _sitemap_outlet(),
        )

    assert item is None
    assert not any("web.archive.org" in url and "cdx" not in url for url in requested), (
        "a string that is not a capture timestamp was built into a fetched URL"
    )


def test_a_window_that_runs_backwards_is_refused():
    """A reversed window discovers nothing, and silence would read as no history."""
    from anveshak.scraper.archive_backfill import DateWindow

    with pytest.raises(ValueError, match="starts after it ends"):
        DateWindow(start=date(2026, 7, 31), end=date(2026, 7, 1))


# ---------------------------------------------------------------------------
# The backstops, which degrade rather than fail
# ---------------------------------------------------------------------------


async def test_the_page_cap_is_a_backstop_and_reports_itself():
    """A feed that never exhausts stops at the cap, and says that is why.

    Stopping at the cap means the window was not reached, so the corpus is
    short by however much history the walk did not get to. Silence here reads
    as an outlet that stops publishing on a date it does not.
    """
    from anveshak.scraper.archive_backfill import discover_paginated_feed

    requested: list[str] = []

    def _factory(*args, **kwargs):
        def _handler(request: httpx.Request) -> httpx.Response:
            # Every page is new content in the window, so nothing but the cap
            # can end this walk.
            page = len(requested) + 1
            requested.append(str(request.url))
            body = f"""<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0"><channel><item>
              <title>Page {page}</title>
              <link>https://paged.example.in/2026/07/20/story-{page}</link>
              <description>{"Body text for an item that is long enough to be one. " * 4}</description>
              <pubDate>Mon, 20 Jul 2026 18:40:00 +0530</pubDate>
            </item></channel></rss>""".encode()
            return httpx.Response(200, content=body)

        return _REAL_ASYNC_CLIENT(*args, transport=httpx.MockTransport(_handler), **kwargs)

    ssrf, robots = _allow_fetch()
    with (
        ssrf,
        robots,
        patch("anveshak.scraper.archive_backfill.settings.archive_backfill_max_feed_pages", new=3),
        patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=_factory),
    ):
        found = await discover_paginated_feed(_paged_outlet(), _window())

    assert len(requested) == 3
    assert len(found) == 3


async def test_discovery_stops_fetching_once_the_url_budget_is_spent():
    """The cap bounds the crawl, not just the list it returns.

    Applied after discovery it would bound the output while the walk had
    already made every request, which is the expensive half.
    """
    from anveshak.scraper.archive_backfill import discover_urls

    requested: list[str] = []
    sitemap = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset>
      <url><loc>https://paged.example.in/2026/07/20/one</loc></url>
      <url><loc>https://paged.example.in/2026/07/19/two</loc></url>
    </urlset>"""
    outlet_module = __import__("anveshak.scraper.archive_backfill", fromlist=["OutletBackfill"])
    outlet = outlet_module.OutletBackfill(
        host="paged.example.in",
        path_date_format="numeric_padded",
        archive_sitemap_template="https://paged.example.in/archive/{year}/{month:02d}.xml",
        paginated_feed_template="https://paged.example.in/feed?paged={page}",
        reason="fixture outlet",
    )
    client = _routed_client(
        {
            "/archive/2026/07.xml": httpx.Response(200, content=sitemap),
            "paged=": httpx.Response(200, content=_fixture("02_paginated_feed_page_1.xml")),
        },
        record=requested,
    )
    ssrf, robots = _allow_fetch()
    with (
        ssrf,
        robots,
        patch(
            "anveshak.scraper.archive_backfill.settings.archive_backfill_max_urls_per_outlet",
            new=2,
        ),
        patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client),
    ):
        found = await discover_urls(outlet, _window())

    assert len(found) == 2
    assert not any("paged=" in url for url in requested), "the feed was walked after the budget"


async def test_a_response_past_the_byte_bound_is_refused_rather_than_buffered():
    """A document larger than the bound is no document, and the bound reports itself."""
    from anveshak.scraper.archive_backfill import _MAX_DOCUMENT_BYTES, fetch_backfill_item

    oversized = b"<html><body><p>" + (b"a" * (_MAX_DOCUMENT_BYTES + 1)) + b"</p></body></html>"
    client = _routed_client({"sitemap.example.in": httpx.Response(200, content=oversized)})
    ssrf, robots = _allow_fetch()
    with ssrf, robots, patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=client):
        item = await fetch_backfill_item(
            _discovered("https://sitemap.example.in/2026/7/20/police-clear"),
            _sitemap_outlet(),
        )

    assert item is None


def test_feed_depth_handles_items_sharing_one_instant():
    """Two items published at the same second are common, and neither is evergreen."""
    from anveshak.scraper.archive_backfill import measure_feed_depth

    newest = datetime(2026, 7, 20, tzinfo=UTC)
    same = newest - timedelta(days=4)
    depth = measure_feed_depth([newest, same, same, newest - timedelta(days=9)])

    assert depth is not None
    assert depth.evergreen_excluded == 0
    assert depth.span == timedelta(days=9)
