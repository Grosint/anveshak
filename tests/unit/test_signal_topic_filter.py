"""Unit tests for signals API topic-scoped filtering.

Bug: GET /api/v1/signals?topic_id=X returns ALL org signals, not just topic X.
Route calls list_signals_by_org(org_id) ignoring topic_id param.

pytest.mark.unit — mocks DB, no external dependencies.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


def _fake_user(role="analyst", org_id="org_cyber"):
    return {"sub": "user-1", "role": role, "org_id": org_id}


class TestListSignalsTopicFilter:
    @pytest.mark.asyncio
    async def test_org_user_with_topic_id_calls_topic_scoped_query(self):
        """When topic_id is provided, must call list_signals with topic_id, not list_signals_by_org."""
        from anveshak.api.routes.signals import list_signals

        db = AsyncMock()
        user = _fake_user()

        with patch("anveshak.api.routes.signals.signals_db") as mock_db:
            mock_db.list_signals_by_org = AsyncMock(return_value=([], 0))
            mock_db.list_signals = AsyncMock(return_value=([], 0))

            await list_signals(
                status="new",
                topic_id="topic-123",
                since=None,
                until=None,
                limit=50,
                offset=0,
                db=db,
                user=user,
            )

            # Must NOT call org-wide query
            mock_db.list_signals_by_org.assert_not_awaited()
            # Must call topic-scoped query
            mock_db.list_signals.assert_awaited_once_with(db, "new", 50, 0, topic_id="topic-123")

    @pytest.mark.asyncio
    async def test_org_user_without_topic_id_calls_org_scoped_query(self):
        """When topic_id is absent, use org-scoped query (global signals page)."""
        from anveshak.api.routes.signals import list_signals

        db = AsyncMock()
        user = _fake_user()

        with patch("anveshak.api.routes.signals.signals_db") as mock_db:
            mock_db.list_signals_by_org = AsyncMock(return_value=([], 0))
            mock_db.list_signals = AsyncMock(return_value=([], 0))

            await list_signals(
                status="new",
                topic_id=None,
                since=None,
                until=None,
                limit=50,
                offset=0,
                db=db,
                user=user,
            )

            # Org-scoped when no topic_id
            mock_db.list_signals_by_org.assert_awaited_once_with(db, "new", "org_cyber", 50, 0)
            mock_db.list_signals.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_time_filtered_with_topic_id_passes_topic(self):
        """Time-range queries with topic_id must also filter by topic."""
        from datetime import UTC, datetime

        from anveshak.api.routes.signals import list_signals

        db = AsyncMock()
        user = _fake_user()
        since = datetime(2026, 6, 1, tzinfo=UTC)
        until = datetime(2026, 6, 15, tzinfo=UTC)

        with patch("anveshak.api.routes.signals.signals_db") as mock_db:
            mock_db.list_signals_filtered = AsyncMock(return_value=[])

            await list_signals(
                status="new",
                topic_id="topic-123",
                since=since,
                until=until,
                limit=50,
                offset=0,
                db=db,
                user=user,
            )

            mock_db.list_signals_filtered.assert_awaited_once_with(
                db,
                "new",
                since,
                until,
                topic_id="topic-123",
                org_id="org_cyber",
            )
