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
    "POSTGRES_TEST_URL",
    "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak_test",
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

TEST_ORG_ID = "org-integration-test"


@pytest.fixture
async def ensure_org(db_pool):
    """Ensure a test organization exists for integration tests."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
            VALUES ($1, 'Integration Test Org', 'integration-test', NOW(), NOW(), $2)
            ON CONFLICT (id) DO NOTHING
            """,
            TEST_ORG_ID, LABELS_JSON,
        )
    return TEST_ORG_ID


@pytest.fixture
async def make_topic(db_pool, ensure_org):
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
        org_id: str = TEST_ORG_ID,
    ) -> str:
        topic_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO topics (id, name, keywords, signal_threshold, status,
                                    org_id, created_at, updated_at, labels)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                topic_id, name, keywords or ["test", "integration"],
                signal_threshold, status, org_id, now, now, LABELS_JSON,
            )
        created.append(topic_id)
        return topic_id

    yield _factory

    # Cleanup in reverse FK order (deepest children first)
    async with db_pool.acquire() as conn:
        for tid in reversed(created):
            # vision_results → media_assets → content_items
            await conn.execute(
                "DELETE FROM vision_results WHERE media_asset_id IN "
                "(SELECT id FROM media_assets WHERE content_item_id IN "
                "(SELECT id FROM content_items WHERE topic_id=$1))", tid)
            await conn.execute(
                "DELETE FROM media_assets WHERE content_item_id IN "
                "(SELECT id FROM content_items WHERE topic_id=$1)", tid)
            # extracted_entities → content_items
            await conn.execute(
                "DELETE FROM extracted_entities WHERE content_item_id IN "
                "(SELECT id FROM content_items WHERE topic_id=$1)", tid)
            # report_source_warnings → reports
            await conn.execute(
                "DELETE FROM report_source_warnings WHERE report_id IN "
                "(SELECT id FROM reports WHERE topic_id=$1)", tid)
            await conn.execute("DELETE FROM reports WHERE topic_id=$1", tid)
            # near_duplicates → content_items
            await conn.execute(
                "DELETE FROM near_duplicates WHERE content_item_a_id IN "
                "(SELECT id FROM content_items WHERE topic_id=$1) "
                "OR content_item_b_id IN "
                "(SELECT id FROM content_items WHERE topic_id=$1)", tid)
            await conn.execute("DELETE FROM signals WHERE topic_id=$1", tid)
            # Engine C: identifier_cluster_items → identifier_clusters
            await conn.execute(
                "DELETE FROM identifier_cluster_items WHERE identifier_cluster_id IN "
                "(SELECT id FROM identifier_clusters WHERE topic_id=$1)", tid)
            await conn.execute("DELETE FROM identifier_clusters WHERE topic_id=$1", tid)
            # Engine C: topic_templates
            await conn.execute("DELETE FROM topic_templates WHERE topic_id=$1", tid)
            # nullify cluster FK before deleting clusters
            await conn.execute(
                "UPDATE content_items SET narrative_cluster_id = NULL "
                "WHERE topic_id=$1 AND narrative_cluster_id IS NOT NULL", tid)
            await conn.execute("DELETE FROM narrative_clusters WHERE topic_id=$1", tid)
            await conn.execute("DELETE FROM topic_content_items WHERE topic_id=$1", tid)
            await conn.execute("DELETE FROM content_items WHERE topic_id=$1", tid)
            await conn.execute("DELETE FROM topic_sources WHERE topic_id=$1", tid)
            await conn.execute("DELETE FROM discovered_sources WHERE topic_id=$1", tid)
            await conn.execute("DELETE FROM catalog_approvals WHERE topic_id=$1", tid)
            await conn.execute("DELETE FROM analysis_jobs WHERE topic_id=$1", tid)
            await conn.execute("DELETE FROM topics WHERE id=$1", tid)


@pytest.fixture
async def make_source(db_pool, ensure_org):
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
        org_id: str = TEST_ORG_ID,
    ) -> str:
        source_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        handle = url_or_handle or f"https://{source_id[:8]}.example.com"
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sources (
                    id, name, url_or_handle, platform, credibility_score,
                    org_id, created_at, updated_at, labels
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                source_id, name, handle, platform, credibility_score,
                org_id, now, now, LABELS_JSON,
            )
        created.append(source_id)
        return source_id

    yield _factory

    async with db_pool.acquire() as conn:
        for sid in reversed(created):
            await conn.execute("DELETE FROM credibility_audit_log WHERE source_id=$1", sid)
            await conn.execute("DELETE FROM report_source_warnings WHERE source_id=$1", sid)
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
    org_id: str = TEST_ORG_ID,
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
                org_id, created_at, updated_at, labels
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,{embedding_val}$11,$12,$13,$14,$15)
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
            cluster_id, org_id, now, now, LABELS_JSON,
        )
    return item_id
