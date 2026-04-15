"""Unit tests for services/api db/reports repository."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from datetime import datetime, UTC


@pytest.fixture
def mock_conn():
    return AsyncMock()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_report_returns_none_when_missing(mock_conn):
    from anveshak.api.db.reports import fetch_report  # type: ignore[import]

    mock_conn.fetchrow.return_value = None
    result = await fetch_report(mock_conn, "missing")
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_report_returns_dict(mock_conn):
    from anveshak.api.db.reports import fetch_report  # type: ignore[import]

    now = datetime.now(UTC)
    mock_conn.fetchrow.return_value = {
        "id": "r1", "topic_id": "t1", "generated_at": now,
        "source_warnings": "[]",
    }
    result = await fetch_report(mock_conn, "r1")
    assert result["id"] == "r1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_insert_report_calls_execute(mock_conn):
    from anveshak.api.db.reports import insert_report  # type: ignore[import]

    now = datetime.now(UTC)
    await insert_report(
        mock_conn, "r1", "t1", "intelligence_brief",
        now, now, 30.0, now,
        '{"classification":"OPEN","domain":"report","owner_org":"anveshak"}',
    )
    mock_conn.execute.assert_awaited_once()
    assert "INSERT INTO reports" in mock_conn.execute.call_args[0][0]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_topic_reports_returns_list(mock_conn):
    from anveshak.api.db.reports import list_topic_reports  # type: ignore[import]

    now = datetime.now(UTC)
    mock_conn.fetch.return_value = [
        {"id": "r1", "topic_id": "t1", "report_type": "intelligence_brief",
         "generated_at": now, "confidence_score": 0.8,
         "content_item_count": 42, "created_at": now}
    ]
    result = await list_topic_reports(mock_conn, "t1")
    assert len(result) == 1
    assert result[0]["report_type"] == "intelligence_brief"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_report_geojson_returns_none_when_missing(mock_conn):
    from anveshak.api.db.reports import get_report_geojson  # type: ignore[import]

    mock_conn.fetchrow.return_value = None
    result = await get_report_geojson(mock_conn, "missing")
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_report_geojson_returns_dict(mock_conn):
    from anveshak.api.db.reports import get_report_geojson  # type: ignore[import]

    now = datetime.now(UTC)
    mock_conn.fetchrow.return_value = {
        "generated_at": now,
        "geojson": '{"type":"FeatureCollection","features":[]}',
    }
    result = await get_report_geojson(mock_conn, "r1")
    assert result["generated_at"] == now
