"""Unit tests for services/api db/signals repository."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from datetime import datetime, UTC


@pytest.fixture
def mock_conn():
    return AsyncMock()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_signals_returns_list(mock_conn):
    from anveshak.api.db.signals import list_signals  # type: ignore[import]

    now = datetime.now(UTC)

    # First call: list signals query; subsequent calls: enrichment queries
    mock_conn.fetch.side_effect = [
        # SQL_LIST_SIGNALS result
        [{"id": "sig1", "topic_id": "t1", "cluster_id": "c1",
         "signal_type": "threshold_breach", "status": "new", "created_at": now,
         "cluster_label": "Naval ops", "independent_source_count": 4,
         "cluster_item_count": 5, "topic_name": "Test Topic"}],
        # SQL_SIGNAL_SOURCES result (for enrichment)
        [{"source_name": "example.com", "platform": "web", "credibility_score": 75.0}],
    ]
    mock_conn.fetchrow.return_value = {"first_seen": now, "last_seen": now}

    result = await list_signals(mock_conn, "new")
    assert len(result) == 1
    assert result[0]["sources"][0]["source_name"] == "example.com"
    assert result[0]["first_seen"] is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_acknowledge_signal_returns_none_when_not_found(mock_conn):
    from anveshak.api.db.signals import acknowledge_signal  # type: ignore[import]

    mock_conn.fetchrow.return_value = None
    result = await acknowledge_signal(mock_conn, "sig1", datetime.now(UTC))
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_acknowledge_signal_returns_dict_when_found(mock_conn):
    from anveshak.api.db.signals import acknowledge_signal  # type: ignore[import]

    mock_conn.fetchrow.return_value = {"id": "sig1"}
    result = await acknowledge_signal(mock_conn, "sig1", datetime.now(UTC))
    assert result == {"id": "sig1"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dismiss_signal_returns_none_when_not_found(mock_conn):
    from anveshak.api.db.signals import dismiss_signal  # type: ignore[import]

    mock_conn.fetchrow.return_value = None
    result = await dismiss_signal(mock_conn, "sig1", datetime.now(UTC))
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_missed_signals_returns_list(mock_conn):
    from anveshak.api.db.signals import get_missed_signals  # type: ignore[import]

    now = datetime.now(UTC)
    mock_conn.fetch.return_value = [
        {"id": "sig1", "topic_id": "t1", "cluster_id": "c1",
         "signal_type": "threshold_breach", "status": "new", "created_at": now}
    ]
    result = await get_missed_signals(mock_conn, now)
    assert len(result) == 1
    assert result[0]["id"] == "sig1"
