"""Tests for get_topic_content dynamic SQL builder in services/api/anveshak/api/db/topics.py.

Validates parameter ordering, label parsing, and filter composition.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from services.api.anveshak.api.db.topics import (
    _DEFAULT_RELEVANCE_THRESHOLD,
    get_topic_content,
)

pytestmark = pytest.mark.unit

TOPIC_ID = "topic-001"


def _make_row(**overrides) -> dict:
    """Build a fake asyncpg Row (dict-like) with sensible defaults."""
    base = {
        "id": "ci-001",
        "url": "https://example.com/article",
        "title": "Test Article",
        "clean_text": "Some content here",
        "translated_text": None,
        "language": "en",
        "credibility_score_at_capture": 0.8,
        "captured_at": "2026-05-01T12:00:00",
        "source_name": "Example Source",
        "platform": "web",
        "backfilled": False,
        "duplicate_count": 1,
        "labels": json.dumps({"sentiment": {"compound": 0.5}, "keywords": ["osint", "defence"]}),
    }
    base.update(overrides)
    return base


# ---- Test 1: Basic call, no optional filters ----

@pytest.mark.unit
async def test_get_topic_content_basic(mock_conn: AsyncMock) -> None:
    """No filters: params should be $1=topic_id, $2=limit, $3=offset, $4=threshold."""
    row = _make_row()
    mock_conn.fetch = AsyncMock(return_value=[row])

    result = await get_topic_content(
        conn=mock_conn,
        topic_id=TOPIC_ID,
        limit=20,
        offset=0,
        has_embedding=None,
        platform=None,
    )

    # Verify the call was made with correct positional params
    call_args = mock_conn.fetch.call_args
    sql = call_args[0][0]
    params = call_args[0][1:]

    assert params == (TOPIC_ID, 20, 0, _DEFAULT_RELEVANCE_THRESHOLD)
    assert len(params) == 4
    # SQL should NOT contain platform filter
    assert "s.platform = $" not in sql or "s.platform = $4" not in sql
    assert len(result) == 1
    assert result[0]["sentiment"] == {"compound": 0.5}
    assert result[0]["keywords"] == ["osint", "defence"]


# ---- Test 2: Platform filter shifts threshold to $5 ----

@pytest.mark.unit
async def test_get_topic_content_with_platform(mock_conn: AsyncMock) -> None:
    """platform='web' -> $4=platform, $5=threshold (5 params total)."""
    mock_conn.fetch = AsyncMock(return_value=[_make_row()])

    await get_topic_content(
        conn=mock_conn,
        topic_id=TOPIC_ID,
        limit=10,
        offset=5,
        has_embedding=None,
        platform="web",
    )

    call_args = mock_conn.fetch.call_args
    sql = call_args[0][0]
    params = call_args[0][1:]

    assert len(params) == 5
    assert params == (TOPIC_ID, 10, 5, "web", _DEFAULT_RELEVANCE_THRESHOLD)
    # SQL must contain parameterized platform clause
    assert "s.platform = $4" in sql
    # Relevance threshold should use $5
    assert f"topic_relevance_score >= $5" in sql


# ---- Test 3: All filters together — param count and order ----

@pytest.mark.unit
async def test_get_topic_content_param_order_with_all_filters(mock_conn: AsyncMock) -> None:
    """platform + sentiment + has_embedding -> verify param count and SQL clauses."""
    mock_conn.fetch = AsyncMock(return_value=[])

    await get_topic_content(
        conn=mock_conn,
        topic_id=TOPIC_ID,
        limit=50,
        offset=10,
        has_embedding=True,
        platform="telegram",
        sentiment="negative",
    )

    call_args = mock_conn.fetch.call_args
    sql = call_args[0][0]
    params = call_args[0][1:]

    # platform adds $4, relevance adds $5; sentiment uses hardcoded float thresholds
    assert len(params) == 5
    assert params[3] == "telegram"  # $4 = platform
    assert params[4] == _DEFAULT_RELEVANCE_THRESHOLD  # $5 = threshold

    # Sentiment uses hardcoded floats in SQL, not parameterized
    assert "<= -0.05" in sql
    # Embedding filter is a static clause
    assert "ci.embedding IS NOT NULL" in sql


# ---- Test 4: Labels column returns JSON string -> parsed to dict ----

@pytest.mark.unit
async def test_get_topic_content_labels_as_string(mock_conn: AsyncMock) -> None:
    """When labels is a JSON string, it should be parsed and sentiment/keywords extracted."""
    labels_str = json.dumps({"sentiment": {"compound": -0.3}, "keywords": ["crisis"]})
    mock_conn.fetch = AsyncMock(return_value=[_make_row(labels=labels_str)])

    result = await get_topic_content(
        conn=mock_conn, topic_id=TOPIC_ID, limit=10, offset=0,
        has_embedding=None, platform=None,
    )

    assert result[0]["sentiment"] == {"compound": -0.3}
    assert result[0]["keywords"] == ["crisis"]
    # labels key should NOT be in the final dict (it's popped)
    assert "labels" not in result[0]


# ---- Test 5: Labels column returns dict directly ----

@pytest.mark.unit
async def test_get_topic_content_labels_as_dict(mock_conn: AsyncMock) -> None:
    """When asyncpg returns labels as a dict (jsonb), no JSON parsing needed."""
    labels_dict = {"sentiment": {"compound": 0.9}, "keywords": ["victory", "success"]}
    mock_conn.fetch = AsyncMock(return_value=[_make_row(labels=labels_dict)])

    result = await get_topic_content(
        conn=mock_conn, topic_id=TOPIC_ID, limit=10, offset=0,
        has_embedding=None, platform=None,
    )

    assert result[0]["sentiment"] == {"compound": 0.9}
    assert result[0]["keywords"] == ["victory", "success"]


# ---- Test 6: Labels is None -> sentiment=None, keywords=[] ----

@pytest.mark.unit
async def test_get_topic_content_labels_null(mock_conn: AsyncMock) -> None:
    """Null labels -> sentiment is None, keywords is empty list."""
    mock_conn.fetch = AsyncMock(return_value=[_make_row(labels=None)])

    result = await get_topic_content(
        conn=mock_conn, topic_id=TOPIC_ID, limit=10, offset=0,
        has_embedding=None, platform=None,
    )

    assert result[0]["sentiment"] is None
    assert result[0]["keywords"] == []


# ---- Test 7: Custom relevance threshold overrides default ----

@pytest.mark.unit
async def test_get_topic_content_custom_relevance_threshold(mock_conn: AsyncMock) -> None:
    """Override default threshold (0.42) with 0.75 — verify it's passed as param."""
    mock_conn.fetch = AsyncMock(return_value=[])

    await get_topic_content(
        conn=mock_conn, topic_id=TOPIC_ID, limit=10, offset=0,
        has_embedding=None, platform=None,
        relevance_threshold=0.75,
    )

    call_args = mock_conn.fetch.call_args
    params = call_args[0][1:]

    # $4 should be 0.75, not the default 0.42
    assert params[3] == 0.75
    assert params[3] != _DEFAULT_RELEVANCE_THRESHOLD
