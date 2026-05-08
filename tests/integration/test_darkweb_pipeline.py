"""Integration test: dark web source creation + .onion URL validation.

pytest.mark.integration — requires running Docker Compose services:
  make up

Run with:
  uv run --package anveshak-tests pytest tests/integration/test_darkweb_pipeline.py -v -m integration
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, UTC

import pytest
import asyncpg

pytestmark = pytest.mark.integration

POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_pool():
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=3)
    yield pool
    await pool.close()


@pytest.fixture
async def test_topic(db_pool):
    """Create a throwaway topic for the integration test."""
    topic_id = str(uuid.uuid4())
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO topics (id, name, keywords, status, created_at, updated_at, labels)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            topic_id, "Darkweb Integration Test", ["darkweb", "test"],
            "active", datetime.now(UTC), datetime.now(UTC),
            '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}',
        )
    yield topic_id
    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM content_items WHERE topic_id = $1", topic_id
        )
        await conn.execute(
            "DELETE FROM topic_sources WHERE topic_id = $1", topic_id
        )
        await conn.execute("DELETE FROM topics WHERE id = $1", topic_id)


@pytest.fixture
async def darkweb_source(db_pool, test_topic):
    """Create a throwaway dark web source linked to the test topic."""
    source_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO sources (
                id, name, url_or_handle, platform, credibility_score,
                created_at, updated_at, labels
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            source_id,
            "Test Onion Site",
            "http://testsite.onion",
            "darkweb",
            50.0,
            now,
            now,
            '{"classification":"RESTRICTED","domain":"darkweb","owner_org":"anveshak"}',
        )
        await conn.execute(
            """
            INSERT INTO topic_sources (topic_id, source_id, added_at)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            test_topic, source_id, now,
        )
    yield source_id
    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM topic_sources WHERE source_id = $1", source_id
        )
        await conn.execute("DELETE FROM sources WHERE id = $1", source_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDarkwebSourceInDB:

    @pytest.mark.asyncio
    async def test_darkweb_source_has_correct_platform(self, db_pool, darkweb_source):
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT platform FROM sources WHERE id = $1", darkweb_source
            )
        assert row is not None
        assert row["platform"] == "darkweb"

    @pytest.mark.asyncio
    async def test_darkweb_source_linked_to_topic(self, db_pool, test_topic, darkweb_source):
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT source_id FROM topic_sources WHERE topic_id = $1 AND source_id = $2",
                test_topic, darkweb_source,
            )
        assert row is not None

    @pytest.mark.asyncio
    async def test_darkweb_sql_query_returns_source(self, db_pool, test_topic, darkweb_source):
        from anveshak.scraper.jobs import SQL_GET_DARKWEB_SOURCES

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(SQL_GET_DARKWEB_SOURCES, test_topic)
        source_ids = [r["id"] for r in rows]
        assert darkweb_source in source_ids

    @pytest.mark.asyncio
    async def test_web_sql_query_does_not_return_darkweb_source(
        self, db_pool, test_topic, darkweb_source
    ):
        from anveshak.scraper.jobs import SQL_GET_WEB_SOURCES

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(SQL_GET_WEB_SOURCES, test_topic)
        source_ids = [r["id"] for r in rows]
        assert darkweb_source not in source_ids


class TestDarkwebContentDedup:

    @pytest.mark.asyncio
    async def test_duplicate_content_hash_rejected(self, db_pool, test_topic, darkweb_source):
        """ON CONFLICT(content_hash) DO NOTHING must work for darkweb content."""
        from anveshak.scraper.jobs import SQL_INSERT_CONTENT
        from anveshak.scraper.normalise import compute_content_hash

        raw_text = "Dark web content for dedup test"
        content_hash = compute_content_hash(raw_text)
        now = datetime.now(UTC)
        labels = '{"classification":"RESTRICTED","domain":"darkweb","owner_org":"anveshak"}'

        async with db_pool.acquire() as conn:
            # First insert
            r1 = await conn.fetchrow(
                SQL_INSERT_CONTENT,
                str(uuid.uuid4()), test_topic, darkweb_source,
                raw_text, raw_text, "en", content_hash,
                "http://testsite.onion/page1", now, 50.0,
                now, now, labels, "good", content_hash, "Test",
            )
            # Second insert with same content_hash
            r2 = await conn.fetchrow(
                SQL_INSERT_CONTENT,
                str(uuid.uuid4()), test_topic, darkweb_source,
                raw_text, raw_text, "en", content_hash,
                "http://testsite.onion/page1", now, 50.0,
                now, now, labels, "good", content_hash, "Test",
            )

        assert r1 is not None  # first insert succeeds
        assert r2 is None  # duplicate rejected
