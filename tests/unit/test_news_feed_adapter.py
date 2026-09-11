"""News source adapter for RSS and Atom collection - issue #43.

Tested at the HTTP boundary: the feed transport is mocked and the article
fetcher is mocked, so every test runs on CPU with no network.

The failures these pin, each seen on a surveyed outlet:

  1. An outlet emits a content element on every item and never fills it. The
     element's presence is not the presence of text, and its markup is not
     length. Both readings store an empty body.
  2. An Atom outlet dates entries with ``updated`` and never emits
     ``published``. Reading only ``published`` leaves the whole feed undated.
  3. An outlet emits no date at all. The date then comes from the article
     document, never from collection time.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

pytestmark = pytest.mark.unit

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "news_feeds"

_REAL_ASYNC_CLIENT = httpx.AsyncClient

# A dated article document, for the case where the feed supplies no date.
_ARTICLE_WITH_JSONLD = """
<html><head>
<script type="application/ld+json">
{"@type": "NewsArticle", "datePublished": "2026-07-19T18:30:00+05:30"}
</script>
</head><body><article><p>The organisers published the march route on Sunday
evening, naming three assembly points and a single dispersal point, and asked
participants to carry identification.</p></article></body></html>
"""

_FETCHED_BODY = (
    "Forty marchers were detained near the parliament approach road on Monday "
    "afternoon and released without charge the same evening, according to a "
    "police statement issued after midnight. The statement did not name the "
    "organisation the marchers belonged to, and gave no account of the order "
    "under which the detentions were made."
)


def _feed_bytes(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


def _fetched(text: str | None = _FETCHED_BODY, html: str | None = None):
    from anveshak.scraper.fetch import FetchedArticle

    return FetchedArticle(text=text, html=html)


@contextlib.contextmanager
def _feed_served(payload: bytes):
    """Serve feed bytes to the guarded fetch path, with resolution fixed.

    A real httpx.AsyncClient over a MockTransport, not a stand-in for one, so
    the streamed read the fetcher performs is exercised rather than mocked past.
    The resolver is fixed because the fetch path connects to the address it
    validated, and a unit test that asks DNS about an example host is a network
    test with a slow failure.
    """

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, content=payload)

    def _factory(*args, **kwargs):
        kwargs.pop("proxy", None)
        # The real class, captured before the patch that installed this factory
        # in its place, so constructing one here does not call this again.
        return _REAL_ASYNC_CLIENT(*args, transport=httpx.MockTransport(_handler), **kwargs)

    with (
        patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=_factory),
        patch(
            "anveshak.net.url_safety._resolve_host",
            new=AsyncMock(return_value=["93.184.216.34"]),
        ),
    ):
        yield


async def _collect_bytes(
    payload: bytes,
    *,
    article: object | None = None,
    robots_allowed: bool = True,
    address_external: bool = True,
):
    """Run fetch_rss_items against feed bytes. Returns (items, fetch mock).

    Address validation is stubbed rather than resolved, because a unit test
    that asks DNS about an example host is a network test with a slow failure.
    """
    from anveshak.scraper import rss as rss_module

    fetch_article = AsyncMock(return_value=article if article is not None else _fetched())
    with (
        _feed_served(payload),
        patch("anveshak.scraper.rss.fetch_article", new=fetch_article),
        patch(
            "anveshak.scraper.rss.validate_external_url_resolved",
            new=AsyncMock(return_value=address_external),
        ),
        patch(
            "anveshak.scraper.rss.check_robots_allowed",
            new=AsyncMock(return_value=robots_allowed),
        ),
    ):
        items = await rss_module.fetch_rss_items("https://feed.example.in/rss")
    return items, fetch_article


async def _collect(
    feed_fixture: str,
    *,
    article: object | None = None,
    robots_allowed: bool = True,
    address_external: bool = True,
):
    """Run fetch_rss_items against a fixture feed. Returns (items, fetch mock)."""
    return await _collect_bytes(
        _feed_bytes(feed_fixture),
        article=article,
        robots_allowed=robots_allowed,
        address_external=address_external,
    )


# ---------------------------------------------------------------------------
# Body selection
# ---------------------------------------------------------------------------


class TestFeedBody:
    async def test_full_text_feed_is_used_without_fetching_the_article(self):
        """A feed carrying genuine full text is used as-is - rule: fetch nothing we have."""
        items, fetch_article = await _collect("01_full_text_feed.xml")

        assert len(items) == 2
        assert fetch_article.await_count == 0
        assert "third such assembly in a fortnight" in items[0].raw_text

    async def test_feed_body_is_stored_as_text_not_markup(self):
        """Feed bodies are HTML fragments. Tags are not content."""
        items, _ = await _collect("01_full_text_feed.xml")

        for item in items:
            assert "<p>" not in item.raw_text
            assert "<" not in item.raw_text

    async def test_short_summary_triggers_the_article_fetch(self):
        """Summary below the threshold means the body is fetched from the publisher."""
        items, fetch_article = await _collect("02_summary_only_feed.xml")

        assert fetch_article.await_count == 2
        assert all(item.raw_text == _FETCHED_BODY for item in items)

    async def test_empty_content_element_does_not_suppress_the_summary(self):
        """An always-empty content element must not shadow a usable description."""
        items, fetch_article = await _collect("03_empty_content_element_feed.xml")

        resigned = next(i for i in items if "minister-resigns" in i.url)
        assert "resignation letter cited personal reasons" in resigned.raw_text
        assert fetch_article.await_count == 1  # only the second item needed a fetch

    async def test_empty_content_element_markup_is_not_counted_as_length(self):
        """The markup wrapper is longer than the threshold and carries no text."""
        items, fetch_article = await _collect("03_empty_content_element_feed.xml")

        faction = next(i for i in items if "breakaway-faction" in i.url)
        assert faction.raw_text == _FETCHED_BODY
        assert "article-body-wrapper" not in faction.raw_text
        assert fetch_article.await_args_list[0].args[0].endswith("breakaway-faction")

    async def test_no_item_is_produced_with_an_empty_body(self):
        """A silently empty item must never enter the corpus."""
        items, _ = await _collect("03_empty_content_element_feed.xml", article=_fetched(text=None))

        assert items, "the dated item with a usable summary is still produced"
        for item in items:
            assert item.raw_text.strip()

    async def test_failed_article_fetch_keeps_the_feed_summary(self):
        """A failed fetch never discards an entry that has some text."""
        items, _ = await _collect("02_summary_only_feed.xml", article=_fetched(text=None))

        assert len(items) == 2
        assert "Forty marchers were detained" in items[0].raw_text


# ---------------------------------------------------------------------------
# Publication Time
# ---------------------------------------------------------------------------


class TestPublicationTime:
    async def test_every_item_carries_the_feed_date(self):
        """Publication Time is set on every produced item, timezone-aware, in UTC."""
        items, _ = await _collect("01_full_text_feed.xml")

        assert items
        for item in items:
            assert item.published_at is not None
            assert item.published_at.tzinfo is not None
            assert item.published_at.utcoffset().total_seconds() == 0

    async def test_feed_date_keeps_its_declared_offset(self):
        """+05:30 in the feed is 04:00 UTC, not 09:30 UTC."""
        items, _ = await _collect("01_full_text_feed.xml")

        assert items[0].published_at == datetime(2026, 7, 20, 4, 0, tzinfo=UTC)

    async def test_atom_updated_is_read_when_published_is_absent(self):
        """An Atom outlet that only emits updated is not an undated outlet."""
        items, _ = await _collect("04_atom_updated_only_feed.xml")

        assert len(items) == 1
        assert items[0].published_at == datetime(2026, 7, 22, 2, 10, tzinfo=UTC)

    async def test_undated_feed_falls_back_to_the_article_document(self):
        """No feed date means the extraction library reads the document."""
        items, _ = await _collect(
            "05_undated_feed.xml",
            article=_fetched(text=_FETCHED_BODY, html=_ARTICLE_WITH_JSONLD),
        )

        assert len(items) == 1
        assert items[0].published_at == datetime(2026, 7, 19, 13, 0, tzinfo=UTC)

    async def test_signal_records_where_the_date_came_from(self):
        """An analyst weighing a date needs to know which signal produced it."""
        from anveshak.scraper.publication_time import (
            SIGNAL_FEED_PUBLISHED,
            SIGNAL_FEED_UPDATED,
            SIGNAL_JSONLD_DATE_PUBLISHED,
        )

        dated, _ = await _collect("01_full_text_feed.xml")
        atom, _ = await _collect("04_atom_updated_only_feed.xml")
        undated, _ = await _collect(
            "05_undated_feed.xml",
            article=_fetched(text=_FETCHED_BODY, html=_ARTICLE_WITH_JSONLD),
        )

        assert dated[0].published_at_signal == SIGNAL_FEED_PUBLISHED
        assert atom[0].published_at_signal == SIGNAL_FEED_UPDATED
        assert undated[0].published_at_signal == SIGNAL_JSONLD_DATE_PUBLISHED

    async def test_unknown_publication_time_stays_unknown(self):
        """No date in the feed and none in the document means NULL, never now()."""
        items, _ = await _collect(
            "05_undated_feed.xml",
            article=_fetched(text=_FETCHED_BODY, html="<html><body><p>No date.</p></body></html>"),
        )

        assert len(items) == 1
        assert items[0].published_at is None
        assert items[0].published_at_signal is None


# ---------------------------------------------------------------------------
# Fetch conventions
# ---------------------------------------------------------------------------


class TestFetchConventions:
    async def test_robots_disallow_skips_the_article_fetch(self):
        """robots.txt governs the article fetch exactly as it does a web crawl."""
        items, fetch_article = await _collect("02_summary_only_feed.xml", robots_allowed=False)

        assert fetch_article.await_count == 0
        assert len(items) == 2
        assert "Forty marchers were detained" in items[0].raw_text

    async def test_article_fetches_are_rate_limited_per_domain(self):
        """The publisher sees the same per-domain gap a crawl would give it."""
        from anveshak.scraper import rss as rss_module

        waited: list[str] = []

        class _Limiter:
            async def wait(self, url: str) -> None:
                waited.append(url)

        with (
            _feed_served(_feed_bytes("02_summary_only_feed.xml")),
            patch("anveshak.scraper.rss.fetch_article", new=AsyncMock(return_value=_fetched())),
            patch(
                "anveshak.scraper.rss.validate_external_url_resolved",
                new=AsyncMock(return_value=True),
            ),
            patch("anveshak.scraper.rss.check_robots_allowed", new=AsyncMock(return_value=True)),
        ):
            await rss_module.fetch_rss_items("https://feed.example.in/rss", limiter=_Limiter())

        assert waited == [
            "https://summary.example.in/2026/07/20/detained-at-march",
            "https://summary.example.in/2026/07/21/statement-sought",
        ]

    async def test_paywalled_article_falls_back_to_the_feed_summary(self):
        """A paywall interstitial is not an article body."""
        paywall = (
            "Subscribe to continue reading. This article is for subscribers only. "
            "Already a subscriber? Sign in to read the full story. Get unlimited "
            "access to all our journalism with a digital subscription today."
        )
        items, _ = await _collect("02_summary_only_feed.xml", article=_fetched(text=paywall))

        assert len(items) == 2
        assert all("Subscribe to continue" not in item.raw_text for item in items)


# ---------------------------------------------------------------------------
# Adversarial and degenerate feeds
# ---------------------------------------------------------------------------

_TITLELESS_EMPTY_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Degenerate Outlet</title>
    <item>
      <title></title>
      <link>https://degenerate.example.in/nothing-here</link>
      <description></description>
      <pubDate>Mon, 20 Jul 2026 09:30:00 +0530</pubDate>
    </item>
    <item>
      <title>No link on this one</title>
      <description>An entry with no link cannot be stored or revisited.</description>
    </item>
  </channel>
</rss>"""


class TestDegenerateFeeds:
    async def test_entry_with_no_text_anywhere_is_dropped(self):
        """An entry with no body, no fetched article and no title is not an item."""
        items, _ = await _collect_bytes(_TITLELESS_EMPTY_FEED, article=_fetched(text=None))

        assert items == []

    async def test_entry_with_no_link_is_dropped(self):
        """A link is the item's identity and its only route back to the article."""
        from anveshak.scraper.rss import parse_feed_items

        parsed = parse_feed_items(_TITLELESS_EMPTY_FEED, "https://degenerate.example.in/rss")

        assert [item.url for item in parsed] == ["https://degenerate.example.in/nothing-here"]

    async def test_oversized_body_fragment_is_bounded_and_reported(self):
        """Feed markup is adversarial input, so the parser input is bounded."""
        from anveshak.scraper import rss as rss_module

        oversized = "<p>" + ("word " * 200_000) + "</p>"
        text = rss_module._fragment_text(oversized, "https://outlet.example.in/a")

        assert len(text) <= rss_module._MAX_BODY_FRAGMENT_CHARS
        assert text.startswith("word word")

    async def test_unparseable_feed_date_is_not_a_date(self):
        """A struct that cannot be a datetime leaves the entry undated."""
        from anveshak.scraper.rss import _entry_published_at

        assert _entry_published_at({"published_parsed": (2026, 13, 45, 99, 0, 0)}) == (None, None)


# ---------------------------------------------------------------------------
# Untrusted address handling
# ---------------------------------------------------------------------------


class TestUntrustedLinks:
    async def test_link_to_an_internal_address_is_never_fetched(self):
        """A feed chooses the link, so it can name a service on our own network."""
        items, fetch_article = await _collect("02_summary_only_feed.xml", address_external=False)

        assert fetch_article.await_count == 0
        assert len(items) == 2  # the feed summary is still kept

    async def test_address_is_validated_before_robots_and_before_the_gap(self):
        """The robots.txt request goes to the host the feed named, so it is guarded too."""
        from anveshak.scraper import rss as rss_module

        order: list[str] = []

        async def _validate(url: str) -> bool:
            order.append("validate")
            return False

        async def _robots(url: str) -> bool:
            order.append("robots")
            return True

        class _Limiter:
            async def wait(self, url: str) -> None:
                order.append("wait")

        with (
            _feed_served(_feed_bytes("02_summary_only_feed.xml")),
            patch("anveshak.scraper.rss.fetch_article", new=AsyncMock(return_value=_fetched())),
            patch("anveshak.scraper.rss.validate_external_url_resolved", new=_validate),
            patch("anveshak.scraper.rss.check_robots_allowed", new=_robots),
        ):
            await rss_module.fetch_rss_items("https://feed.example.in/rss", limiter=_Limiter())

        assert order == ["validate", "validate"]

    async def test_gap_is_taken_before_the_robots_request(self):
        """An entry list naming many hosts must not outrun the per-domain gap."""
        from anveshak.scraper import rss as rss_module

        order: list[str] = []

        async def _robots(url: str) -> bool:
            order.append("robots")
            return True

        class _Limiter:
            async def wait(self, url: str) -> None:
                order.append("wait")

        with (
            _feed_served(_feed_bytes("02_summary_only_feed.xml")),
            patch("anveshak.scraper.rss.fetch_article", new=AsyncMock(return_value=_fetched())),
            patch(
                "anveshak.scraper.rss.validate_external_url_resolved",
                new=AsyncMock(return_value=True),
            ),
            patch("anveshak.scraper.rss.check_robots_allowed", new=_robots),
        ):
            await rss_module.fetch_rss_items("https://feed.example.in/rss", limiter=_Limiter())

        assert order[:2] == ["wait", "robots"]


# ---------------------------------------------------------------------------
# Bounds on what a publisher can make us read
# ---------------------------------------------------------------------------


class TestBounds:
    async def test_feed_past_the_byte_bound_is_refused(self):
        """Measured after decompression, so a small response cannot expand past it."""
        from anveshak.scraper import rss as rss_module

        oversized = b"<rss><channel>" + (b"<!-- pad -->" * 2_000_000) + b"</channel></rss>"
        assert len(oversized) > rss_module._MAX_FEED_BYTES

        items, _ = await _collect_bytes(oversized)

        assert items == []

    async def test_a_date_only_need_does_not_start_a_browser(self):
        """An undated feed with usable bodies costs one document read, not one browser."""
        from anveshak.scraper import rss as rss_module

        fetch_article = AsyncMock(return_value=_fetched())
        fetch_html = AsyncMock(return_value=_ARTICLE_WITH_JSONLD)
        long_body_undated = _feed_bytes("05_undated_feed.xml").replace(
            b"<description>The march route was published.</description>",
            b"<description>"
            + (b"The march route was published in full. " * 20)
            + b"</description>",
        )

        with (
            _feed_served(long_body_undated),
            patch("anveshak.scraper.rss.fetch_article", new=fetch_article),
            patch("anveshak.scraper.rss.fetch_html", new=fetch_html),
            patch(
                "anveshak.scraper.rss.validate_external_url_resolved",
                new=AsyncMock(return_value=True),
            ),
            patch("anveshak.scraper.rss.check_robots_allowed", new=AsyncMock(return_value=True)),
        ):
            items = await rss_module.fetch_rss_items("https://feed.example.in/rss")

        assert fetch_article.await_count == 0
        assert fetch_html.await_count == 1
        assert items[0].published_at == datetime(2026, 7, 19, 13, 0, tzinfo=UTC)
        assert "march route was published in full" in items[0].raw_text

    async def test_entry_carrying_many_content_blocks_is_bounded(self):
        """The per-fragment bound alone does not bound an entry."""
        from anveshak.scraper import rss as rss_module

        entry = {"content": [{"value": f"<p>block {i}</p>"} for i in range(50)]}
        body = rss_module._entry_body(entry, "https://outlet.example.in/a")

        assert body.startswith("block ")
        assert int(body.split()[1]) < rss_module._MAX_BODY_BLOCKS
