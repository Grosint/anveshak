"""Integration tests — topics DB repository against real PostgreSQL.

Replaces tests/unit/test_db_topics.py which only tested mocks.
Exercises real SQL: topic CRUD, entity aggregation, cluster queries.

Requires: make up (PostgreSQL running)
"""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

import pytest

from anveshak.api.db.topics import (
    get_topic,
    insert_topic,
    list_topics,
    topic_exists,
    update_topic_status,
    get_topic_entities,
)

from tests.conftest import LABELS_JSON

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _cleanup_topic(conn, topic_id: str) -> None:
    await conn.execute("DELETE FROM extracted_entities WHERE content_item_id IN (SELECT id FROM content_items WHERE topic_id=$1)", topic_id)
    await conn.execute("DELETE FROM content_items WHERE topic_id=$1", topic_id)
    await conn.execute("DELETE FROM topic_sources WHERE topic_id=$1", topic_id)
    await conn.execute("DELETE FROM topics WHERE id=$1", topic_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_insert_and_get_topic(db_pool):
    """INSERT a topic then SELECT it — all fields must match."""
    topic_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        await insert_topic(
            conn, topic_id, "Defence Intel Test", ["defence", "IAF"],
            ["en"], 30.0, 3, [], None, None, now, LABELS_JSON,
        )
        result = await get_topic(conn, topic_id)

    try:
        assert result is not None, "get_topic should return the inserted topic"
        assert result["id"] == topic_id
        assert result["name"] == "Defence Intel Test"
        assert result["signal_threshold"] == 3
        assert result["credibility_min"] == 30.0
    finally:
        async with db_pool.acquire() as conn:
            await _cleanup_topic(conn, topic_id)


async def test_get_topic_returns_none_for_missing(db_pool):
    """get_topic with non-existent ID → None."""
    async with db_pool.acquire() as conn:
        result = await get_topic(conn, "nonexistent-topic-id")
    assert result is None


async def test_topic_exists_true_and_false(db_pool):
    """topic_exists returns True for existing, False for missing."""
    topic_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        await insert_topic(
            conn, topic_id, "Exists Test", ["test"],
            ["en"], 30.0, 2, [], None, None, now, LABELS_JSON,
        )
        assert await topic_exists(conn, topic_id) is True
        assert await topic_exists(conn, "nonexistent-id") is False
    async with db_pool.acquire() as conn:
        await _cleanup_topic(conn, topic_id)


async def test_update_topic_status(db_pool):
    """update_topic_status changes status in DB."""
    topic_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        await insert_topic(
            conn, topic_id, "Status Test", ["test"],
            ["en"], 30.0, 2, [], None, None, now, LABELS_JSON,
        )
        await update_topic_status(conn, topic_id, "paused", now)
        result = await get_topic(conn, topic_id)

    try:
        assert result["status"] == "paused"
    finally:
        async with db_pool.acquire() as conn:
            await _cleanup_topic(conn, topic_id)


async def test_list_topics_includes_counts(db_pool):
    """list_topics returns content_count and signal_count from JOINs."""
    topic_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        await insert_topic(
            conn, topic_id, "List Test", ["test"],
            ["en"], 30.0, 2, [], None, None, now, LABELS_JSON,
        )
        result = await list_topics(conn)

    try:
        matching = [t for t in result if t["id"] == topic_id]
        assert len(matching) == 1
        topic = matching[0]
        # New topic should have 0 content and 0 signals
        assert topic["content_count"] == 0
        assert topic["signal_count"] == 0
    finally:
        async with db_pool.acquire() as conn:
            await _cleanup_topic(conn, topic_id)


async def test_get_topic_entities_empty(db_pool):
    """Topic with no content → empty entities list."""
    topic_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        await insert_topic(
            conn, topic_id, "Entities Test", ["test"],
            ["en"], 30.0, 2, [], None, None, now, LABELS_JSON,
        )
        result = await get_topic_entities(conn, topic_id)

    try:
        assert result == [], "New topic with no content should have no entities"
    finally:
        async with db_pool.acquire() as conn:
            await _cleanup_topic(conn, topic_id)
