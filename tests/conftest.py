"""Root conftest — shared fixtures for all test layers.

Provides:
  - db_pool (function-scoped) for integration/e2e tests
  - redis_conn (function-scoped) for integration/e2e tests
  - Factory fixtures: make_topic, make_source, insert_content_item
  - Constants: POSTGRES_URL, REDIS_URL, LABELS_JSON
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, UTC

import pytest

# ---------------------------------------------------------------------------
# Constants — used across all integration / e2e tests
# ---------------------------------------------------------------------------

POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak",
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


# ---------------------------------------------------------------------------
# Database pool (function-scoped to avoid event-loop conflicts)
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_pool():
    """Per-test asyncpg pool for integration tests.

    Function-scoped to avoid pytest-asyncio event-loop mismatch.
    Lightweight (min_size=1) so creation overhead is ~5ms per test.
    Existing per-file db_pool fixtures in integration tests take precedence
    over this one (pytest closest-conftest-wins rule).
    """
    asyncpg = pytest.importorskip("asyncpg")
    try:
        pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=3)
    except Exception:
        pytest.skip("PostgreSQL not available — skipping integration tests")
    yield pool
    await pool.close()


# ---------------------------------------------------------------------------
# Transaction-rollback isolation (per-test)
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_conn(db_pool):
    """Per-test connection with transaction rollback.

    Every INSERT/UPDATE inside the test is rolled back automatically.
    Zero cleanup needed — the Amazon/Stripe pattern.
    """
    conn = await db_pool.acquire()
    tx = conn.transaction()
    await tx.start()
    yield conn
    await tx.rollback()
    await db_pool.release(conn)


# ---------------------------------------------------------------------------
# Redis (function-scoped)
# ---------------------------------------------------------------------------

@pytest.fixture
async def redis_conn():
    """Per-test Redis connection."""
    try:
        import redis.asyncio as aioredis
        conn = aioredis.from_url(REDIS_URL, decode_responses=True)
        await conn.ping()
    except Exception:
        pytest.skip("Redis not available — skipping tests that need Redis")
    yield conn
    await conn.aclose()


# ---------------------------------------------------------------------------
# Factory fixtures — create test data with auto-cleanup
# ---------------------------------------------------------------------------

@pytest.fixture
async def make_topic(db_pool):
    """Async factory fixture: create throwaway topics with auto-cleanup.

    Usage:
        topic_id = await make_topic(name="My Topic", keywords=["test"])
    """
    created: list[str] = []

    async def _factory(
        name: str = "Integration Test Topic",
        keywords: list[str] | None = None,
        signal_threshold: int = 2,
        status: str = "active",
    ) -> str:
        topic_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO topics (id, name, keywords, signal_threshold, status,
                                    created_at, updated_at, labels)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                topic_id, name, keywords or ["test", "integration"],
                signal_threshold, status, now, now, LABELS_JSON,
            )
        created.append(topic_id)
        return topic_id

    yield _factory

    # Cleanup in reverse order to handle FK dependencies
    async with db_pool.acquire() as conn:
        for tid in reversed(created):
            await conn.execute("DELETE FROM signals WHERE topic_id=$1", tid)
            await conn.execute("DELETE FROM narrative_clusters WHERE topic_id=$1", tid)
            await conn.execute("DELETE FROM content_items WHERE topic_id=$1", tid)
            await conn.execute("DELETE FROM topic_sources WHERE topic_id=$1", tid)
            await conn.execute("DELETE FROM topics WHERE id=$1", tid)


@pytest.fixture
async def make_source(db_pool):
    """Async factory fixture: create throwaway sources with auto-cleanup.

    Usage:
        source_id = await make_source(name="BBC", platform="web", score=80.0)
    """
    created: list[str] = []

    async def _factory(
        name: str = "Test Source",
        url_or_handle: str | None = None,
        platform: str = "web",
        credibility_score: float = 75.0,
    ) -> str:
        source_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        handle = url_or_handle or f"https://{source_id[:8]}.example.com"
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sources (
                    id, name, url_or_handle, platform, credibility_score,
                    created_at, updated_at, labels
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                source_id, name, handle, platform, credibility_score,
                now, now, LABELS_JSON,
            )
        created.append(source_id)
        return source_id

    yield _factory

    async with db_pool.acquire() as conn:
        for sid in reversed(created):
            await conn.execute("DELETE FROM sources WHERE id=$1", sid)


# ---------------------------------------------------------------------------
# Content item helper
# ---------------------------------------------------------------------------

async def insert_content_item(
    pool,
    topic_id: str,
    source_id: str,
    text: str,
    content_hash: str | None = None,
    url: str | None = None,
    embedding: list[float] | None = None,
    language: str = "en",
    cluster_id: str | None = None,
) -> str:
    """Insert a content_item directly (simulates scraper output).

    Returns the item_id. If content_hash collides, returns the id but row is a no-op.
    """
    import hashlib

    item_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    if content_hash is None:
        content_hash = hashlib.sha256(text.lower().strip().encode()).hexdigest()
    if url is None:
        url = f"https://example.com/test-{item_id[:8]}"

    async with pool.acquire() as conn:
        sql = """
            INSERT INTO content_items (
                id, topic_id, source_id, raw_text, clean_text, language,
                content_hash, url, captured_at, credibility_score_at_capture,
                {embedding_col}narrative_cluster_id,
                created_at, updated_at, labels
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,{embedding_val}$11,$12,$13,$14)
            ON CONFLICT(content_hash) DO NOTHING
        """
        if embedding is not None:
            embedding_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
            sql = sql.replace("{embedding_col}", "embedding, ")
            sql = sql.replace("{embedding_val}", f"'{embedding_str}'::vector, ")
        else:
            sql = sql.replace("{embedding_col}", "")
            sql = sql.replace("{embedding_val}", "")

        await conn.execute(
            sql,
            item_id, topic_id, source_id, text, text, language,
            content_hash, url, now, 75.0,
            cluster_id, now, now, LABELS_JSON,
        )
    return item_id
