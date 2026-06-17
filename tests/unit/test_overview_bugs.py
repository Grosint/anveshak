"""Tests for topic overview dashboard bugs.

Bug 1: GET /topics/{id} must return content_count and signal_count.
Bug 2: SQL_INSERT_IDENTIFIER_CLUSTER_ITEM must match table schema (no 'id', no 'labels').
Bug 3: Audit trail must be accessible to analysts when filtered by resource_id.

pytest.mark.unit — no external dependencies.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _FakeRecord(dict):
    """Mimics asyncpg.Record: dict() conversion works, supports keys()/items()."""
    pass


def asyncpg_record(data: dict) -> _FakeRecord:
    return _FakeRecord(data)


# ---------------------------------------------------------------------------
# Bug 1: Content count missing from GET topic detail
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetTopicIncludesContentCount:
    """SQL_GET_TOPIC must compute content_count from both content paths."""

    def test_sql_get_topic_has_content_count(self):
        from anveshak.api.db.topics import SQL_GET_TOPIC
        sql_lower = SQL_GET_TOPIC.lower()
        assert "content_count" in sql_lower, \
            "SQL_GET_TOPIC must include content_count computed column"

    def test_sql_get_topic_unions_both_content_paths(self):
        from anveshak.api.db.topics import SQL_GET_TOPIC
        sql_lower = SQL_GET_TOPIC.lower()
        assert "content_items" in sql_lower, \
            "SQL_GET_TOPIC must query content_items table"
        assert "topic_content_items" in sql_lower, \
            "SQL_GET_TOPIC must query topic_content_items join table"

    def test_sql_get_topic_has_signal_count(self):
        from anveshak.api.db.topics import SQL_GET_TOPIC
        sql_lower = SQL_GET_TOPIC.lower()
        assert "signal_count" in sql_lower, \
            "SQL_GET_TOPIC must include signal_count computed column"

    @pytest.mark.asyncio
    async def test_get_topic_returns_content_count(self):
        """get_topic() result must include content_count key."""
        from anveshak.api.db.topics import get_topic

        fake_row = asyncpg_record({
            "id": "topic-1",
            "name": "Test Topic",
            "status": "active",
            "content_count": 42,
            "signal_count": 3,
        })
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=fake_row)

        result = await get_topic(conn, "topic-1")
        assert result is not None
        assert "content_count" in result, \
            "get_topic() must return content_count"


# ---------------------------------------------------------------------------
# Bug 2: Identifier cluster item INSERT column mismatch
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestIdentifierClusterItemInsert:
    """SQL_INSERT_IDENTIFIER_CLUSTER_ITEM must match actual table schema."""

    def test_insert_does_not_reference_id_column(self):
        """Table has composite PK (identifier_cluster_id, content_item_id), no 'id' column."""
        from anveshak.analyst.scheduler import SQL_INSERT_IDENTIFIER_CLUSTER_ITEM
        # Extract column list from INSERT INTO ... (columns) VALUES
        match = re.search(
            r"INSERT\s+INTO\s+identifier_cluster_items\s*\(([^)]+)\)",
            SQL_INSERT_IDENTIFIER_CLUSTER_ITEM,
            re.IGNORECASE,
        )
        assert match, "SQL must be an INSERT INTO identifier_cluster_items"
        columns = [c.strip().lower() for c in match.group(1).split(",")]
        assert "id" not in columns, \
            "identifier_cluster_items has no 'id' column — INSERT must not reference it"

    def test_insert_does_not_reference_labels_column(self):
        """Table has no 'labels' column."""
        from anveshak.analyst.scheduler import SQL_INSERT_IDENTIFIER_CLUSTER_ITEM
        match = re.search(
            r"INSERT\s+INTO\s+identifier_cluster_items\s*\(([^)]+)\)",
            SQL_INSERT_IDENTIFIER_CLUSTER_ITEM,
            re.IGNORECASE,
        )
        assert match
        columns = [c.strip().lower() for c in match.group(1).split(",")]
        assert "labels" not in columns, \
            "identifier_cluster_items has no 'labels' column — INSERT must not reference it"

    def test_insert_uses_three_params(self):
        """INSERT must use exactly 3 positional params ($1, $2, $3)."""
        from anveshak.analyst.scheduler import SQL_INSERT_IDENTIFIER_CLUSTER_ITEM
        params = re.findall(r"\$\d+", SQL_INSERT_IDENTIFIER_CLUSTER_ITEM)
        assert params == ["$1", "$2", "$3"], \
            f"Expected 3 params ($1,$2,$3) for (identifier_cluster_id, content_item_id, source_id), got {params}"

    def test_insert_columns_match_schema(self):
        """INSERT must target exactly: identifier_cluster_id, content_item_id, source_id."""
        from anveshak.analyst.scheduler import SQL_INSERT_IDENTIFIER_CLUSTER_ITEM
        match = re.search(
            r"INSERT\s+INTO\s+identifier_cluster_items\s*\(([^)]+)\)",
            SQL_INSERT_IDENTIFIER_CLUSTER_ITEM,
            re.IGNORECASE,
        )
        assert match
        columns = {c.strip().lower() for c in match.group(1).split(",")}
        expected = {"identifier_cluster_id", "content_item_id", "source_id"}
        assert columns == expected, \
            f"Columns {columns} don't match table schema {expected}"


@pytest.mark.unit
class TestIdentifierClusterCycleCallSite:
    """_run_identifier_cluster_cycle must pass correct args to INSERT."""

    @pytest.mark.asyncio
    async def test_execute_called_with_three_params(self):
        """INSERT call site must pass (cluster_id, content_item_id, source_id) — no uuid prefix."""
        from anveshak.analyst.identifier_clustering import (
            IdentifierCluster,
        )

        now = datetime.now(timezone.utc)

        fake_cluster = IdentifierCluster(
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            content_item_ids=frozenset(["ci-1"]),
            source_ids=frozenset(["src-1"]),
            source_count=2,
            content_item_count=2,
            first_seen_at=now,
            last_seen_at=now,
        )

        fake_entity_rows = [
            {
                "entity_type": "PHONE_IN",
                "entity_text": "9876543210",
                "confidence": 0.95,
                "content_item_id": "ci-1",
                "source_id": "src-1",
                "captured_at": now,
                "topic_id": "topic-1",
            },
        ]

        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=[
            [{"id": "topic-1"}],  # active topics
            fake_entity_rows,     # unclustered identifiers
        ])
        conn.fetchrow = AsyncMock(return_value={"id": "cluster-1"})
        conn.execute = AsyncMock()

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)

        acq = AsyncMock()
        acq.__aenter__ = AsyncMock(return_value=conn)
        acq.__aexit__ = AsyncMock(return_value=False)

        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=acq)

        with patch("anveshak.analyst.scheduler.build_clusters", return_value=[fake_cluster]):
            from anveshak.analyst.scheduler import _run_identifier_cluster_cycle
            await _run_identifier_cluster_cycle(pool)

        # Find the execute call for INSERT INTO identifier_cluster_items
        insert_calls = [
            c for c in conn.execute.call_args_list
            if "identifier_cluster_items" in str(c)
        ]
        assert len(insert_calls) >= 1, "Must INSERT into identifier_cluster_items"
        # Each INSERT call should have SQL + 3 params (not 4)
        for call in insert_calls:
            args = call.args
            # args[0] = SQL string, args[1:] = params
            param_count = len(args) - 1
            assert param_count == 3, \
                f"INSERT must pass 3 params (cluster_id, ci_id, source_id), got {param_count}"


# ---------------------------------------------------------------------------
# Bug 3: Audit trail inaccessible to analysts
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAuditTrailByResourceId:
    """get_audit_trail() must filter by resource_id even without resource_type."""

    @pytest.mark.asyncio
    async def test_resource_id_only_filters_correctly(self):
        """When resource_id is given without resource_type, must still filter."""
        from anveshak.api.db.audit import get_audit_trail

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])

        await get_audit_trail(conn, resource_type=None, resource_id="topic-123", limit=5, offset=0)

        # Must NOT fall through to SQL_GET_AUDIT_TRAIL_ALL
        call_args = conn.fetch.call_args
        sql = call_args.args[0].lower()
        assert "resource_id" in sql, \
            "When resource_id is provided, SQL must filter by resource_id (not return all)"

    def test_sql_get_audit_trail_by_resource_id_exists(self):
        """A SQL constant for resource_id-only filtering must exist."""
        from anveshak.api.db import audit
        assert hasattr(audit, "SQL_GET_AUDIT_TRAIL_BY_RESOURCE_ID"), \
            "audit.py must define SQL_GET_AUDIT_TRAIL_BY_RESOURCE_ID"

    def test_sql_get_audit_trail_by_resource_id_content(self):
        """SQL must filter by resource_id without requiring resource_type."""
        from anveshak.api.db.audit import SQL_GET_AUDIT_TRAIL_BY_RESOURCE_ID
        sql_lower = SQL_GET_AUDIT_TRAIL_BY_RESOURCE_ID.lower()
        assert "resource_id" in sql_lower
        assert "audit_trail" in sql_lower


@pytest.mark.unit
class TestAuditTrailAnalystAccess:
    """Audit trail endpoint must allow analyst role when resource_id is provided."""

    def test_audit_trail_route_accepts_analyst(self):
        """Route decorator must include 'analyst' in allowed roles."""
        import inspect
        from anveshak.api.routes import system
        source = inspect.getsource(system.get_audit_trail)
        assert "analyst" in source, \
            "audit-trail endpoint must allow analyst role"
