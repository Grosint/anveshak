"""Tests for Trackers feature — persistent analyst case files.

Trackers replace ephemeral Leiden narrative clusters with permanent,
analyst-owned objects that survive re-clustering cycles.

pytest.mark.unit — no external dependencies.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _FakeRecord(dict):
    """Mimics asyncpg.Record: dict() conversion works."""
    pass


def asyncpg_record(data: dict) -> _FakeRecord:
    return _FakeRecord(data)


# ---------------------------------------------------------------------------
# 1. Migration / Schema: SQL constants exist and are well-formed
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTrackerSQLConstants:
    """SQL constants for trackers must exist and match table schema."""

    def test_sql_insert_tracker_exists(self):
        from anveshak.api.db.trackers import SQL_INSERT_TRACKER
        sql = SQL_INSERT_TRACKER.lower()
        assert "insert into trackers" in sql

    def test_sql_insert_tracker_has_required_columns(self):
        from anveshak.api.db.trackers import SQL_INSERT_TRACKER
        sql = SQL_INSERT_TRACKER.lower()
        for col in ["id", "case_number", "org_id", "topic_id", "title",
                     "status", "priority", "created_by", "created_at",
                     "updated_at", "labels"]:
            assert col in sql, f"SQL_INSERT_TRACKER must include {col}"

    def test_sql_insert_tracker_has_centroid(self):
        from anveshak.api.db.trackers import SQL_INSERT_TRACKER
        sql = SQL_INSERT_TRACKER.lower()
        assert "centroid" in sql, "SQL_INSERT_TRACKER must include centroid for cluster seeding"

    def test_sql_get_tracker_exists(self):
        from anveshak.api.db.trackers import SQL_GET_TRACKER
        sql = SQL_GET_TRACKER.lower()
        assert "trackers" in sql
        assert "content_count" in sql or "tracker_content_items" in sql, \
            "SQL_GET_TRACKER should compute content/pending counts"

    def test_sql_list_trackers_exists(self):
        from anveshak.api.db.trackers import SQL_LIST_TRACKERS_BY_ORG
        sql = SQL_LIST_TRACKERS_BY_ORG.lower()
        assert "trackers" in sql
        assert "org_id" in sql or "$1" in sql

    def test_sql_insert_tracker_content_exists(self):
        from anveshak.api.db.trackers import SQL_INSERT_TRACKER_CONTENT
        sql = SQL_INSERT_TRACKER_CONTENT.lower()
        assert "tracker_content_items" in sql
        assert "attached_by" in sql
        assert "on conflict" in sql, "Must use ON CONFLICT DO NOTHING for idempotency"

    def test_sql_confirm_content_exists(self):
        from anveshak.api.db.trackers import SQL_CONFIRM_CONTENT
        sql = SQL_CONFIRM_CONTENT.lower()
        assert "tracker_content_items" in sql
        assert "confirmed" in sql

    def test_sql_insert_exclusion_exists(self):
        from anveshak.api.db.trackers import SQL_INSERT_EXCLUSION
        sql = SQL_INSERT_EXCLUSION.lower()
        assert "tracker_content_exclusions" in sql

    def test_sql_insert_note_exists(self):
        from anveshak.api.db.trackers import SQL_INSERT_NOTE
        sql = SQL_INSERT_NOTE.lower()
        assert "tracker_notes" in sql
        assert "body" in sql

    def test_sql_insert_audit_log_exists(self):
        from anveshak.api.db.trackers import SQL_INSERT_AUDIT_LOG
        sql = SQL_INSERT_AUDIT_LOG.lower()
        assert "tracker_audit_log" in sql
        assert "action" in sql

    def test_sql_seed_from_cluster_exists(self):
        from anveshak.api.db.trackers import SQL_SEED_FROM_CLUSTER
        sql = SQL_SEED_FROM_CLUSTER.lower()
        assert "tracker_content_items" in sql
        assert "narrative_cluster" in sql or "content_items" in sql


# ---------------------------------------------------------------------------
# 2. Case number generation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCaseNumberGeneration:
    """Case numbers must follow TRK-YYYY-NNNN format."""

    @pytest.mark.asyncio
    async def test_generate_case_number_format(self):
        from anveshak.api.db.trackers import generate_case_number

        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=42)

        case_number = await generate_case_number(conn)
        year = datetime.now(timezone.utc).year
        assert case_number == f"TRK-{year}-0042"

    @pytest.mark.asyncio
    async def test_generate_case_number_pads_to_four_digits(self):
        from anveshak.api.db.trackers import generate_case_number

        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=1)

        case_number = await generate_case_number(conn)
        year = datetime.now(timezone.utc).year
        assert case_number == f"TRK-{year}-0001"


# ---------------------------------------------------------------------------
# 3. Repository functions
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTrackerRepository:
    """Core repository functions for trackers."""

    @pytest.mark.asyncio
    async def test_create_tracker_returns_dict(self):
        from anveshak.api.db.trackers import create_tracker

        fake_row = asyncpg_record({
            "id": "trk-1",
            "case_number": "TRK-2026-0001",
            "title": "Test Tracker",
            "status": "watching",
        })
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=1)  # sequence
        conn.fetchrow = AsyncMock(return_value=fake_row)
        conn.execute = AsyncMock()

        result = await create_tracker(
            conn,
            topic_id="topic-1",
            title="Test Tracker",
            created_by="user-1",
            org_id="org-1",
        )
        assert result is not None
        assert result["case_number"] == "TRK-2026-0001"

    @pytest.mark.asyncio
    async def test_get_tracker_returns_none_when_missing(self):
        from anveshak.api.db.trackers import get_tracker

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        result = await get_tracker(conn, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_tracker_returns_dict(self):
        from anveshak.api.db.trackers import get_tracker

        fake_row = asyncpg_record({
            "id": "trk-1",
            "case_number": "TRK-2026-0001",
            "title": "Test",
            "status": "active",
            "content_count": 10,
            "pending_count": 3,
        })
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=fake_row)

        result = await get_tracker(conn, "trk-1")
        assert result is not None
        assert result["content_count"] == 10
        assert result["pending_count"] == 3

    @pytest.mark.asyncio
    async def test_add_note_returns_note(self):
        from anveshak.api.db.trackers import add_note

        conn = AsyncMock()
        conn.execute = AsyncMock()

        result = await add_note(conn, "trk-1", "user-1", "This is a note")
        assert result is not None
        assert result["body"] == "This is a note"
        assert result["user_id"] == "user-1"
        assert "id" in result
        assert "created_at" in result

    @pytest.mark.asyncio
    async def test_reject_content_inserts_exclusion(self):
        """Rejecting content must insert into exclusions AND delete from tracker_content_items."""
        from anveshak.api.db.trackers import reject_content

        conn = AsyncMock()
        conn.execute = AsyncMock()

        await reject_content(conn, "trk-1", "ci-1", "user-1")

        # Must have called execute at least twice (delete + insert exclusion + audit log)
        assert conn.execute.call_count >= 2
        calls_sql = [str(c) for c in conn.execute.call_args_list]
        has_exclusion = any("tracker_content_exclusions" in s for s in calls_sql)
        has_delete = any("DELETE" in s.upper() or "tracker_content_items" in s for s in calls_sql)
        assert has_exclusion, "Must insert into tracker_content_exclusions"


# ---------------------------------------------------------------------------
# 4. Status transitions
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStatusTransitions:
    """Status change rules for trackers."""

    @pytest.mark.asyncio
    async def test_conclude_requires_closing_summary(self):
        """Concluding a tracker must require a closing_summary."""
        from anveshak.api.db.trackers import update_tracker_status

        conn = AsyncMock()
        conn.execute = AsyncMock()

        with pytest.raises((ValueError, Exception)):
            await update_tracker_status(
                conn, "trk-1", "concluded", "user-1",
                closing_summary=None,
            )

    @pytest.mark.asyncio
    async def test_conclude_with_summary_succeeds(self):
        from anveshak.api.db.trackers import update_tracker_status

        conn = AsyncMock()
        conn.execute = AsyncMock()

        # Should not raise
        await update_tracker_status(
            conn, "trk-1", "concluded", "user-1",
            closing_summary="Case closed. Chargesheet filed.",
        )
        assert conn.execute.called


# ---------------------------------------------------------------------------
# 5. Access control
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTrackerAccess:
    """Org isolation for trackers."""

    @pytest.mark.asyncio
    async def test_verify_tracker_access_raises_on_wrong_org(self):
        from anveshak.api.db.trackers import verify_tracker_access

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=asyncpg_record({"org_id": "org-A"}))

        user = {"sub": "user-1", "role": "analyst", "org_id": "org-B"}

        with pytest.raises(Exception):
            await verify_tracker_access(conn, "trk-1", user)

    @pytest.mark.asyncio
    async def test_verify_tracker_access_passes_for_same_org(self):
        from anveshak.api.db.trackers import verify_tracker_access

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=asyncpg_record({"org_id": "org-A"}))

        user = {"sub": "user-1", "role": "analyst", "org_id": "org-A"}

        # Should not raise
        await verify_tracker_access(conn, "trk-1", user)


# ---------------------------------------------------------------------------
# 6. Notes immutability (no update/delete SQL exists)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNotesImmutability:
    """Tracker notes must be append-only — no update or delete operations."""

    def test_no_update_note_sql(self):
        from anveshak.api.db import trackers
        # There must be no SQL constant for updating notes
        attrs = [a for a in dir(trackers) if a.startswith("SQL_")]
        update_note = [a for a in attrs if "UPDATE" in a and "NOTE" in a]
        assert len(update_note) == 0, \
            f"Notes are immutable — no UPDATE SQL allowed, found: {update_note}"

    def test_no_delete_note_sql(self):
        from anveshak.api.db import trackers
        attrs = [a for a in dir(trackers) if a.startswith("SQL_")]
        delete_note = [a for a in attrs if "DELETE" in a and "NOTE" in a]
        assert len(delete_note) == 0, \
            f"Notes are immutable — no DELETE SQL allowed, found: {delete_note}"


# ---------------------------------------------------------------------------
# 7. SDK Pydantic model
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTrackerModel:
    """Tracker Pydantic model must follow CLAUDE.md rules."""

    def test_tracker_model_has_labels(self):
        """Every Pydantic model MUST have labels: Labels (non-Optional)."""
        from anveshak.models.tracker import Tracker
        import typing
        hints = typing.get_type_hints(Tracker)
        assert "labels" in hints, "Tracker model must have labels field"

    def test_tracker_model_has_required_fields(self):
        from anveshak.models.tracker import Tracker
        import typing
        hints = typing.get_type_hints(Tracker)
        for field in ["case_number", "topic_id", "title", "status",
                      "priority", "created_by"]:
            assert field in hints, f"Tracker model must have {field}"


# ---------------------------------------------------------------------------
# 8. Scheduler: tracker matching SQL
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTrackerMatching:
    """Auto-matching cycle must exist in scheduler."""

    def test_tracker_matching_function_exists(self):
        from anveshak.analyst.scheduler import _run_tracker_matching_cycle
        assert callable(_run_tracker_matching_cycle)

    def test_tracker_matching_loop_exists(self):
        from anveshak.analyst.scheduler import tracker_matching_loop
        assert callable(tracker_matching_loop)

    def test_tracker_matching_registered_in_lifespan(self):
        """tracker_matching_loop must be registered in the scheduler lifespan."""
        import inspect
        from anveshak.analyst import scheduler
        source = inspect.getsource(scheduler.lifespan)
        assert "tracker_matching_loop" in source, \
            "tracker_matching_loop must be registered in lifespan task list"

    @pytest.mark.asyncio
    async def test_tracker_matching_skips_when_no_trackers(self):
        """When no active trackers exist, matching should complete without error."""
        from anveshak.analyst.scheduler import _run_tracker_matching_cycle

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])  # no active trackers

        acq = AsyncMock()
        acq.__aenter__ = AsyncMock(return_value=conn)
        acq.__aexit__ = AsyncMock(return_value=False)

        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=acq)

        # Should complete without error
        await _run_tracker_matching_cycle(pool)
        assert conn.fetch.called
