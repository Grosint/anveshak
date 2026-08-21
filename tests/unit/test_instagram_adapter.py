"""Unit tests for Instagram adapter — handle normalization, post/bio extraction, media URLs, rate limit.

pytest.mark.unit — no Instagrapi client, no network.
Tests static helper methods and pure logic on InstagramAdapter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers — mock Instagram API objects
# ---------------------------------------------------------------------------


def _mock_media(
    caption: str = "Buy now! Contact +919876543210",
    shortcode: str = "CxYz123AbC",
    taken_at: int = 1717200000,
    image_versions: list[str] | None = None,
    video_url: str | None = None,
    user_handle: str = "scam_seller",
) -> MagicMock:
    """Build a mock Instagrapi Media object."""
    media = MagicMock()
    media.caption_text = caption
    media.code = shortcode
    media.taken_at = taken_at  # Unix timestamp
    media.user = MagicMock()
    media.user.username = user_handle

    # Thumbnail URL (always present)
    media.thumbnail_url = f"https://scontent.cdninstagram.com/{shortcode}_thumb.jpg"

    # Image versions
    if image_versions is None:
        image_versions = [f"https://scontent.cdninstagram.com/{shortcode}_1080.jpg"]
    media.image_versions2 = image_versions

    # Video
    media.video_url = video_url
    media.media_type = 2 if video_url else 1  # 1=photo, 2=video

    return media


def _mock_user_info(
    username: str = "scam_seller",
    biography: str = "DM for deals! UPI: seller@ybl | +91-98765-43210",
    follower_count: int = 15000,
    following_count: int = 200,
    is_private: bool = False,
) -> MagicMock:
    """Build a mock Instagrapi UserInfo object."""
    user = MagicMock()
    user.username = username
    user.biography = biography
    user.follower_count = follower_count
    user.following_count = following_count
    user.is_private = is_private
    user.pk = 12345678
    return user


# ---------------------------------------------------------------------------
# Handle normalization
# ---------------------------------------------------------------------------


class TestHandleNormalization:
    """InstagramAdapter._normalise_handle strips @ and lowercases."""

    def test_at_prefix_stripped(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        assert InstagramAdapter._normalise_handle("@ScamSeller") == "scamseller"

    def test_bare_handle_lowered(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        assert InstagramAdapter._normalise_handle("ScamSeller") == "scamseller"

    def test_already_normalised(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        assert InstagramAdapter._normalise_handle("scamseller") == "scamseller"

    def test_instagram_url_stripped(self):
        """Handle provided as full Instagram URL."""
        from anveshak.social.adapters.instagram import InstagramAdapter

        assert (
            InstagramAdapter._normalise_handle("https://instagram.com/ScamSeller") == "scamseller"
        )

    def test_instagram_url_with_trailing_slash(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        assert (
            InstagramAdapter._normalise_handle("https://www.instagram.com/ScamSeller/")
            == "scamseller"
        )


# ---------------------------------------------------------------------------
# Post extraction helpers
# ---------------------------------------------------------------------------


class TestPostToRawItem:
    """InstagramAdapter._media_to_raw_item converts Instagrapi Media to RawItem."""

    def test_basic_post_extraction(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media()
        raw = InstagramAdapter._media_to_raw_item(media, "scam_seller")
        assert raw.raw_text == "Buy now! Contact +919876543210"
        assert raw.platform == "instagram"
        assert raw.source_handle == "scam_seller"

    def test_url_uses_shortcode(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media(shortcode="AbCdEf123")
        raw = InstagramAdapter._media_to_raw_item(media, "test_user")
        assert raw.url == "https://www.instagram.com/p/AbCdEf123/"

    def test_captured_at_is_utc(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media(taken_at=1717200000)
        raw = InstagramAdapter._media_to_raw_item(media, "user")
        assert raw.captured_at.tzinfo is not None

    def test_media_urls_includes_thumbnail(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media()
        raw = InstagramAdapter._media_to_raw_item(media, "user")
        assert len(raw.media_urls) >= 1
        assert any("thumb" in u or "1080" in u for u in raw.media_urls)

    def test_video_url_included(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media(video_url="https://scontent.cdninstagram.com/video.mp4")
        raw = InstagramAdapter._media_to_raw_item(media, "user")
        assert "video.mp4" in " ".join(raw.media_urls)

    def test_empty_caption_uses_empty_string(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media(caption="")
        raw = InstagramAdapter._media_to_raw_item(media, "user")
        assert raw.raw_text == ""


# ---------------------------------------------------------------------------
# Bio extraction
# ---------------------------------------------------------------------------


class TestBioExtraction:
    """InstagramAdapter._bio_to_raw_item creates RawItem from profile bio."""

    def test_bio_raw_item_platform(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        user_info = _mock_user_info()
        raw = InstagramAdapter._bio_to_raw_item(user_info)
        assert raw.platform == "instagram_bio"

    def test_bio_raw_text_is_biography(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        user_info = _mock_user_info(biography="Call me at +919876543210")
        raw = InstagramAdapter._bio_to_raw_item(user_info)
        assert raw.raw_text == "Call me at +919876543210"

    def test_bio_url_format(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        user_info = _mock_user_info(username="seller123")
        raw = InstagramAdapter._bio_to_raw_item(user_info)
        assert raw.url == "https://www.instagram.com/seller123/"

    def test_bio_source_handle(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        user_info = _mock_user_info(username="seller123")
        raw = InstagramAdapter._bio_to_raw_item(user_info)
        assert raw.source_handle == "seller123"

    def test_bio_labels_include_follower_counts(self):
        """Bio RawItem should carry follower/following in media_urls=[] (labels go via ingest)."""
        from anveshak.social.adapters.instagram import InstagramAdapter

        user_info = _mock_user_info(follower_count=15000, following_count=200)
        raw = InstagramAdapter._bio_to_raw_item(user_info)
        # Bio items have no media
        assert raw.media_urls == []
        # captured_at is timezone-aware
        assert raw.captured_at.tzinfo is not None


# ---------------------------------------------------------------------------
# Media URL extraction
# ---------------------------------------------------------------------------


class TestExtractMediaUrls:
    """InstagramAdapter._extract_media_urls pulls image/video URLs from Media."""

    def test_photo_post_extracts_thumbnail(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media()
        urls = InstagramAdapter._extract_media_urls(media)
        assert len(urls) >= 1

    def test_video_post_includes_video_url(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media(video_url="https://cdn.instagram.com/v.mp4")
        urls = InstagramAdapter._extract_media_urls(media)
        assert "https://cdn.instagram.com/v.mp4" in urls

    def test_no_media_returns_empty(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = MagicMock()
        media.thumbnail_url = None
        media.video_url = None
        media.image_versions2 = None
        urls = InstagramAdapter._extract_media_urls(media)
        assert urls == []


# ---------------------------------------------------------------------------
# Rate limit guard
# ---------------------------------------------------------------------------


class TestInstagramRateLimitGuard:
    """InstagramRateLimitGuard enforces 100 requests/hour via Redis atomic counter."""

    @pytest.mark.asyncio
    async def test_under_limit_permits(self):
        from anveshak.social.adapters.instagram import InstagramRateLimitGuard

        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=50)
        redis.expire = AsyncMock()
        guard = InstagramRateLimitGuard(redis, cap=100)
        assert await guard.check_and_increment() is True

    @pytest.mark.asyncio
    async def test_at_cap_blocks(self):
        from anveshak.social.adapters.instagram import InstagramRateLimitGuard

        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=101)
        redis.decr = AsyncMock()
        guard = InstagramRateLimitGuard(redis, cap=100)
        assert await guard.check_and_increment() is False

    @pytest.mark.asyncio
    async def test_first_call_sets_ttl(self):
        from anveshak.social.adapters.instagram import InstagramRateLimitGuard

        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        redis.expire = AsyncMock()
        guard = InstagramRateLimitGuard(redis, cap=100)
        await guard.check_and_increment()
        redis.expire.assert_called_once()
        # TTL should be <= 3600 seconds (1 hour)
        ttl_arg = redis.expire.call_args[0][1]
        assert 0 < ttl_arg <= 3600

    @pytest.mark.asyncio
    async def test_cap_exceeded_decrements(self):
        from anveshak.social.adapters.instagram import InstagramRateLimitGuard

        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=101)
        redis.decr = AsyncMock()
        guard = InstagramRateLimitGuard(redis, cap=100)
        await guard.check_and_increment()
        redis.decr.assert_called_once()

    @pytest.mark.asyncio
    async def test_current_count_reads_without_increment(self):
        from anveshak.social.adapters.instagram import InstagramRateLimitGuard

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"42")
        guard = InstagramRateLimitGuard(redis, cap=100)
        count = await guard.current_count()
        assert count == 42
        redis.incr.assert_not_called()


# ---------------------------------------------------------------------------
# Adapter class attributes
# ---------------------------------------------------------------------------


class TestAdapterAttributes:
    """InstagramAdapter has correct class-level attributes."""

    def test_adapter_id(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        assert adapter.adapter_id == "instagram-v1"

    def test_platform(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        assert adapter.platform == "instagram"

    def test_adapter_version(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        assert adapter.adapter_version == "1.0.0"

    def test_no_client_before_auth(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        assert adapter._client is None

    def test_circuit_breaker_params(self):
        """Instagram uses higher threshold (10) and longer cooldown (24h) per plan."""
        from anveshak.social.adapters.instagram import (
            INSTAGRAM_CIRCUIT_BREAKER_COOLDOWN_S,
            INSTAGRAM_CIRCUIT_BREAKER_THRESHOLD,
        )

        assert INSTAGRAM_CIRCUIT_BREAKER_THRESHOLD == 10
        assert INSTAGRAM_CIRCUIT_BREAKER_COOLDOWN_S == 86400


# ---------------------------------------------------------------------------
# Conformance (reuse pattern from test_social_conformance.py)
# ---------------------------------------------------------------------------


class TestInstagramConformance:
    """Instagram adapter passes SourceAdapterConformanceSuite."""

    def test_platform_in_allowed_set(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        assert adapter.platform in {"telegram", "reddit", "bluesky", "twitter", "web", "instagram"}

    def test_adapter_id_kebab_case(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        assert "-" in adapter.adapter_id

    def test_raw_item_content_hash_deterministic(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media()
        raw = InstagramAdapter._media_to_raw_item(media, "user")
        h1 = raw.content_hash()
        h2 = raw.content_hash()
        assert h1 == h2
        assert len(h1) == 64

    def test_raw_item_url_non_empty(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media()
        raw = InstagramAdapter._media_to_raw_item(media, "user")
        assert raw.url

    def test_raw_item_captured_at_timezone_aware(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media()
        raw = InstagramAdapter._media_to_raw_item(media, "user")
        assert raw.captured_at.tzinfo is not None

    def test_raw_item_platform_matches_adapter(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        media = _mock_media()
        raw = InstagramAdapter._media_to_raw_item(media, "user")
        assert raw.platform == adapter.platform


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


class TestSessionManagement:
    """InstagramAdapter handles session login and re-login."""

    @pytest.mark.asyncio
    async def test_authenticate_calls_login(self):
        """authenticate() should call Instagrapi Client.login."""
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        mock_client = MagicMock()
        mock_client.login = MagicMock(return_value=True)
        with patch("instagrapi.Client", return_value=mock_client):
            with patch("anveshak.social.adapters.instagram.settings") as mock_settings:
                mock_settings.instagram_adapter_enabled = True
                mock_settings.instagram_username = "test_user"
                mock_settings.instagram_password = "test_pass"
                mock_settings.instagram_session_path = ""
                await adapter.authenticate()
        assert adapter._client is not None

    @pytest.mark.asyncio
    async def test_authenticate_disabled_logs_warning(self):
        """authenticate() with adapter disabled should not raise."""
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        with patch("anveshak.social.adapters.instagram.settings") as mock_settings:
            mock_settings.instagram_adapter_enabled = False
            await adapter.authenticate()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_refresh_credentials_returns_true_on_success(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter.authenticate = AsyncMock()
        result = await adapter.refresh_credentials()
        assert result is True

    @pytest.mark.asyncio
    async def test_refresh_credentials_returns_false_on_failure(self):
        from anveshak.social.adapters.base import AdapterAuthError
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter.authenticate = AsyncMock(side_effect=AdapterAuthError("bad creds"))
        result = await adapter.refresh_credentials()
        assert result is False

    @pytest.mark.asyncio
    async def test_authenticate_raises_when_enabled_no_creds(self):
        """adapter enabled but no username/password → AdapterAuthError."""
        from anveshak.social.adapters.base import AdapterAuthError
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        with patch("anveshak.social.adapters.instagram.settings") as mock_settings:
            mock_settings.instagram_adapter_enabled = True
            mock_settings.instagram_username = None
            mock_settings.instagram_password = None
            with pytest.raises(AdapterAuthError, match="INSTAGRAM_USERNAME"):
                await adapter.authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_with_session_path(self):
        """Session path provided → load_settings called first."""
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        mock_client = MagicMock()
        mock_client.login = MagicMock(return_value=True)
        mock_client.load_settings = MagicMock()
        with patch("instagrapi.Client", return_value=mock_client):
            with patch("anveshak.social.adapters.instagram.settings") as mock_settings:
                mock_settings.instagram_adapter_enabled = True
                mock_settings.instagram_username = "user"
                mock_settings.instagram_password = "pass"
                mock_settings.instagram_session_path = "/tmp/session.json"
                await adapter.authenticate()
        mock_client.load_settings.assert_called_once_with("/tmp/session.json")

    @pytest.mark.asyncio
    async def test_authenticate_session_expired_relogin(self):
        """Session load fails → re-creates client and logs in fresh."""
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        mock_client = MagicMock()
        mock_client.load_settings = MagicMock(side_effect=Exception("session expired"))
        mock_client.login = MagicMock(return_value=True)
        # Second Client() call for re-login
        mock_client2 = MagicMock()
        mock_client2.login = MagicMock(return_value=True)
        with patch("instagrapi.Client", side_effect=[mock_client, mock_client2]):
            with patch("anveshak.social.adapters.instagram.settings") as mock_settings:
                mock_settings.instagram_adapter_enabled = True
                mock_settings.instagram_username = "user"
                mock_settings.instagram_password = "pass"
                mock_settings.instagram_session_path = "/tmp/session.json"
                await adapter.authenticate()
        assert adapter._client is not None


# ---------------------------------------------------------------------------
# Collect early returns
# ---------------------------------------------------------------------------


class TestCollectEarlyReturns:
    """Test collect() guard clauses and early returns."""

    @pytest.mark.asyncio
    async def test_collect_not_authenticated_yields_nothing(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter._client = None
        items = [item async for item in adapter.collect(["test"], ["@user"], "topic-1")]
        assert items == []

    @pytest.mark.asyncio
    async def test_health_no_client_returns_down(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter._client = None
        result = await adapter.health()
        assert result["status"] == "DOWN"

    @pytest.mark.asyncio
    async def test_health_with_client_calls_account_info(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        mock_client = MagicMock()
        mock_client.account_info = MagicMock(return_value=MagicMock())
        adapter._client = mock_client
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=MagicMock()):
            result = await adapter.health()
        assert result["status"] == "HEALTHY"

    @pytest.mark.asyncio
    async def test_health_with_exception_returns_degraded(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter._client = MagicMock()
        with patch("asyncio.to_thread", new_callable=AsyncMock, side_effect=Exception("oops")):
            result = await adapter.health()
        assert result["status"] == "DEGRADED"


# ---------------------------------------------------------------------------
# Hourly key and TTL helpers
# ---------------------------------------------------------------------------


class TestHourlyKeyHelpers:
    """Test _hourly_key and _seconds_until_hour_end."""

    def test_hourly_key_format(self):
        from anveshak.social.adapters.instagram import _hourly_key

        key = _hourly_key()
        assert key.startswith("anveshak:instagram:hourly_calls:")
        # Format: YYYY-MM-DD-HH
        import re

        suffix = key.split(":")[-1]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}", suffix), f"Bad key: {key}"

    def test_seconds_until_hour_end_positive(self):
        from anveshak.social.adapters.instagram import _seconds_until_hour_end

        ttl = _seconds_until_hour_end()
        assert 0 < ttl <= 3600


# ---------------------------------------------------------------------------
# Media timestamp parsing edge cases
# ---------------------------------------------------------------------------


class TestTimestampParsing:
    """_media_to_raw_item handles various timestamp formats."""

    def test_unix_int_timestamp(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media(taken_at=1717200000)
        raw = InstagramAdapter._media_to_raw_item(media, "user")
        assert raw.captured_at.year >= 2024
        assert raw.captured_at.tzinfo is not None

    def test_datetime_object_naive(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media()
        media.taken_at = datetime(2026, 1, 15, 10, 30)  # naive
        raw = InstagramAdapter._media_to_raw_item(media, "user")
        assert raw.captured_at.tzinfo is not None

    def test_datetime_object_aware(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media()
        media.taken_at = datetime(2026, 1, 15, 10, 30, tzinfo=UTC)
        raw = InstagramAdapter._media_to_raw_item(media, "user")
        assert raw.captured_at == datetime(2026, 1, 15, 10, 30, tzinfo=UTC)

    def test_none_timestamp_falls_back(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        media = _mock_media()
        media.taken_at = None
        raw = InstagramAdapter._media_to_raw_item(media, "user")
        assert raw.captured_at.tzinfo is not None


# ---------------------------------------------------------------------------
# Collect with mocked client
# ---------------------------------------------------------------------------


class TestCollectWithMockedClient:
    """Test collect() flows with mocked Instagrapi client."""

    @pytest.mark.asyncio
    async def test_profile_yields_bio_and_posts(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        mock_client = MagicMock()
        adapter._client = mock_client

        user_info = _mock_user_info(username="seller", is_private=False)
        media1 = _mock_media(caption="Post 1", shortcode="AAA")
        media2 = _mock_media(caption="Post 2", shortcode="BBB")

        async def fake_to_thread(fn, *args, **kwargs):
            name = fn.__name__ if hasattr(fn, "__name__") else str(fn)
            if "user_info" in name:
                return user_info
            if "user_medias" in name:
                return [media1, media2]
            return []

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            items = [item async for item in adapter.collect([], ["@seller"], "topic-1")]

        # Should yield: 1 bio + 2 posts = 3 items
        assert len(items) == 3
        assert items[0].platform == "instagram_bio"
        assert items[1].platform == "instagram"
        assert items[2].platform == "instagram"

    @pytest.mark.asyncio
    async def test_private_profile_skips_posts(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter._client = MagicMock()

        user_info = _mock_user_info(username="private_user", is_private=True)

        async def fake_to_thread(fn, *args, **kwargs):
            return user_info

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            items = [item async for item in adapter.collect([], ["@private_user"], "topic-1")]

        # Only bio (profile is private, posts skipped)
        assert len(items) == 1
        assert items[0].platform == "instagram_bio"

    @pytest.mark.asyncio
    async def test_hashtag_search_yields_posts(self):
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter._client = MagicMock()

        media1 = _mock_media(caption="Hashtag post", shortcode="HHH")

        async def fake_to_thread(fn, *args, **kwargs):
            return [media1]

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            items = [item async for item in adapter.collect(["scam"], [], "topic-1")]

        assert len(items) == 1
        assert items[0].raw_text == "Hashtag post"

    @pytest.mark.asyncio
    async def test_profile_error_continues(self):
        """Per-handle errors are logged and collect continues."""
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter._client = MagicMock()

        async def fake_to_thread(fn, *args, **kwargs):
            raise Exception("some error")

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            items = [item async for item in adapter.collect([], ["@bad_handle"], "topic-1")]

        assert items == []

    @pytest.mark.asyncio
    async def test_login_required_raises_auth_error(self):
        """login_required exception → AdapterAuthError."""
        from anveshak.social.adapters.base import AdapterAuthError
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter._client = MagicMock()

        async def fake_to_thread(fn, *args, **kwargs):
            raise Exception("login_required")

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            with pytest.raises(AdapterAuthError):
                async for _ in adapter.collect([], ["@user"], "topic-1"):
                    pass

    @pytest.mark.asyncio
    async def test_rate_limit_raises_rate_limit_error(self):
        """Rate limit from Meta → AdapterRateLimitError."""
        from anveshak.social.adapters.base import AdapterRateLimitError
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter._client = MagicMock()

        async def fake_to_thread(fn, *args, **kwargs):
            raise Exception("rate limit exceeded 429")

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            with pytest.raises(AdapterRateLimitError):
                async for _ in adapter.collect([], ["@user"], "topic-1"):
                    pass

    @pytest.mark.asyncio
    async def test_rate_guard_blocks_when_exhausted(self):
        """Rate guard blocks further collection when hourly cap hit."""
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter._client = MagicMock()
        adapter._rate_guard = AsyncMock()
        adapter._rate_guard.check_and_increment = AsyncMock(return_value=False)

        items = [item async for item in adapter.collect([], ["@user"], "topic-1")]
        assert items == []

    @pytest.mark.asyncio
    async def test_empty_caption_posts_skipped(self):
        """Posts with empty captions are not yielded."""
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter._client = MagicMock()

        user_info = _mock_user_info(username="user", is_private=False, biography="")
        media = _mock_media(caption="", shortcode="EEE")

        call_count = 0

        async def fake_to_thread(fn, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return user_info
            return [media]

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            items = [item async for item in adapter.collect([], ["@user"], "topic-1")]

        # No bio (empty) and no post (empty caption)
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_hashtag_rate_limit_raises(self):
        """Rate limit during hashtag search → AdapterRateLimitError."""
        from anveshak.social.adapters.base import AdapterRateLimitError
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter._client = MagicMock()

        async def fake_to_thread(fn, *args, **kwargs):
            raise Exception("rate limit 429")

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            with pytest.raises(AdapterRateLimitError):
                async for _ in adapter.collect(["keyword"], [], "topic-1"):
                    pass

    @pytest.mark.asyncio
    async def test_hashtag_error_continues(self):
        """Non-rate-limit hashtag errors are logged, collection continues."""
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        adapter._client = MagicMock()

        async def fake_to_thread(fn, *args, **kwargs):
            raise Exception("some hashtag error")

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            items = [item async for item in adapter.collect(["keyword"], [], "topic-1")]

        assert items == []

    @pytest.mark.asyncio
    async def test_auth_failure_sets_client_none(self):
        """authenticate() failure → _client remains None."""
        from anveshak.social.adapters.base import AdapterAuthError
        from anveshak.social.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter()
        mock_client = MagicMock()
        mock_client.login = MagicMock(side_effect=Exception("blocked"))
        with patch("instagrapi.Client", return_value=mock_client):
            with patch("anveshak.social.adapters.instagram.settings") as mock_settings:
                mock_settings.instagram_adapter_enabled = True
                mock_settings.instagram_username = "user"
                mock_settings.instagram_password = "pass"
                mock_settings.instagram_session_path = ""
                with pytest.raises(AdapterAuthError):
                    await adapter.authenticate()
        assert adapter._client is None
