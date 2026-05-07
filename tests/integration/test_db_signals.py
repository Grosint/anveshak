"""Integration tests — signals DB repository against real PostgreSQL.

Replaces tests/unit/test_db_signals.py which only tested mocks.
Exercises real SQL: signal INSERT, list with JOIN, status transitions, enrichment.

Requires: make up (PostgreSQL running)
"""
from __future__ import annotations

import uuid
from datetime import datetime, UTC, timedelta

import pytest

from anveshak.api.db.signals import (
    acknowledge_signal,
    dismiss_signal,
    list_signals,
)

from tests.conftest import LABELS_JSON

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _setup_signal(conn, topic_id: str, cluster_id: str, signal_id: str) -> None:
    """Insert a topic, cluster, and signal for testing."""
    await conn.execute(
        """
        INSERT INTO topics (id, name, keywords, signal_threshold, created_at, updated_at, labels)
        VALUES ($1, $2, '{}', 2, NOW(), NOW(), $3::jsonb)
        ON CONFLICT (id) DO NOTHING
        """,
        topic_id, f"Signal Test {topic_id[:8]}", LABELS_JSON,
    )
    await conn.execute(
        """
        INSERT INTO narrative_clusters
            (id, topic_id, label, item_count, independent_source_count,
             created_at, updated_at, labels)
        VALUES ($1, $2, 'Test Cluster', 5, 3, NOW(), NOW(), $3::jsonb)
        ON CONFLICT (id) DO NOTHING
        """,
        cluster_id, topic_id, LABELS_JSON,
    )
    await conn.execute(
        """
        INSERT INTO signals
            (id, topic_id, cluster_id, signal_type, description, evidence,
             status, created_at, updated_at, labels)
        VALUES ($1, $2, $3, 'multi_source_convergence',
                'Test signal for integration testing', '{}',
                'new', NOW(), NOW(), $4::jsonb)
        """,
        signal_id, topic_id, cluster_id, LABELS_JSON,
    )


async def _cleanup(conn, topic_id: str) -> None:
    await conn.execute("DELETE FROM signals WHERE topic_id=$1", topic_id)
    await conn.execute("DELETE FROM narrative_clusters WHERE topic_id=$1", topic_id)
    await conn.execute("DELETE FROM topics WHERE id=$1", topic_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_list_signals_returns_enriched_data(db_pool):
    """list_signals should return signal with cluster label and topic name from JOINs."""
    topic_id = str(uuid.uuid4())
    cluster_id = str(uuid.uuid4())
    signal_id = str(uuid.uuid4())

    async with db_pool.acquire() as conn:
        await _setup_signal(conn, topic_id, cluster_id, signal_id)
        result = await list_signals(conn, "new")

    try:
        matching = [s for s in result if s["id"] == signal_id]
        assert len(matching) == 1, f"Signal {signal_id} not found in list_signals results"
        sig = matching[0]
        assert sig["cluster_label"] == "Test Cluster"
        assert sig["topic_name"] == f"Signal Test {topic_id[:8]}"
        assert sig["independent_source_count"] == 3
        assert sig["cluster_item_count"] == 5
    finally:
        async with db_pool.acquire() as conn:
            await _cleanup(conn, topic_id)


async def test_acknowledge_signal_transitions_status(db_pool):
    """acknowledge_signal should change status from 'new' to 'acknowledged'."""
    topic_id = str(uuid.uuid4())
    cluster_id = str(uuid.uuid4())
    signal_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        await _setup_signal(conn, topic_id, cluster_id, signal_id)
        result = await acknowledge_signal(conn, signal_id, now)

    try:
        assert result is not None, "Signal should be found and acknowledged"
        # Verify status changed in DB
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT status FROM signals WHERE id=$1", signal_id)
        assert row["status"] == "acknowledged"
    finally:
        async with db_pool.acquire() as conn:
            await _cleanup(conn, topic_id)


async def test_acknowledge_nonexistent_signal_returns_none(db_pool):
    """acknowledge_signal with bad ID → None, no crash."""
    async with db_pool.acquire() as conn:
        result = await acknowledge_signal(conn, "nonexistent-signal", datetime.now(UTC))
    assert result is None


async def test_dismiss_signal_transitions_status(db_pool):
    """dismiss_signal should change status from 'new' to 'dismissed'."""
    topic_id = str(uuid.uuid4())
    cluster_id = str(uuid.uuid4())
    signal_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        await _setup_signal(conn, topic_id, cluster_id, signal_id)
        result = await dismiss_signal(conn, signal_id, now)

    try:
        assert result is not None
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT status FROM signals WHERE id=$1", signal_id)
        assert row["status"] == "dismissed"
    finally:
        async with db_pool.acquire() as conn:
            await _cleanup(conn, topic_id)


async def test_list_signals_empty_when_no_matching_status(db_pool):
    """list_signals with status that has no matches → empty list."""
    async with db_pool.acquire() as conn:
        result = await list_signals(conn, "nonexistent_status")
    assert result == []
