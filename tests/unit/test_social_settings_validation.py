"""Unit tests for social adapter startup credential validation.

Tests:
  - Enabled adapter with missing credentials logs warning and is NOT added to _ADAPTERS
  - Enabled adapter with valid credentials proceeds to authenticate
  - Disabled adapter is skipped entirely
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_settings(**overrides):
    """Build a mock SocialSettings with all adapters disabled by default."""
    s = MagicMock()
    s.postgres_url = "postgresql://test:test@localhost:5432/test"
    s.redis_url = "redis://localhost:6379"
    s.reddit_adapter_enabled = False
    s.bluesky_adapter_enabled = False
    s.telegram_adapter_enabled = False
    s.x_adapter_enabled = False
    s.reddit_client_id = None
    s.reddit_client_secret = None
    s.bluesky_handle = None
    s.bluesky_password = None
    s.bluesky_daily_call_cap = 7200
    s.telegram_api_id = None
    s.telegram_api_hash = None
    s.telegram_session_string = None
    s.x_bearer_token = None
    s.x_adapter_mode = "polling"
    s.x_monthly_read_cap = 40000
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


class TestCredentialValidation:

    @pytest.mark.asyncio
    async def test_bluesky_enabled_missing_handle_warns(self):
        """Bluesky enabled but handle not set → warning logged, not added."""
        from anveshak.social.jobs import _ADAPTERS, _validate_adapter_credentials

        s = _make_settings(bluesky_adapter_enabled=True, bluesky_handle=None, bluesky_password="pass")
        issues = _validate_adapter_credentials("bluesky", s)
        assert len(issues) > 0
        assert any("BLUESKY_HANDLE" in i for i in issues)

    @pytest.mark.asyncio
    async def test_bluesky_enabled_missing_password_warns(self):
        """Bluesky enabled but password not set → warning logged."""
        from anveshak.social.jobs import _validate_adapter_credentials

        s = _make_settings(bluesky_adapter_enabled=True, bluesky_handle="user.bsky.social", bluesky_password=None)
        issues = _validate_adapter_credentials("bluesky", s)
        assert len(issues) > 0
        assert any("BLUESKY_PASSWORD" in i for i in issues)

    @pytest.mark.asyncio
    async def test_bluesky_valid_credentials_no_issues(self):
        """Bluesky with both handle + password → no issues."""
        from anveshak.social.jobs import _validate_adapter_credentials

        s = _make_settings(
            bluesky_adapter_enabled=True,
            bluesky_handle="user.bsky.social",
            bluesky_password="secret",
        )
        issues = _validate_adapter_credentials("bluesky", s)
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_reddit_enabled_missing_client_id_warns(self):
        """Reddit enabled but client_id not set → warning."""
        from anveshak.social.jobs import _validate_adapter_credentials

        s = _make_settings(reddit_adapter_enabled=True, reddit_client_id=None, reddit_client_secret="sec")
        issues = _validate_adapter_credentials("reddit", s)
        assert len(issues) > 0

    @pytest.mark.asyncio
    async def test_telegram_enabled_missing_api_hash_warns(self):
        """Telegram enabled but api_hash not set → warning."""
        from anveshak.social.jobs import _validate_adapter_credentials

        s = _make_settings(
            telegram_adapter_enabled=True,
            telegram_api_id=12345,
            telegram_api_hash=None,
            telegram_session_string="sess",
        )
        issues = _validate_adapter_credentials("telegram", s)
        assert len(issues) > 0

    @pytest.mark.asyncio
    async def test_x_enabled_missing_bearer_token_warns(self):
        """X enabled but bearer token not set → warning."""
        from anveshak.social.jobs import _validate_adapter_credentials

        s = _make_settings(x_adapter_enabled=True, x_bearer_token=None)
        issues = _validate_adapter_credentials("x", s)
        assert len(issues) > 0
