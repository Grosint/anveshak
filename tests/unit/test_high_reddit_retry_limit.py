"""Unit tests for Reddit backoff retry limit — HIGH-13.

The retry loop must not continue indefinitely after exhausting backoff steps.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestRedditRetryLimit:

    def test_backoff_has_explicit_max_retries(self):
        """_BACKOFF_SECONDS length must match the retry limit."""
        from anveshak.social.adapters.reddit import _BACKOFF_SECONDS

        # Backoff list exists and has reasonable length
        assert isinstance(_BACKOFF_SECONDS, (list, tuple))
        assert len(_BACKOFF_SECONDS) <= 5, "Too many backoff steps — keep it bounded"

    @pytest.mark.asyncio
    async def test_rate_limit_exhaustion_raises_after_max_retries(self):
        """After exhausting all backoff steps, must raise AdapterRateLimitError."""
        from anveshak.social.adapters.reddit import RedditAdapter, _BACKOFF_SECONDS
        from anveshak.social.adapters.base import AdapterRateLimitError
        import praw.exceptions

        adapter = RedditAdapter.__new__(RedditAdapter)
        adapter._reddit = MagicMock()

        # _fetch_feed always raises RATELIMIT
        def always_rate_limit(*args, **kwargs):
            raise praw.exceptions.RedditAPIException(
                items=[["RATELIMIT", "rate limit", ""]],
            )

        adapter._fetch_feed = always_rate_limit

        # Collect should raise AdapterRateLimitError after exhausting retries
        with pytest.raises(AdapterRateLimitError):
            items = []
            # Patch sleep to avoid real delays
            with patch("asyncio.sleep", new_callable=AsyncMock):
                async for item in adapter._poll_subreddit("test_sub", "r/test", ["keyword"]):
                    items.append(item)

    @pytest.mark.asyncio
    async def test_retry_count_matches_backoff_steps(self):
        """Number of fetch attempts must equal 1 (initial) + len(_BACKOFF_SECONDS)."""
        from anveshak.social.adapters.reddit import RedditAdapter, _BACKOFF_SECONDS
        from anveshak.social.adapters.base import AdapterRateLimitError
        import praw.exceptions

        adapter = RedditAdapter.__new__(RedditAdapter)
        adapter._reddit = MagicMock()

        attempt_count = {"n": 0}

        def counting_rate_limit(*args, **kwargs):
            attempt_count["n"] += 1
            raise praw.exceptions.RedditAPIException(
                items=[["RATELIMIT", "rate limit", ""]],
            )

        adapter._fetch_feed = counting_rate_limit

        with patch("asyncio.sleep", new_callable=AsyncMock):
            try:
                async for _ in adapter._poll_subreddit("test_sub", "r/test", ["kw"]):
                    pass
            except AdapterRateLimitError:
                pass

        expected = 1 + len(_BACKOFF_SECONDS)  # initial + retries
        assert attempt_count["n"] == expected, (
            f"Expected {expected} attempts, got {attempt_count['n']}"
        )
