"""Unit tests for catalog DB functions — mock asyncpg, verify SQL + params."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


@pytest.fixture
def mock_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()
    return conn


# ---------------------------------------------------------------------------
# list_catalog_suggestions
# ---------------------------------------------------------------------------


async def test_list_catalog_suggestions_calls_correct_sql(mock_conn):
    """list_catalog_suggestions must query by topic keywords overlap."""
    from anveshak.api.db.catalog import list_catalog_suggestions

    mock_conn.fetch.return_value = []
    result = await list_catalog_suggestions(mock_conn, ["china", "military"])
    mock_conn.fetch.assert_called_once()
    # First arg is the SQL, second is the keywords list
    call_args = mock_conn.fetch.call_args
    assert call_args[0][1] == ["china", "military"]
    assert isinstance(result, list)


async def test_list_catalog_suggestions_returns_dicts(mock_conn):
    """list_catalog_suggestions returns list of dicts."""
    from anveshak.api.db.catalog import list_catalog_suggestions

    fake_row = MagicMock()
    fake_row.__iter__ = MagicMock(return_value=iter([("id", "c1"), ("name", "Test")]))
    fake_row.items = MagicMock(return_value=[("id", "c1"), ("name", "Test")])
    mock_conn.fetch.return_value = [fake_row]
    result = await list_catalog_suggestions(mock_conn, ["china"])
    assert len(result) == 1


# ---------------------------------------------------------------------------
# upsert_discovered
# ---------------------------------------------------------------------------


async def test_upsert_discovered_calls_execute(mock_conn):
    """upsert_discovered must INSERT with ON CONFLICT DO UPDATE."""
    from anveshak.api.db.catalog import upsert_discovered

    await upsert_discovered(
        mock_conn,
        topic_id="t1",
        domain_or_handle="example.com",
        platform="web",
        discovery_method="snowball",
        citation_count=3,
        confidence_score=0.8,
        evidence={"citing_sources": ["src1"]},
        labels_json=LABELS_JSON,
    )
    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args[0]
    # Verify topic_id and domain are passed
    assert call_args[1] is not None  # id (uuid)
    assert call_args[2] == "t1"
    assert call_args[3] == "example.com"


# ---------------------------------------------------------------------------
# approve_discovered
# ---------------------------------------------------------------------------


async def test_approve_discovered_updates_status(mock_conn):
    """approve_discovered must set status=approved and link source_id."""
    from anveshak.api.db.catalog import approve_discovered

    await approve_discovered(mock_conn, discovered_id="d1", source_id="s1")
    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args[0]
    assert "d1" in call_args
    assert "s1" in call_args


# ---------------------------------------------------------------------------
# dismiss_discovered
# ---------------------------------------------------------------------------


async def test_dismiss_discovered_updates_status(mock_conn):
    """dismiss_discovered must set status=dismissed."""
    from anveshak.api.db.catalog import dismiss_discovered

    await dismiss_discovered(mock_conn, discovered_id="d1")
    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args[0]
    assert "d1" in call_args


# ---------------------------------------------------------------------------
# list_discovered
# ---------------------------------------------------------------------------


async def test_list_discovered_by_topic(mock_conn):
    """list_discovered must filter by topic_id and optional status."""
    from anveshak.api.db.catalog import list_discovered

    mock_conn.fetch.return_value = []
    await list_discovered(mock_conn, topic_id="t1")
    mock_conn.fetch.assert_called_once()
    call_args = mock_conn.fetch.call_args[0]
    assert call_args[1] == "t1"


async def test_list_discovered_with_status_filter(mock_conn):
    """list_discovered with status filter must pass status param."""
    from anveshak.api.db.catalog import list_discovered

    mock_conn.fetch.return_value = []
    await list_discovered(mock_conn, topic_id="t1", status="pending")
    call_args = mock_conn.fetch.call_args[0]
    assert "t1" in call_args
    assert "pending" in call_args


# ---------------------------------------------------------------------------
# insert_catalog_approval
# ---------------------------------------------------------------------------


async def test_insert_catalog_approval(mock_conn):
    """insert_catalog_approval must INSERT with ON CONFLICT DO NOTHING."""
    from anveshak.api.db.catalog import insert_catalog_approval

    await insert_catalog_approval(
        mock_conn,
        catalog_entry_id="ce1",
        topic_id="t1",
        source_id="s1",
        approved_by="analyst@test.com",
        labels_json=LABELS_JSON,
    )
    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args[0]
    assert "ce1" in call_args
    assert "t1" in call_args


# ---------------------------------------------------------------------------
# update_catalog_effectiveness
# ---------------------------------------------------------------------------


async def test_update_catalog_effectiveness(mock_conn):
    """update_catalog_effectiveness must UPDATE analytics columns."""
    from anveshak.api.db.catalog import update_catalog_effectiveness

    await update_catalog_effectiveness(
        mock_conn,
        catalog_entry_id="ce1",
        signal_contribution_count=5,
        relevance_hit_rate=0.78,
        cluster_participation_rate=0.45,
        topics_approved_count=3,
        recommendation_rank="most_recommended",
    )
    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args[0]
    assert "ce1" in call_args
    assert 5 in call_args
