"""Integration test: full scrape → DB → analyst → embedding stored (criteria 1.33, 1.34).

pytest.mark.integration — requires running Docker Compose services:
  make up

Run with:
  uv run --package anveshak-tests pytest tests/integration/ -v -m integration
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, UTC

import pytest
import asyncpg

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

POSTGRES_URL = os.environ.get("POSTGRES_URL", "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak")


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
            topic_id, "Integration Test Topic", ["test", "integration"],
            "active", datetime.now(UTC), datetime.now(UTC),
            '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}',
        )
    yield topic_id
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM topics WHERE id = $1", topic_id)


@pytest.fixture
async def test_source(db_pool):
    """Create a throwaway web source for the integration test."""
    source_id = str(uuid.uuid4())
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO sources (
                id, name, url_or_handle, platform, credibility_score,
                created_at, updated_at, labels
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            source_id, "Test Source", "https://example.com", "web", 75.0,
            datetime.now(UTC), datetime.now(UTC),
            '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}',
        )
    yield source_id
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM sources WHERE id = $1", source_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _insert_content_item(
    db_pool: asyncpg.Pool,
    topic_id: str,
    source_id: str,
    text: str,
    content_hash: str,
    url: str = "https://example.com/article",
) -> str:
    """Insert a content_item directly (simulates scraper output)."""
    from anveshak.scraper.normalise import compute_content_hash

    item_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO content_items (
                id, topic_id, source_id, raw_text, clean_text, language,
                content_hash, url, captured_at, credibility_score_at_capture,
                created_at, updated_at, labels
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            ON CONFLICT(content_hash) DO NOTHING
            """,
            item_id, topic_id, source_id, text, text, "en",
            content_hash, url, now, 75.0, now, now,
            '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}',
        )
    return item_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_content_hash_deduplication(db_pool, test_topic, test_source):
    """Criteria 1.26: same content scraped twice → exactly ONE row."""
    from anveshak.scraper.normalise import compute_content_hash

    text = "This is a test article about defence procurement. " * 5
    content_hash = compute_content_hash(text)

    # Insert twice
    id1 = await _insert_content_item(
        db_pool, test_topic, test_source, text, content_hash, "https://example.com/a1"
    )
    id2 = await _insert_content_item(
        db_pool, test_topic, test_source, text, content_hash, "https://example.com/a2"
    )

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM content_items WHERE content_hash = $1", content_hash
        )

    assert count == 1, "Duplicate content_hash must produce exactly one row"



# NOTE: test_analyst_sets_embedding, test_extracted_entities_exist, and
# test_language_not_null_after_analysis have been moved to
# scripts/test_analyst_models.py (runs inside analyst-worker container
# where spaCy and sentence-transformers are installed).
# They execute as part of `make test-integration` step 2/4.


