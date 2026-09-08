"""Publication time and collection time are independently observable — #24.

The point of the column is that a NULL publication time stays NULL. A test
that only checks the column exists would pass against the old behaviour of
writing now(), so these assert on the distinction itself.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

PUBLISHED = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


async def _insert(db_pool, topic_id, source_id, *, published_at, captured_at):
    content_id = str(uuid.uuid4())
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO content_items (
                id, topic_id, source_id, org_id, raw_text, clean_text,
                content_hash, captured_at, published_at, labels
            )
            VALUES ($1, $2, $3, $4, $5, $5, $6, $7, $8,
                    '{"classification":"OPEN","domain":"osint",
                      "owner_org":"anveshak"}'::jsonb)
            """,
            content_id,
            topic_id,
            source_id,
            "org-integration-test",
            f"body {content_id}",
            content_id,
            captured_at,
            published_at,
        )
    return content_id


@pytest.fixture
async def cleanup_content(db_pool):
    created: list[str] = []
    yield created
    if created:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM content_items WHERE id = ANY($1::text[])", created)


class TestTimestampsAreIndependent:
    async def test_both_timestamps_round_trip(
        self, db_pool, make_topic, make_source, cleanup_content
    ):
        topic_id = await make_topic(name="Integration Test Topic pubtime")
        source_id = await make_source(name="Test Source pubtime")
        collected = datetime.now(UTC)

        content_id = await _insert(
            db_pool, topic_id, source_id, published_at=PUBLISHED, captured_at=collected
        )
        cleanup_content.append(content_id)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT captured_at, published_at FROM content_items WHERE id = $1", content_id
            )

        assert row["published_at"] == PUBLISHED
        assert row["captured_at"] == collected
        assert row["published_at"] != row["captured_at"]

    async def test_unknown_publication_time_stays_null(
        self, db_pool, make_topic, make_source, cleanup_content
    ):
        """The whole point: a missing publication time is not the collection time."""
        topic_id = await make_topic(name="Integration Test Topic pubtime null")
        source_id = await make_source(name="Test Source pubtime null")

        content_id = await _insert(
            db_pool, topic_id, source_id, published_at=None, captured_at=datetime.now(UTC)
        )
        cleanup_content.append(content_id)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT captured_at, published_at FROM content_items WHERE id = $1", content_id
            )

        assert row["published_at"] is None
        assert row["captured_at"] is not None

    async def test_a_timeline_query_separates_known_from_unknown(
        self, db_pool, make_topic, make_source, cleanup_content
    ):
        """A chart plots the known rows and reports the unknown ones as a count."""
        topic_id = await make_topic(name="Integration Test Topic pubtime split")
        source_id = await make_source(name="Test Source pubtime split")

        for offset in (0, 1, 2):
            cleanup_content.append(
                await _insert(
                    db_pool,
                    topic_id,
                    source_id,
                    published_at=PUBLISHED + timedelta(days=offset),
                    captured_at=datetime.now(UTC),
                )
            )
        cleanup_content.append(
            await _insert(
                db_pool, topic_id, source_id, published_at=None, captured_at=datetime.now(UTC)
            )
        )

        async with db_pool.acquire() as conn:
            plotted = await conn.fetchval(
                "SELECT COUNT(*) FROM content_items "
                "WHERE topic_id = $1 AND published_at IS NOT NULL",
                topic_id,
            )
            excluded = await conn.fetchval(
                "SELECT COUNT(*) FROM content_items WHERE topic_id = $1 AND published_at IS NULL",
                topic_id,
            )

        assert plotted == 3
        assert excluded == 1


class TestStanceAndHostilityColumns:
    async def test_columns_accept_valid_values(
        self, db_pool, make_topic, make_source, cleanup_content
    ):
        topic_id = await make_topic(name="Integration Test Topic stance")
        source_id = await make_source(name="Test Source stance")
        content_id = await _insert(
            db_pool, topic_id, source_id, published_at=PUBLISHED, captured_at=datetime.now(UTC)
        )
        cleanup_content.append(content_id)

        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE content_items SET stance = $2, hostility = $3 WHERE id = $1",
                content_id,
                "opposing",
                0.42,
            )
            row = await conn.fetchrow(
                "SELECT stance, hostility FROM content_items WHERE id = $1", content_id
            )

        assert row["stance"] == "opposing"
        assert row["hostility"] == pytest.approx(0.42, abs=1e-6)

    async def test_stance_outside_the_closed_set_is_rejected(
        self, db_pool, make_topic, make_source, cleanup_content
    ):
        import asyncpg

        topic_id = await make_topic(name="Integration Test Topic stance bad")
        source_id = await make_source(name="Test Source stance bad")
        content_id = await _insert(
            db_pool, topic_id, source_id, published_at=PUBLISHED, captured_at=datetime.now(UTC)
        )
        cleanup_content.append(content_id)

        with pytest.raises(asyncpg.CheckViolationError):
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE content_items SET stance = 'hostile' WHERE id = $1", content_id
                )

    async def test_hostility_outside_zero_to_one_is_rejected(
        self, db_pool, make_topic, make_source, cleanup_content
    ):
        import asyncpg

        topic_id = await make_topic(name="Integration Test Topic hostility range")
        source_id = await make_source(name="Test Source hostility range")
        content_id = await _insert(
            db_pool, topic_id, source_id, published_at=PUBLISHED, captured_at=datetime.now(UTC)
        )
        cleanup_content.append(content_id)

        with pytest.raises(asyncpg.CheckViolationError):
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE content_items SET hostility = 1.5 WHERE id = $1", content_id
                )


class TestWatchSpaceColumns:
    async def test_topics_default_to_not_a_watch_space(self, db_pool, make_topic):
        topic_id = await make_topic(name="Integration Test Topic watchspace default")
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT is_watch_space, parent_topic_id FROM topics WHERE id = $1", topic_id
            )
        assert row["is_watch_space"] is False
        assert row["parent_topic_id"] is None

    async def test_a_topic_records_its_lineage(self, db_pool, make_topic):
        watch_space_id = await make_topic(name="Integration Test Topic watchspace parent")
        child_id = await make_topic(name="Integration Test Topic watchspace child")

        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE topics SET is_watch_space = TRUE WHERE id = $1", watch_space_id
            )
            await conn.execute(
                "UPDATE topics SET parent_topic_id = $2 WHERE id = $1", child_id, watch_space_id
            )
            row = await conn.fetchrow("SELECT parent_topic_id FROM topics WHERE id = $1", child_id)

        assert row["parent_topic_id"] == watch_space_id
