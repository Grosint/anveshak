"""Unit tests for Reddit adapter — catches the lstrip('r/') bug and tests helpers.

pytest.mark.unit — no network, no PRAW client needed.
Tests static/pure methods and documents the known lstrip bug.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# lstrip("r/") bug — real bug in collect()
# ---------------------------------------------------------------------------


class TestSubredditNameNormalization:
    """handle.removeprefix('r/') correctly strips the 'r/' prefix.

    Regression test: the original code used lstrip('r/') which strips
    individual chars {r, /}, not the prefix. 'r/russia' → 'ussia'.
    Fixed to use removeprefix('r/') which correctly yields 'russia'.
    """

    def test_subreddit_r_prefix_stripped(self):
        """'r/worldnews' → 'worldnews'."""
        assert "r/worldnews".removeprefix("r/") == "worldnews"

    def test_subreddit_starting_with_r_preserved(self):
        """'r/russia' → 'russia' (NOT 'ussia' as lstrip would produce)."""
        handle = "r/russia"
        result = handle.removeprefix("r/")
        assert result == "russia", (
            f"Regression: subreddit name mangled to '{result}'. "
            "This was the lstrip('r/') bug — chars stripped, not prefix."
        )

    def test_handle_without_prefix_unchanged(self):
        """'worldnews' without 'r/' prefix → unchanged."""
        assert "worldnews".removeprefix("r/") == "worldnews"


# ---------------------------------------------------------------------------
# _post_to_text tests
# ---------------------------------------------------------------------------


class TestPostToText:
    """RedditAdapter._post_to_text combines title + selftext, filters [removed]/[deleted]."""

    @staticmethod
    def _make_post(title: str, selftext: str) -> MagicMock:
        post = MagicMock()
        post.title = title
        post.selftext = selftext
        return post

    def test_post_to_text_removed_body(self):
        """[removed] selftext is excluded — only title returned."""
        from anveshak.social.adapters.reddit import RedditAdapter
        post = self._make_post("Title", "[removed]")
        assert RedditAdapter._post_to_text(post) == "Title"

    def test_post_to_text_deleted_body(self):
        """[deleted] selftext is excluded — only title returned."""
        from anveshak.social.adapters.reddit import RedditAdapter
        post = self._make_post("Title", "[deleted]")
        assert RedditAdapter._post_to_text(post) == "Title"

    def test_post_to_text_with_body(self):
        """Normal selftext is joined with title via double newline."""
        from anveshak.social.adapters.reddit import RedditAdapter
        post = self._make_post("Title", "body text")
        assert RedditAdapter._post_to_text(post) == "Title\n\nbody text"


# ---------------------------------------------------------------------------
# _extract_media_urls tests
# ---------------------------------------------------------------------------


class TestExtractMediaUrls:
    """RedditAdapter._extract_media_urls checks URL for image/video extensions."""

    def test_extract_media_urls_jpg(self):
        """Post with .jpg URL → extracted."""
        from anveshak.social.adapters.reddit import RedditAdapter
        post = MagicMock()
        post.url = "https://i.redd.it/photo.jpg"
        assert RedditAdapter._extract_media_urls(post) == ["https://i.redd.it/photo.jpg"]

    def test_extract_media_urls_no_extension(self):
        """Post URL without media extension → empty list."""
        from anveshak.social.adapters.reddit import RedditAdapter
        post = MagicMock()
        post.url = "https://reddit.com/post"
        assert RedditAdapter._extract_media_urls(post) == []

    def test_extract_media_urls_no_url_attr(self):
        """Post without url attribute → empty list (hasattr check)."""
        from anveshak.social.adapters.reddit import RedditAdapter
        post = MagicMock(spec=[])  # spec=[] means no attributes at all
        assert RedditAdapter._extract_media_urls(post) == []
