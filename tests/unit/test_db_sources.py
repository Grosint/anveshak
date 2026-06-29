"""Unit tests for services/api db/sources repository."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from datetime import datetime, UTC


@pytest.fixture
def mock_conn():
    return AsyncMock()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_sources_returns_tuple(mock_conn):
    from anveshak.api.db.sources import list_sources  # type: ignore[import]

    mock_conn.fetch.return_value = [
        {"id": "s1", "name": "NDTV", "platform": "web", "credibility_score": 75.0,
         "is_active": True, "last_checked_at": None, "total": 1}
    ]
    items, total = await list_sources(mock_conn)
    assert len(items) == 1
    assert items[0]["name"] == "NDTV"
    assert "total" not in items[0]
    assert total == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_source_score_returns_none_when_missing(mock_conn):
    from anveshak.api.db.sources import get_source_score  # type: ignore[import]

    mock_conn.fetchrow.return_value = None
    result = await get_source_score(mock_conn, "missing")
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_source_score_returns_float(mock_conn):
    from anveshak.api.db.sources import get_source_score  # type: ignore[import]

    mock_conn.fetchrow.return_value = {"credibility_score": 72.5}
    result = await get_source_score(mock_conn, "s1")
    assert result == 72.5


@pytest.mark.unit
@pytest.mark.asyncio
async def test_source_exists_true(mock_conn):
    from anveshak.api.db.sources import source_exists  # type: ignore[import]

    mock_conn.fetchrow.return_value = {"id": "s1"}
    assert await source_exists(mock_conn, "s1") is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_source_exists_false(mock_conn):
    from anveshak.api.db.sources import source_exists  # type: ignore[import]

    mock_conn.fetchrow.return_value = None
    assert await source_exists(mock_conn, "missing") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_credibility_calls_both_sqls(mock_conn):
    """update_credibility must write score update AND audit log (CLAUDE.md rule 8)."""
    from anveshak.api.db.sources import update_credibility  # type: ignore[import]

    now = datetime.now(UTC)
    await update_credibility(
        mock_conn, "s1", "audit-id", 75.0, 50.0,
        "deepfake amplification", "user:analyst1",
        now, '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}',
    )
    assert mock_conn.execute.await_count == 2
    calls = [c[0][0] for c in mock_conn.execute.call_args_list]
    assert any("UPDATE sources" in sql for sql in calls)
    assert any("INSERT INTO credibility_audit_log" in sql for sql in calls)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_count_report_warnings_returns_int(mock_conn):
    from anveshak.api.db.sources import count_report_warnings  # type: ignore[import]

    mock_conn.fetchval.return_value = 3
    result = await count_report_warnings(mock_conn, "s1")
    assert result == 3
    assert isinstance(result, int)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_count_report_warnings_handles_none(mock_conn):
    from anveshak.api.db.sources import count_report_warnings  # type: ignore[import]

    mock_conn.fetchval.return_value = None
    result = await count_report_warnings(mock_conn, "s1")
    assert result == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_audit_log_returns_list(mock_conn):
    from anveshak.api.db.sources import get_audit_log  # type: ignore[import]

    mock_conn.fetch.return_value = [
        {"id": "a1", "source_id": "s1", "old_score": 75.0, "new_score": 50.0,
         "reason": "test", "changed_by": "user:x", "created_at": datetime.now(UTC)}
    ]
    result = await get_audit_log(mock_conn, "s1")
    assert len(result) == 1
    assert result[0]["old_score"] == 75.0
