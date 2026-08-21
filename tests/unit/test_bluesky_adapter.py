"""Unit tests for Bluesky adapter — URI parsing, timestamp handling, media extraction.

pytest.mark.unit — no atproto client, no network.
Tests static helper methods on BlueskyAdapter.
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


class TestUriToUrl:
    """BlueskyAdapter._uri_to_url converts AT URIs to bsky.app URLs."""

    def test_uri_to_url_standard(self):
        """Standard AT URI → bsky.app profile URL with rkey."""
        from anveshak.social.adapters.bluesky import BlueskyAdapter

        uri = "at://did:plc:abc/app.bsky.feed.post/rkey123"
        result = BlueskyAdapter._uri_to_url(uri, "user.bsky.social")
        assert result == "https://bsky.app/profile/user.bsky.social/post/rkey123"


class TestParseIndexedAt:
    """BlueskyAdapter._parse_indexed_at handles ISO 8601 timestamps."""

    def test_parse_indexed_at_z_suffix(self):
        """'Z' suffix → UTC datetime."""
        from anveshak.social.adapters.bluesky import BlueskyAdapter

        result = BlueskyAdapter._parse_indexed_at("2026-01-15T10:30:00Z")
        expected = datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc)
        assert result == expected

    def test_parse_indexed_at_with_timezone(self):
        """'+00:00' suffix → same UTC datetime."""
        from anveshak.social.adapters.bluesky import BlueskyAdapter

        result = BlueskyAdapter._parse_indexed_at("2026-01-15T10:30:00+00:00")
        expected = datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc)
        assert result == expected

    def test_parse_indexed_at_invalid_fallback(self):
        """Invalid date string → falls back to datetime.now(UTC)."""
        from anveshak.social.adapters.bluesky import BlueskyAdapter

        before = datetime.now(UTC)
        result = BlueskyAdapter._parse_indexed_at("not-a-date")
        after = datetime.now(UTC)
        # Result should be between before and after (within 2 seconds)
        assert before <= result <= after


class TestExtractMediaUrls:
    """BlueskyAdapter._extract_media_urls constructs blob URLs from embed images."""

    def test_extract_media_urls_with_images(self):
        """Post with embed.images → blob URL constructed from did + cid."""
        from anveshak.social.adapters.bluesky import BlueskyAdapter

        # Build mock post structure: post.record.embed.images[0].image.ref.link
        ref = MagicMock()
        ref.link = "cid123"
        image = MagicMock()
        image.image = MagicMock()
        image.image.ref = ref

        embed = MagicMock()
        embed.images = [image]

        record = MagicMock()
        record.embed = embed

        author = MagicMock()
        author.did = "did:plc:abc"

        post = MagicMock()
        post.record = record
        post.author = author

        urls = BlueskyAdapter._extract_media_urls(post)
        assert len(urls) == 1
        assert "did=did:plc:abc" in urls[0]
        assert "cid=cid123" in urls[0]
        assert "com.atproto.sync.getBlob" in urls[0]

    def test_extract_media_urls_no_embed(self):
        """Post with no embed → empty list."""
        from anveshak.social.adapters.bluesky import BlueskyAdapter

        record = MagicMock()
        record.embed = None

        post = MagicMock()
        post.record = record
        post.author = MagicMock()

        urls = BlueskyAdapter._extract_media_urls(post)
        assert urls == []

    def test_extract_media_urls_embed_no_images(self):
        """Post with embed but no images attribute → empty list."""
        from anveshak.social.adapters.bluesky import BlueskyAdapter

        embed = MagicMock(spec=[])  # spec=[] means no attributes — hasattr returns False
        record = MagicMock()
        record.embed = embed

        post = MagicMock()
        post.record = record
        post.author = MagicMock()

        urls = BlueskyAdapter._extract_media_urls(post)
        assert urls == []
