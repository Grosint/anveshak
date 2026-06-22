"""Integration test — full pipeline integrity: scrape → analyse → cluster → signal.

This is the single most important integration test. It follows one piece of
content through the entire data pipeline and verifies each stage produces
correct output.

Requires: make up (PostgreSQL + Redis + Ollama running)
Target: < 60s on CPU
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, UTC

import pytest
import asyncpg

from tests.conftest import LABELS_JSON, POSTGRES_URL

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_pool():
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=3)
    yield pool
    await pool.close()


@pytest.fixture
async def pipeline_topic(db_pool):
    """Topic for full pipeline test."""
    topic_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
            VALUES ('org-integration-test', 'Integration Test Org', 'integration-test', NOW(), NOW(),
                    '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
        )
        await conn.execute(
            """
            INSERT INTO topics (id, name, keywords, signal_threshold, status,
                                created_at, updated_at, labels, org_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            topic_id, "Pipeline Integrity Test",
            ["defence", "military", "IAF"],
            2, "active", now, now, LABELS_JSON, "org-integration-test",
        )
    yield topic_id
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM signals WHERE topic_id=$1", topic_id)
        await conn.execute("DELETE FROM narrative_clusters WHERE topic_id=$1", topic_id)
        await conn.execute("DELETE FROM extracted_entities WHERE content_item_id IN (SELECT id FROM content_items WHERE topic_id=$1)", topic_id)
        await conn.execute("DELETE FROM content_items WHERE topic_id=$1", topic_id)
        await conn.execute("DELETE FROM topic_sources WHERE topic_id=$1", topic_id)
        await conn.execute("DELETE FROM topics WHERE id=$1", topic_id)


@pytest.fixture
async def pipeline_sources(db_pool):
    """Three sources from distinct platforms for signal threshold."""
    ids = {}
    platforms = {
        "web": "https://defence-news.example.com",
        "telegram": "t.me/defence_watch",
        "reddit": "r/IndianDefence",
    }
    for platform, handle in platforms.items():
        sid = str(uuid.uuid4())
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sources (id, name, url_or_handle, platform, credibility_score,
                                     created_at, updated_at, labels, org_id)
                VALUES ($1, $2, $3, $4, $5, NOW(), NOW(), $6::jsonb, $7)
                """,
                sid, f"Pipeline Source {platform}", handle, platform, 75.0, LABELS_JSON, "org-integration-test",
            )
        ids[platform] = sid
    yield ids
    for sid in ids.values():
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM sources WHERE id=$1", sid)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _insert_raw_content(
    pool, topic_id: str, source_id: str, text: str, embedding: list[float],
) -> str:
    """Insert content with pre-computed embedding (bypasses NLP for speed)."""
    item_id = str(uuid.uuid4())
    content_hash = hashlib.sha256(text.lower().strip().encode()).hexdigest()
    embedding_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO content_items (
                id, topic_id, source_id, raw_text, clean_text, language,
                content_hash, url, captured_at, credibility_score_at_capture,
                embedding, created_at, updated_at, labels, org_id
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'{embedding_str}'::vector,$11,$12,$13,$14)
            ON CONFLICT(content_hash) DO NOTHING
            """,
            item_id, topic_id, source_id, text, text, "en",
            content_hash, f"https://example.com/pipeline/{item_id[:8]}",
            now, 75.0, now, now, LABELS_JSON, "org-integration-test",
        )
    return item_id


def _similar_embedding(base: list[float], noise: float = 0.02) -> list[float]:
    """Generate a perturbed, L2-normalized embedding."""
    import random
    import math
    raw = [x + random.uniform(-noise, noise) for x in base]
    norm = math.sqrt(sum(x * x for x in raw))
    if norm == 0:
        return raw
    return [x / norm for x in raw]


def _normalize(vec: list[float]) -> list[float]:
    import math
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm > 0 else vec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_full_pipeline_scrape_to_signal(
    db_pool, pipeline_topic, pipeline_sources,
):
    """Full chain: insert content → cluster → signal fires → verify DB state."""
    from anveshak.analyst.clustering import run_clustering
    from anveshak.analyst.signal_engine import check_signals

    topic_id = pipeline_topic
    import random
    random.seed(42)
    # Create a realistic L2-normalized base embedding
    raw_base = [random.gauss(0.0, 1.0) for _ in range(384)]
    base_embedding = _normalize(raw_base)

    # STAGE 1: Insert content from 3 platforms (simulates scraper output)
    item_ids = []
    for platform, source_id in pipeline_sources.items():
        for i in range(4):  # 4 items per platform = 12 total (enough for HDBSCAN)
            emb = _similar_embedding(base_embedding, noise=0.05)
            item_id = await _insert_raw_content(
                db_pool, topic_id, source_id,
                f"IAF deploys Rafale jets in eastern sector, {platform} report #{i} {uuid.uuid4()}",
                emb,
            )
            item_ids.append(item_id)

    # Verify: all 12 items are in the database
    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM content_items WHERE topic_id=$1", topic_id
        )
    assert count == 12, f"Expected 12 content items, got {count}"

    # STAGE 2: Run clustering
    cluster_ids = await run_clustering(topic_id, db_pool)
    assert len(cluster_ids) >= 1, "At least one cluster should form"

    # Verify: at least one cluster meets signal threshold (ISC >= 2)
    async with db_pool.acquire() as conn:
        cluster_rows = await conn.fetch(
            """
            SELECT independent_source_count, item_count
            FROM narrative_clusters
            WHERE topic_id=$1 ORDER BY item_count DESC
            """,
            topic_id,
        )
    assert len(cluster_rows) >= 1, "At least one cluster should exist in DB"
    best = cluster_rows[0]
    assert best["independent_source_count"] >= 2, (
        f"Largest cluster should have ISC >= 2 (signal threshold), got {best['independent_source_count']}"
    )
    assert best["item_count"] >= 3, (
        f"Expected at least 3 items in largest cluster, got {best['item_count']}"
    )

    # STAGE 3: Check signals (threshold=2, ISC=3 → should fire)
    broadcast_payloads: list[dict] = []

    async def capture_broadcast(payload: dict) -> None:
        broadcast_payloads.append(payload)

    fired = await check_signals(db_pool, capture_broadcast)
    assert fired >= 1, "Signal should fire (ISC=3 >= threshold=2)"

    # Verify: signal exists in DB with correct structure
    async with db_pool.acquire() as conn:
        signal_row = await conn.fetchrow(
            "SELECT * FROM signals WHERE topic_id=$1 ORDER BY created_at DESC LIMIT 1",
            topic_id,
        )
    assert signal_row is not None, "Signal should be written to DB"
    assert signal_row["status"] == "new"
    assert signal_row["signal_type"] == "multi_source_convergence"

    # Verify: broadcast payload has required fields
    assert len(broadcast_payloads) >= 1
    payload = broadcast_payloads[0]
    assert payload["type"] == "signal"
    assert "signal_id" in payload
    assert "topic_id" in payload
    assert "severity" in payload


async def test_content_dedup_prevents_double_counting(db_pool, pipeline_topic, pipeline_sources):
    """Same content_hash inserted twice → exactly one row (ON CONFLICT)."""
    source_id = list(pipeline_sources.values())[0]
    text = "Identical text for dedup test — should only appear once."
    content_hash = hashlib.sha256(text.lower().strip().encode()).hexdigest()

    for _ in range(3):  # Insert same text 3 times
        item_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO content_items (
                    id, topic_id, source_id, raw_text, clean_text, language,
                    content_hash, url, captured_at, credibility_score_at_capture,
                    created_at, updated_at, labels, org_id
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                ON CONFLICT(content_hash) DO NOTHING
                """,
                item_id, pipeline_topic, source_id, text, text, "en",
                content_hash, f"https://example.com/dedup/{uuid.uuid4()}",
                now, 75.0, now, now, LABELS_JSON, "org-integration-test",
            )

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM content_items WHERE content_hash=$1", content_hash
        )
    assert count == 1, f"Dedup failed: expected 1 row, got {count}"
