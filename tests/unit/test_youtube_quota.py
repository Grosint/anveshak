"""Tests for YouTube quota guard — daily Redis atomic counter."""
import hashlib
import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestYouTubeQuotaGuardLua:
    """Test Lua script logic and daily key generation."""

    def test_daily_key_format(self):
        from anveshak.social.adapters.youtube_adapter import _daily_quota_key
        key = _daily_quota_key()
        assert key.startswith("anveshak:youtube:daily_quota:")
        # Should contain today's date in YYYY-MM-DD format
        date_part = key.split(":")[-1]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_part)

    def test_seconds_until_day_end_positive(self):
        from anveshak.social.adapters.youtube_adapter import _seconds_until_day_end
        secs = _seconds_until_day_end()
        assert 0 < secs <= 86400

    def test_lua_script_exists(self):
        from anveshak.social.adapters.youtube_adapter import YouTubeQuotaGuard
        assert hasattr(YouTubeQuotaGuard, "_LUA_CHECK_AND_INCREMENT")
        lua = YouTubeQuotaGuard._LUA_CHECK_AND_INCREMENT
        assert "INCR" in lua
        assert "EXPIRE" in lua
        assert "DECR" in lua


class TestYouTubeQuotaGuardBehavior:
    """Test guard check_and_increment with mocked Redis."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        return redis

    @pytest.fixture
    def guard(self, mock_redis):
        from anveshak.social.adapters.youtube_adapter import YouTubeQuotaGuard
        return YouTubeQuotaGuard(redis=mock_redis, cap=9000)

    @pytest.mark.asyncio
    async def test_under_cap_returns_true(self, guard, mock_redis):
        mock_redis.eval.return_value = 100  # new count
        result = await guard.check_and_increment(units=1)
        assert result is True

    @pytest.mark.asyncio
    async def test_at_cap_returns_false(self, guard, mock_redis):
        mock_redis.eval.return_value = -1  # blocked
        result = await guard.check_and_increment(units=100)
        assert result is False

    @pytest.mark.asyncio
    async def test_variable_cost_passed_to_lua(self, guard, mock_redis):
        mock_redis.eval.return_value = 500
        await guard.check_and_increment(units=100)
        # Verify units passed as ARGV[3]
        call_args = mock_redis.eval.call_args
        assert 100 in call_args[0] or 100 in (call_args[1].values() if call_args[1] else [])

    @pytest.mark.asyncio
    async def test_current_count_reads_without_increment(self, guard, mock_redis):
        mock_redis.get.return_value = b"4500"
        count = await guard.current_count()
        assert count == 4500
        mock_redis.eval.assert_not_called()

    @pytest.mark.asyncio
    async def test_current_count_returns_zero_when_no_key(self, guard, mock_redis):
        mock_redis.get.return_value = None
        count = await guard.current_count()
        assert count == 0


class TestYouTubeContentHash:
    """Test content_hash strategy for YouTube items."""

    def test_video_content_hash_uses_video_id(self):
        from anveshak.social.adapters.youtube_adapter import youtube_video_hash
        h = youtube_video_hash("dQw4w9WgXcQ")
        expected = hashlib.sha256("youtube:video:dQw4w9WgXcQ".encode()).hexdigest()
        assert h == expected

    def test_video_content_hash_deterministic(self):
        from anveshak.social.adapters.youtube_adapter import youtube_video_hash
        h1 = youtube_video_hash("abc123")
        h2 = youtube_video_hash("abc123")
        assert h1 == h2

    def test_comment_content_hash_uses_comment_id(self):
        from anveshak.social.adapters.youtube_adapter import youtube_comment_hash
        h = youtube_comment_hash("Ugx1234abcd")
        expected = hashlib.sha256("youtube:comment:Ugx1234abcd".encode()).hexdigest()
        assert h == expected


class TestYouTubeCaptionCleaning:
    """Test caption noise removal."""

    def test_strips_music_tag(self):
        from anveshak.social.adapters.youtube_adapter import clean_caption
        assert clean_caption("[Music] Hello world") == "Hello world"

    def test_strips_applause_tag(self):
        from anveshak.social.adapters.youtube_adapter import clean_caption
        assert clean_caption("[Applause] Thank you") == "Thank you"

    def test_strips_silence_tag(self):
        from anveshak.social.adapters.youtube_adapter import clean_caption
        assert "silence" not in clean_caption("[Silence] Next topic").lower()

    def test_strips_musical_notes(self):
        from anveshak.social.adapters.youtube_adapter import clean_caption
        result = clean_caption("♪ Some song lyrics ♪ Now talking")
        assert "♪" not in result

    def test_preserves_normal_text(self):
        from anveshak.social.adapters.youtube_adapter import clean_caption
        text = "This is a normal sentence about politics"
        assert clean_caption(text) == text

    def test_strips_multiple_tags(self):
        from anveshak.social.adapters.youtube_adapter import clean_caption
        text = "[Music] Hello [Applause] world [Laughter]"
        result = clean_caption(text)
        assert "Music" not in result
        assert "Applause" not in result
        assert "Laughter" not in result
        assert "Hello" in result
        assert "world" in result


class TestYouTubeChannelNormalization:
    """Test channel URL normalization."""

    def test_at_handle(self):
        from anveshak.social.adapters.youtube_adapter import normalize_channel_input
        result = normalize_channel_input("@MrBeast")
        assert result == ("handle", "MrBeast")

    def test_channel_id_url(self):
        from anveshak.social.adapters.youtube_adapter import normalize_channel_input
        result = normalize_channel_input("https://www.youtube.com/channel/UCX6OQ3DkcsbYNE6H8uQQuVA")
        assert result == ("channel_id", "UCX6OQ3DkcsbYNE6H8uQQuVA")

    def test_c_name_url(self):
        from anveshak.social.adapters.youtube_adapter import normalize_channel_input
        result = normalize_channel_input("https://www.youtube.com/c/MrBeast")
        assert result == ("custom", "MrBeast")

    def test_user_url(self):
        from anveshak.social.adapters.youtube_adapter import normalize_channel_input
        result = normalize_channel_input("https://www.youtube.com/user/PewDiePie")
        assert result == ("user", "PewDiePie")

    def test_at_handle_url(self):
        from anveshak.social.adapters.youtube_adapter import normalize_channel_input
        result = normalize_channel_input("https://www.youtube.com/@MrBeast")
        assert result == ("handle", "MrBeast")

    def test_bare_channel_id(self):
        from anveshak.social.adapters.youtube_adapter import normalize_channel_input
        result = normalize_channel_input("UCX6OQ3DkcsbYNE6H8uQQuVA")
        assert result == ("channel_id", "UCX6OQ3DkcsbYNE6H8uQQuVA")

    def test_bare_handle_without_at(self):
        from anveshak.social.adapters.youtube_adapter import normalize_channel_input
        result = normalize_channel_input("MrBeast")
        assert result == ("handle", "MrBeast")


class TestYouTubeAdapterContract:
    """Test adapter follows SourceAdapterBase contract."""

    def test_adapter_has_required_class_attrs(self):
        from anveshak.social.adapters.youtube_adapter import YouTubeAdapter
        assert YouTubeAdapter.adapter_id == "youtube-v1"
        assert YouTubeAdapter.platform == "youtube"
        assert YouTubeAdapter.adapter_version == "1.0.0"

    def test_adapter_extends_base(self):
        from anveshak.social.adapters.youtube_adapter import YouTubeAdapter
        from anveshak.social.adapters.base import SourceAdapterBase
        assert issubclass(YouTubeAdapter, SourceAdapterBase)


class TestYouTubeSettings:
    """Test YouTube settings exist in SocialSettings."""

    def test_youtube_settings_exist(self):
        from anveshak.social.settings import SocialSettings
        s = SocialSettings()
        assert hasattr(s, "youtube_api_key")
        assert hasattr(s, "youtube_adapter_enabled")
        assert hasattr(s, "youtube_daily_quota_cap")
        assert hasattr(s, "youtube_poll_interval_s")
        assert hasattr(s, "youtube_fetch_comments")
        assert hasattr(s, "youtube_max_comments_per_video")
        assert hasattr(s, "youtube_backfill_count")

    def test_youtube_defaults(self):
        from anveshak.social.settings import SocialSettings
        s = SocialSettings()
        assert s.youtube_adapter_enabled is False
        assert s.youtube_daily_quota_cap == 9000
        assert s.youtube_poll_interval_s == 900
        assert s.youtube_fetch_comments is True
        assert s.youtube_max_comments_per_video == 100
        assert s.youtube_backfill_count == 50


class TestYouTubeAdapterRegistration:
    """Test adapter is registered in jobs.py startup."""

    def test_youtube_in_required_credentials(self):
        from anveshak.social.jobs import _REQUIRED_CREDENTIALS
        assert "youtube" in _REQUIRED_CREDENTIALS
        creds = _REQUIRED_CREDENTIALS["youtube"]
        env_names = [env for _, env in creds]
        assert "YOUTUBE_API_KEY" in env_names

    def test_youtube_adapter_in_startup_source(self):
        import inspect
        from anveshak.social import jobs
        source = inspect.getsource(jobs.startup)
        assert "youtube_adapter_enabled" in source
        assert "YouTubeAdapter" in source
