"""Unit tests for social adapter credential refresh mechanism.

When an adapter encounters AdapterAuthError during collect(), the system
should attempt refresh_credentials() once before recording a circuit breaker failure.

pytest.mark.unit — no external dependencies.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestRefreshCredentials:
    """Test the refresh_credentials() method on SourceAdapterBase."""

    @pytest.mark.asyncio
    async def test_base_class_has_refresh_method(self):
        """SourceAdapterBase must define refresh_credentials()."""
        from anveshak.social.adapters.base import SourceAdapterBase
        assert hasattr(SourceAdapterBase, "refresh_credentials")

    @pytest.mark.asyncio
    async def test_default_refresh_returns_false(self):
        """Default implementation returns False (no refresh possible)."""
        from anveshak.social.adapters.base import SourceAdapterBase

        class DummyAdapter(SourceAdapterBase):
            adapter_id = "dummy-v1"
            platform = "dummy"
            adapter_version = "1.0.0"
            async def authenticate(self): pass
            async def collect(self, kw, sh, tid): return; yield
            async def health(self): return {"status": "HEALTHY"}

        adapter = DummyAdapter()
        result = await adapter.refresh_credentials()
        assert result is False

    @pytest.mark.asyncio
    async def test_bluesky_refresh_re_authenticates(self):
        """BlueskyAdapter.refresh_credentials() calls authenticate() again."""
        from anveshak.social.adapters.bluesky import BlueskyAdapter

        adapter = BlueskyAdapter()
        with patch.object(adapter, "authenticate", new_callable=AsyncMock) as mock_auth:
            result = await adapter.refresh_credentials()
            mock_auth.assert_awaited_once()
            assert result is True

    @pytest.mark.asyncio
    async def test_bluesky_refresh_returns_false_on_auth_failure(self):
        """If re-authentication fails, refresh_credentials returns False."""
        from anveshak.social.adapters.bluesky import BlueskyAdapter
        from anveshak.social.adapters.base import AdapterAuthError

        adapter = BlueskyAdapter()
        with patch.object(
            adapter, "authenticate",
            new_callable=AsyncMock,
            side_effect=AdapterAuthError("bad creds"),
        ):
            result = await adapter.refresh_credentials()
            assert result is False


class TestRefreshInPollLoop:
    """Test that poll_social_topic attempts refresh on AdapterAuthError."""

    @pytest.mark.asyncio
    async def test_auth_error_triggers_refresh(self):
        """AdapterAuthError during collect → refresh_credentials called."""
        from anveshak.social.adapters.base import AdapterAuthError, SourceAdapterBase

        class FailingAdapter(SourceAdapterBase):
            adapter_id = "failing-v1"
            platform = "failing"
            adapter_version = "1.0.0"
            async def authenticate(self): pass
            async def collect(self, kw, sh, tid):
                raise AdapterAuthError("token expired")
                yield  # noqa
            async def health(self): return {"status": "DOWN"}

        adapter = FailingAdapter()
        adapter.refresh_credentials = AsyncMock(return_value=True)

        # Simulate what poll_social_topic does on auth error
        from anveshak.social.adapters.base import AdapterAuthError
        try:
            async for _ in adapter.collect(["test"], [], "topic-1"):
                pass
        except AdapterAuthError:
            refreshed = await adapter.refresh_credentials()
            assert refreshed is True
            adapter.refresh_credentials.assert_awaited_once()
