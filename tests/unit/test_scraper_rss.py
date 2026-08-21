"""Unit tests for RSS feed fetcher (services/scraper/anveshak/scraper/rss.py).

All tests run on CPU with no external dependencies (network mocked via httpx.MockTransport).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>J-20 spotted near Hotan airbase</title>
      <link>https://example.com/j20-hotan</link>
      <description>Short summary.</description>
      <pubDate>Thu, 01 Jan 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>PAF JF-17 Block III deliveries</title>
      <link>https://example.com/jf17-block3</link>
      <description>Pakistan Air Force received three additional JF-17 Block III fighters today, bringing the total delivered under the latest batch to twelve aircraft. The upgraded variant features an AESA radar and extended-range PL-15 missiles.</description>
      <pubDate>Thu, 01 Jan 2026 12:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""

_EMPTY_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Empty</title></channel></rss>"""


def _make_http_response(content: bytes, url: str = "https://example.com/feed", status: int = 200):
    """Build a minimal httpx.Response with a request set (required for raise_for_status)."""
    import httpx

    request = httpx.Request("GET", url)
    return httpx.Response(status_code=status, content=content, request=request)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_rss_content_hash_deterministic():
    """Same article text always produces the same SHA-256 content_hash."""
    from anveshak.scraper.normalise import compute_content_hash

    text = "Pakistan Air Force received three additional JF-17 Block III fighters."
    assert compute_content_hash(text) == compute_content_hash(text)
    assert len(compute_content_hash(text)) == 64  # SHA-256 hex


@pytest.mark.unit
def test_rss_item_url_non_empty():
    """Every RssItem returned by _parse_feed_sync has a non-empty url."""
    from anveshak.scraper.rss import _parse_feed_sync

    items = _parse_feed_sync(_MINIMAL_RSS, "https://example.com/feed")
    assert all(item.url for item in items), "All RssItems must have a non-empty url"


@pytest.mark.unit
def test_rss_published_at_timezone_aware():
    """Every RssItem.published_at must be timezone-aware (never naive)."""
    from anveshak.scraper.rss import _parse_feed_sync

    items = _parse_feed_sync(_MINIMAL_RSS, "https://example.com/feed")
    assert items, "Expected at least one item"
    for item in items:
        assert item.published_at.tzinfo is not None, (
            f"published_at for {item.url} is naive — must be timezone-aware"
        )


@pytest.mark.unit
def test_rss_short_summary_triggers_full_fetch():
    """Entry with summary < rss_full_text_min_chars triggers fetch_url() for full text."""
    from anveshak.scraper import rss as rss_module

    full_text = (
        "Full article: J-20 stealth fighters have been observed at Hotan airbase "
        "in satellite imagery from multiple commercial providers, confirming a "
        "significant forward deployment along the Line of Actual Control."
    )

    async def _run():
        with patch("anveshak.scraper.rss.fetch_url", new=AsyncMock(return_value=full_text)):
            with patch("anveshak.scraper.rss.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(
                    return_value=_make_http_response(_MINIMAL_RSS, url="https://example.com/feed")
                )
                mock_client_cls.return_value = mock_client

                items = await rss_module.fetch_rss_items("https://example.com/feed")

        # First item has short summary ("Short summary.") → full_text should be used
        matches = [i for i in items if "j20-hotan" in i.url]
        assert matches, "Expected item with url containing 'j20-hotan'"
        assert matches[0].raw_text == full_text

    asyncio.run(_run())


@pytest.mark.unit
def test_rss_empty_feed_returns_empty_list():
    """An RSS feed with no entries returns [] without raising."""
    from anveshak.scraper import rss as rss_module

    async def _run():
        with patch("anveshak.scraper.rss.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(
                return_value=_make_http_response(_EMPTY_RSS, url="https://example.com/feed")
            )
            mock_client_cls.return_value = mock_client

            items = await rss_module.fetch_rss_items("https://example.com/feed")

        assert items == []

    asyncio.run(_run())


@pytest.mark.unit
def test_rss_feed_fetch_failure_returns_empty_list():
    """Network failure fetching the feed returns [] — never raises."""
    import httpx
    from anveshak.scraper import rss as rss_module

    async def _run():
        with patch("anveshak.scraper.rss.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_cls.return_value = mock_client

            items = await rss_module.fetch_rss_items("https://dead-feed.example.com/feed")

        assert items == []

    asyncio.run(_run())


@pytest.mark.unit
def test_fetch_py_user_agent_not_bot_declared():
    """fetch.py User-Agent must not contain 'Anveshak/1.0' — that string is a bot declaration."""
    import inspect

    import anveshak.scraper.fetch as fetch_module

    source = inspect.getsource(fetch_module)
    assert "Anveshak/1.0" not in source, (
        "User-Agent 'Anveshak/1.0' detected in fetch.py — this identifies us as a bot. "
        "Use a real browser UA string."
    )
