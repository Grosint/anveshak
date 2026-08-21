"""Unit tests for entity-based source discovery (Level 3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def test_discover_entity_sources_upserts():
    """discover_entity_sources extracts top entities and upserts suggestions."""
    from anveshak.analyst.discovery import discover_entity_sources

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_conn.fetch = AsyncMock(
        side_effect=[
            # SQL_TOP_ENTITIES
            [
                {"entity_text": "Rashid K", "entity_type": "PERSON", "mention_count": 15},
                {"entity_text": "Barmer", "entity_type": "GPE", "mention_count": 10},
            ],
            # SQL_EXISTING_SOURCE_URLS
            [],
        ]
    )
    mock_conn.execute = AsyncMock()

    count = await discover_entity_sources(mock_pool, "topic-1", top_n_entities=5)
    assert count == 2
    assert mock_conn.execute.call_count == 2


async def test_discover_entity_sources_skips_existing():
    """discover_entity_sources skips entities with existing source handles."""
    from anveshak.analyst.discovery import discover_entity_sources

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_conn.fetch = AsyncMock(
        side_effect=[
            [
                {"entity_text": "Known Entity", "entity_type": "ORG", "mention_count": 20},
            ],
            [{"url_or_handle": "search:Known Entity"}],
        ]
    )
    mock_conn.execute = AsyncMock()

    count = await discover_entity_sources(mock_pool, "topic-1")
    assert count == 0


async def test_discover_entity_sources_no_entities():
    """discover_entity_sources returns 0 with no entities."""
    from anveshak.analyst.discovery import discover_entity_sources

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_conn.fetch = AsyncMock(return_value=[])

    count = await discover_entity_sources(mock_pool, "topic-1")
    assert count == 0
