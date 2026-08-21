"""Unit tests for Telegram forwarding chain discovery."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# asyncio_mode = "auto" in pyproject.toml already marks the async tests here.
# An explicit asyncio mark also lands on the sync ones and emits a PytestWarning.
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# RawItem forwarding fields
# ---------------------------------------------------------------------------


def test_raw_item_has_forwarding_fields():
    """RawItem must have optional forwarded_from_channel_id and forwarded_from_channel_name."""
    from datetime import UTC, datetime

    from anveshak.social.adapters.base import RawItem

    # Without forwarding (default)
    item = RawItem(
        raw_text="test",
        url="https://t.me/channel/1",
        platform="telegram",
        captured_at=datetime.now(UTC),
        source_handle="@channel",
    )
    assert item.forwarded_from_channel_id is None
    assert item.forwarded_from_channel_name is None

    # With forwarding
    item_fwd = RawItem(
        raw_text="forwarded message",
        url="https://t.me/channel/2",
        platform="telegram",
        captured_at=datetime.now(UTC),
        source_handle="@channel",
        forwarded_from_channel_id="@origin_channel",
        forwarded_from_channel_name="Origin Channel",
    )
    assert item_fwd.forwarded_from_channel_id == "@origin_channel"
    assert item_fwd.forwarded_from_channel_name == "Origin Channel"


# ---------------------------------------------------------------------------
# Telegram forwarding discovery job
# ---------------------------------------------------------------------------


async def test_discover_telegram_channels_upserts():
    """discover_telegram_channels aggregates forwarding data and upserts."""
    from anveshak.analyst.discovery import discover_telegram_channels

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_conn.fetch = AsyncMock(
        side_effect=[
            # SQL_FORWARDING_AGGREGATION results
            [
                {
                    "forwarded_from_channel_id": "origin1",
                    "forwarded_from_channel_name": "Origin One",
                    "forward_count": 12,
                },
                {
                    "forwarded_from_channel_id": "origin2",
                    "forwarded_from_channel_name": "Origin Two",
                    "forward_count": 5,
                },
            ],
            # SQL_EXISTING_SOURCE_URLS
            [],
        ]
    )
    mock_conn.execute = AsyncMock()

    count = await discover_telegram_channels(mock_pool, "topic-1")
    assert count == 2
    assert mock_conn.execute.call_count == 2


async def test_discover_telegram_skips_registered():
    """discover_telegram_channels skips already-registered channels."""
    from anveshak.analyst.discovery import discover_telegram_channels

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "forwarded_from_channel_id": "registered_channel",
                    "forwarded_from_channel_name": "Already There",
                    "forward_count": 20,
                },
            ],
            # Already registered
            [{"url_or_handle": "@registered_channel"}],
        ]
    )
    mock_conn.execute = AsyncMock()

    count = await discover_telegram_channels(mock_pool, "topic-1")
    assert count == 0


async def test_discover_telegram_no_forwards():
    """discover_telegram_channels returns 0 if no forwarding data."""
    from anveshak.analyst.discovery import discover_telegram_channels

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_conn.fetch = AsyncMock(return_value=[])

    count = await discover_telegram_channels(mock_pool, "topic-1")
    assert count == 0
