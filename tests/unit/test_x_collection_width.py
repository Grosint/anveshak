"""X collection width — issue #23.

The adapter fetched ten items per search call against a platform maximum of
one hundred, at identical cost per item. The width is now a setting, so
collection depth changes without a code change, and the spend guard still
gates every call.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anveshak.social.adapters.x_adapter import XPollingAdapter
from anveshak.social.settings import settings

pytestmark = pytest.mark.unit


def _make_adapter(*, allowed: bool = True) -> tuple[XPollingAdapter, MagicMock]:
    """An authenticated adapter with its client and spend guard stubbed."""
    adapter = XPollingAdapter(MagicMock())

    client = MagicMock()
    response = MagicMock()
    response.data = []
    client.search_recent_tweets = AsyncMock(return_value=response)

    guard = MagicMock()
    guard.check_and_increment = AsyncMock(return_value=allowed)

    adapter._client = client
    adapter._spend_guard = guard
    return adapter, client


async def _collect(adapter: XPollingAdapter) -> list:
    return [item async for item in adapter.collect(["protest"], [], "topic-1")]


class TestWidthComesFromSettings:
    async def test_default_width_is_the_platform_maximum(self):
        """One hundred is the X recent-search maximum. Same cost per item."""
        assert settings.x_max_results == 100

    async def test_search_call_uses_the_configured_width(self):
        adapter, client = _make_adapter()
        await _collect(adapter)
        assert client.search_recent_tweets.await_args.kwargs["max_results"] == (
            settings.x_max_results
        )

    async def test_changing_the_setting_changes_the_call(self):
        """Rule 6: no collection parameter is hardcoded in service code."""
        adapter, client = _make_adapter()
        with patch.object(settings, "x_max_results", 25):
            await _collect(adapter)
        assert client.search_recent_tweets.await_args.kwargs["max_results"] == 25


class TestSpendGuardUnchanged:
    async def test_guard_is_checked_before_every_call(self):
        adapter, client = _make_adapter()
        await _collect(adapter)
        adapter._spend_guard.check_and_increment.assert_awaited_once()

    async def test_blocked_call_makes_no_api_request(self):
        """Criteria 3.30 still holds: at cap, no network activity."""
        adapter, client = _make_adapter(allowed=False)
        items = await _collect(adapter)
        assert items == []
        client.search_recent_tweets.assert_not_awaited()

    async def test_width_does_not_change_reads_charged_per_call(self):
        """One search call is one guarded read regardless of width."""
        adapter, client = _make_adapter()
        with patch.object(settings, "x_max_results", 100):
            await _collect(adapter)
        assert adapter._spend_guard.check_and_increment.await_count == 1


class TestLanguageFilter:
    """The search query hardcoded lang:en.

    Every day the adapter runs English-only is a day of Hindi discourse
    permanently missing, because the X search window reaches back seven days.
    #28 scores stance in the content's own language and #33 detects
    mobilization in Hindi, so both read from a corpus this filter shapes.
    """

    async def test_default_covers_english_and_hindi(self):
        assert "en" in settings.x_search_languages
        assert "hi" in settings.x_search_languages

    async def test_query_filters_on_every_configured_language(self):
        adapter, client = _make_adapter()
        with patch.object(settings, "x_search_languages", ["en", "hi"]):
            await _collect(adapter)
        query = client.search_recent_tweets.await_args.kwargs["query"]
        assert "lang:en" in query
        assert "lang:hi" in query

    async def test_empty_language_list_applies_no_filter(self):
        adapter, client = _make_adapter()
        with patch.object(settings, "x_search_languages", []):
            await _collect(adapter)
        assert "lang:" not in client.search_recent_tweets.await_args.kwargs["query"]

    async def test_retweets_are_still_excluded(self):
        adapter, client = _make_adapter()
        await _collect(adapter)
        assert "-is:retweet" in client.search_recent_tweets.await_args.kwargs["query"]
