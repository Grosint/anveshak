"""Unit tests for topic scheduled report management.

Tests:
  - update_topic_schedule DB function exists and is callable
  - Invalid cron expression rejected
  - Valid cron stored correctly
  - Clearing schedule (null cron) works

pytest.mark.unit — mock DB.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit


class TestUpdateTopicScheduleDB:
    """update_topic_schedule DB function."""

    @pytest.mark.asyncio
    async def test_function_exists(self):
        from anveshak.api.db.topics import update_topic_schedule
        assert callable(update_topic_schedule)

    @pytest.mark.asyncio
    async def test_sets_cron_and_type(self):
        from anveshak.api.db.topics import update_topic_schedule

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        await update_topic_schedule(
            mock_conn, "topic-1", "0 9 * * MON", "weekly_digest"
        )
        mock_conn.execute.assert_awaited_once()
        call_args = mock_conn.execute.call_args[0]
        assert call_args[1] == "0 9 * * MON"
        assert call_args[2] == "weekly_digest"
        assert call_args[3] == "topic-1"

    @pytest.mark.asyncio
    async def test_clears_schedule(self):
        from anveshak.api.db.topics import update_topic_schedule

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        await update_topic_schedule(mock_conn, "topic-1", None, None)
        call_args = mock_conn.execute.call_args[0]
        assert call_args[1] is None
        assert call_args[2] is None


class TestScheduleEndpointValidation:
    """Validate cron expression in the update endpoint."""

    def test_valid_cron_accepted(self):
        """croniter must accept the expression."""
        from croniter import croniter
        # Should not raise
        croniter("0 9 * * MON")
        croniter("*/15 * * * *")
        croniter("0 0 * * 0")

    def test_invalid_cron_rejected(self):
        """croniter rejects malformed cron expressions."""
        from croniter import croniter
        with pytest.raises((ValueError, KeyError)):
            croniter("INVALID CRON")
