"""Unit tests for Telegram session expiry handling — HIGH-12.

SessionExpiredError during _iter_channel must be caught and logged,
not crash the entire collect() loop.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

pytestmark = pytest.mark.unit


class TestTelegramSessionExpiry:

    @pytest.mark.asyncio
    async def test_session_expired_during_iteration_is_caught(self):
        """SessionExpiredError mid-channel must not propagate — log and continue."""
        from telethon.errors import SessionExpiredError
        from anveshak.social.adapters.telegram import TelegramAdapter

        adapter = TelegramAdapter.__new__(TelegramAdapter)
        adapter._client = MagicMock()

        # iter_messages raises SessionExpiredError
        async def _raise_session_expired(*args, **kwargs):
            raise SessionExpiredError(MagicMock())
            yield  # make it an async generator

        adapter._client.iter_messages = _raise_session_expired

        # Should NOT raise — must be caught inside _iter_channel
        items = []
        async for item in adapter._iter_channel("@test_channel", "test", "topic-1"):
            items.append(item)

        assert items == []  # no items, but no crash

    @pytest.mark.asyncio
    async def test_session_expired_sets_needs_reauth_flag(self):
        """After SessionExpiredError, adapter should flag need for re-authentication."""
        from telethon.errors import SessionExpiredError
        from anveshak.social.adapters.telegram import TelegramAdapter

        adapter = TelegramAdapter.__new__(TelegramAdapter)
        adapter._client = MagicMock()
        adapter._needs_reauth = False

        async def _raise_session_expired(*args, **kwargs):
            raise SessionExpiredError(MagicMock())
            yield

        adapter._client.iter_messages = _raise_session_expired

        async for _ in adapter._iter_channel("@test_channel", "test", "topic-1"):
            pass

        assert adapter._needs_reauth is True, (
            "After SessionExpiredError, _needs_reauth must be True"
        )
