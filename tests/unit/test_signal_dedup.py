"""Unit tests for signal dedup logic (Phase 2, criteria 2.31).

pytest.mark.unit — no external dependencies, no DB, no network.
All functions under test are pure or use mock asyncpg connections.
"""
from __future__ import annotations

from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock

import pytest

from anveshak.analyst.signal_engine import (
    build_signal_payload,
    is_duplicate_signal,
)


# ---------------------------------------------------------------------------
# build_signal_payload — pure function, no DB
# ---------------------------------------------------------------------------

class TestBuildSignalPayload:
    """Criteria 2.19: WebSocket message schema."""

    def test_required_keys_present(self):
        payload = build_signal_payload(
            signal_id="sig-1",
            topic_id="topic-1",
            cluster_id="cluster-1",
            independent_source_count=3,
            label="IAF Procurement Controversy",
        )
        assert payload["type"] == "signal"
        assert payload["signal_id"] == "sig-1"
        assert payload["topic_id"] == "topic-1"
        assert "severity" in payload

    def test_high_severity_at_three_sources(self):
        payload = build_signal_payload("s", "t", "c", 3, "label")
        assert payload["severity"] == "HIGH"

    def test_medium_severity_below_three(self):
        payload = build_signal_payload("s", "t", "c", 2, "label")
        assert payload["severity"] == "MEDIUM"

    def test_high_severity_above_three(self):
        payload = build_signal_payload("s", "t", "c", 5, "label")
        assert payload["severity"] == "HIGH"

    def test_label_included(self):
        payload = build_signal_payload("s", "t", "c", 2, "My Cluster Label")
        assert payload["cluster_label"] == "My Cluster Label"


# ---------------------------------------------------------------------------
# is_duplicate_signal — async, uses mock asyncpg connection
# ---------------------------------------------------------------------------

class TestIsDuplicateSignal:
    """Criteria 2.13: same cluster_id + signal_type within 24h → duplicate."""

    @pytest.mark.asyncio
    async def test_not_duplicate_when_no_existing_signal(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)  # no row found

        result = await is_duplicate_signal(conn, "cluster-1", "multi_source_convergence")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_duplicate_when_recent_signal_exists(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"id": "existing-signal-id"})

        result = await is_duplicate_signal(conn, "cluster-1", "multi_source_convergence")
        assert result is True

    @pytest.mark.asyncio
    async def test_different_cluster_not_duplicate(self):
        """Signals for different clusters are independent."""
        call_count = 0
        async def mock_fetchrow(sql, cluster_id, signal_type):
            nonlocal call_count
            call_count += 1
            # Only cluster-1 has existing signal
            if cluster_id == "cluster-1":
                return {"id": "existing-signal-id"}
            return None

        conn = AsyncMock()
        conn.fetchrow = mock_fetchrow

        result_dup = await is_duplicate_signal(conn, "cluster-1", "multi_source_convergence")
        result_new = await is_duplicate_signal(conn, "cluster-2", "multi_source_convergence")

        assert result_dup is True
        assert result_new is False

    @pytest.mark.asyncio
    async def test_correct_sql_params_passed(self):
        """Verify the right cluster_id and signal_type are sent to DB."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        await is_duplicate_signal(conn, "my-cluster", "multi_source_convergence")

        conn.fetchrow.assert_called_once()
        call_args = conn.fetchrow.call_args
        # Positional args after SQL: cluster_id, signal_type
        assert "my-cluster" in call_args.args
        assert "multi_source_convergence" in call_args.args
