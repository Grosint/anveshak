"""Unit tests for services/api db/topics repository."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, UTC


@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    return conn


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_topics_returns_dicts(mock_conn):
    from anveshak.api.db.topics import list_topics  # type: ignore[import]

    fake_row = MagicMock()
    fake_row.keys.return_value = ["id", "name", "status"]
    fake_row.__iter__ = MagicMock(return_value=iter([("id", "t1"), ("name", "Test"), ("status", "active")]))
    # asyncpg records support dict() via __iter__ over key-value pairs
    mock_conn.fetch.return_value = [{"id": "t1", "name": "Test", "status": "active"}]

    # Patch dict(row) behaviour — mock fetch returns plain dicts
    result = await list_topics(mock_conn)

    mock_conn.fetch.assert_awaited_once()
    assert isinstance(result, list)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_topic_returns_none_when_missing(mock_conn):
    from anveshak.api.db.topics import get_topic  # type: ignore[import]

    mock_conn.fetchrow.return_value = None
    result = await get_topic(mock_conn, "nonexistent-id")
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_topic_returns_dict_when_found(mock_conn):
    from anveshak.api.db.topics import get_topic  # type: ignore[import]

    mock_conn.fetchrow.return_value = {"id": "t1", "name": "Test", "status": "active"}
    result = await get_topic(mock_conn, "t1")
    assert result == {"id": "t1", "name": "Test", "status": "active"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_topic_exists_true(mock_conn):
    from anveshak.api.db.topics import topic_exists  # type: ignore[import]

    mock_conn.fetchrow.return_value = {"id": "t1"}
    assert await topic_exists(mock_conn, "t1") is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_topic_exists_false(mock_conn):
    from anveshak.api.db.topics import topic_exists  # type: ignore[import]

    mock_conn.fetchrow.return_value = None
    assert await topic_exists(mock_conn, "missing") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_insert_topic_calls_execute(mock_conn):
    from anveshak.api.db.topics import insert_topic  # type: ignore[import]

    now = datetime.now(UTC)
    await insert_topic(
        mock_conn, "t1", "Test", ["kw1"], ["en"],
        30.0, 3, [], None, None, now,
        '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}',
    )
    mock_conn.execute.assert_awaited_once()
    call_sql = mock_conn.execute.call_args[0][0]
    assert "INSERT INTO topics" in call_sql


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_topic_status_calls_execute(mock_conn):
    from anveshak.api.db.topics import update_topic_status  # type: ignore[import]

    now = datetime.now(UTC)
    await update_topic_status(mock_conn, "t1", "paused", now)
    mock_conn.execute.assert_awaited_once()
    call_args = mock_conn.execute.call_args[0]
    assert "UPDATE topics" in call_args[0]
    assert call_args[1] == "paused"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_topic_entities_returns_list(mock_conn):
    from anveshak.api.db.topics import get_topic_entities  # type: ignore[import]

    mock_conn.fetch.return_value = [
        {"entity_type": "ORG", "entity_text": "IAF", "mention_count": 5, "avg_confidence": 0.9}
    ]
    result = await get_topic_entities(mock_conn, "t1")
    assert len(result) == 1
    assert result[0]["entity_type"] == "ORG"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_topic_clusters_returns_list(mock_conn):
    from anveshak.api.db.topics import get_topic_clusters  # type: ignore[import]

    mock_conn.fetch.side_effect = [
        # First call: SQL_GET_TOPIC_CLUSTERS → cluster rows
        [{"id": "c1", "label": "Naval ops", "item_count": 10, "independent_source_count": 3}],
        # Second call: SQL_CLUSTER_SOURCES for cluster "c1" → source rows
        [{"source_name": "reuters.com", "platform": "web", "credibility_score": 72.0}],
    ]
    result = await get_topic_clusters(mock_conn, "t1")
    assert len(result) == 1
    assert result[0]["label"] == "Naval ops"
    assert result[0]["sources"][0]["source_name"] == "reuters.com"
