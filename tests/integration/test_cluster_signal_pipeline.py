"""Integration test: items → cluster → signal → WebSocket (Phase 2, criteria 2.33).

pytest.mark.integration — requires running Docker Compose services:
  make up

Run with:
  uv run --package anveshak-tests pytest tests/integration/test_cluster_signal_pipeline.py -v -m integration

Tests:
  - 5+ items from 3 platforms → cluster forms (criteria 2.26)
  - independent_source_count reflects platform diversity, not item count (criteria 2.27)
  - signal_threshold=2, 2 platforms → signal fires (criteria 2.28)
  - WebSocket delivery loop delivers signal within 10s (criteria 2.29)
  - Duplicate scrape → no duplicate signal within 24h (criteria 2.30)
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, UTC
from unittest.mock import AsyncMock

import pytest
import asyncpg

from anveshak.analyst.clustering import count_independent_sources, run_clustering
from anveshak.analyst.signal_engine import check_signals, is_duplicate_signal

POSTGRES_URL = os.environ.get("POSTGRES_URL", "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_pool():
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=3)
    yield pool
    await pool.close()


@pytest.fixture
async def topic_threshold_2(db_pool):
    """Topic with signal_threshold=2 to trigger signal on 2 platforms."""
    topic_id = str(uuid.uuid4())
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO topics (id, name, keywords, signal_threshold, status,
                                created_at, updated_at, labels)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
            topic_id, "Cluster Signal Test Topic", ["defence", "IAF"],
            2, "active",
            datetime.now(UTC), datetime.now(UTC),
            '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}',
        )
    yield topic_id
    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM signals WHERE topic_id=$1", topic_id
        )
        await conn.execute(
            "DELETE FROM narrative_clusters WHERE topic_id=$1", topic_id
        )
        await conn.execute(
            "DELETE FROM content_items WHERE topic_id=$1", topic_id
        )
        await conn.execute("DELETE FROM topics WHERE id=$1", topic_id)


@pytest.fixture
async def sources_three_platforms(db_pool):
    """Three sources from distinct platforms."""
    ids = {}
    platforms = {"telegram": "t.me/iaf_news", "reddit": "r/IndianDefence", "web": "https://indiandefence.com"}
    for platform, handle in platforms.items():
        sid = str(uuid.uuid4())
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO sources (id, name, url_or_handle, platform, credibility_score,
                                     created_at, updated_at, labels)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                sid, f"Source {platform}", handle, platform, 70.0,
                datetime.now(UTC), datetime.now(UTC),
                '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}',
            )
        ids[platform] = sid
    yield ids
    for sid in ids.values():
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM sources WHERE id=$1", sid)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def insert_item_with_embedding(
    pool: asyncpg.Pool,
    topic_id: str,
    source_id: str,
    text: str,
    url: str,
    embedding: list[float],
) -> str:
    """Insert a content_item with a pre-computed embedding (bypasses NLP for speed)."""
    import hashlib
    item_id = str(uuid.uuid4())
    content_hash = hashlib.sha256(text.lower().encode()).hexdigest()
    embedding_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO content_items (
                id, topic_id, source_id, raw_text, clean_text, language,
                content_hash, url, captured_at, credibility_score_at_capture,
                embedding, created_at, updated_at, labels
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::vector,$12,$13,$14)
            ON CONFLICT(content_hash) DO NOTHING
        """,
            item_id, topic_id, source_id, text, text, "en",
            content_hash, url, now, 70.0, embedding_str, now, now,
            '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}',
        )
    return item_id


def _similar_embedding(base: list[float], noise: float = 0.02) -> list[float]:
    """Generate a slightly perturbed embedding to ensure items cluster together."""
    import random
    return [x + random.uniform(-noise, noise) for x in base]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_cluster_forms_from_multi_platform_items(
    db_pool, topic_threshold_2, sources_three_platforms
):
    """Criteria 2.26: 5+ items from 3 platforms → cluster forms."""
    # Base embedding — all items close in semantic space → single cluster
    base = [0.1] * 384

    items_inserted = 0
    for platform, source_id in sources_three_platforms.items():
        for i in range(2):
            emb = _similar_embedding(base)
            await insert_item_with_embedding(
                pool=db_pool,
                topic_id=topic_threshold_2,
                source_id=source_id,
                text=f"IAF Rafale deployment news {platform} {i} {uuid.uuid4()}",
                url=f"https://example.com/{platform}/{i}/{uuid.uuid4()}",
                embedding=emb,
            )
            items_inserted += 1

    assert items_inserted >= 5

    cluster_ids = await run_clustering(topic_threshold_2, db_pool)
    assert len(cluster_ids) >= 1, "At least one cluster should form from semantically similar items"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_independent_source_count_reflects_platforms(
    db_pool, topic_threshold_2, sources_three_platforms
):
    """Criteria 2.27: independent_source_count = platform diversity, not item count."""
    base = [0.2] * 384

    for platform, source_id in sources_three_platforms.items():
        for i in range(3):  # 3 items per platform = 9 items total
            emb = _similar_embedding(base)
            await insert_item_with_embedding(
                pool=db_pool,
                topic_id=topic_threshold_2,
                source_id=source_id,
                text=f"Cross-platform defence story {platform} item {i} {uuid.uuid4()}",
                url=f"https://example.com/cross/{platform}/{i}/{uuid.uuid4()}",
                embedding=emb,
            )

    await run_clustering(topic_threshold_2, db_pool)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT independent_source_count, item_count
            FROM narrative_clusters
            WHERE topic_id = $1
            ORDER BY item_count DESC
            LIMIT 1
        """, topic_threshold_2)

    assert rows, "At least one cluster should exist"
    best = rows[0]
    # 3 distinct platforms → independent_source_count should be 3
    assert best["independent_source_count"] == 3, (
        f"Expected 3 independent sources, got {best['independent_source_count']}"
    )
    # item_count should be total items, not platform count
    assert best["item_count"] > best["independent_source_count"], (
        "item_count should exceed platform count (9 items vs 3 platforms)"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_signal_fires_when_threshold_met(
    db_pool, topic_threshold_2, sources_three_platforms
):
    """Criteria 2.28: threshold=2, 2+ platforms → signal fires."""
    base = [0.3] * 384

    # Insert items from 2 platforms only
    platform_list = list(sources_three_platforms.items())[:2]
    for platform, source_id in platform_list:
        for i in range(2):
            emb = _similar_embedding(base)
            await insert_item_with_embedding(
                pool=db_pool,
                topic_id=topic_threshold_2,
                source_id=source_id,
                text=f"Signal threshold test {platform} {i} {uuid.uuid4()}",
                url=f"https://example.com/threshold/{platform}/{i}/{uuid.uuid4()}",
                embedding=emb,
            )

    await run_clustering(topic_threshold_2, db_pool)

    broadcast_calls: list[dict] = []

    async def capture_broadcast(payload: dict) -> None:
        broadcast_calls.append(payload)

    fired = await check_signals(db_pool, capture_broadcast)

    assert fired >= 1, "Signal should fire when independent_source_count >= threshold"
    assert len(broadcast_calls) >= 1, "Broadcast should have been called"
    assert broadcast_calls[0]["type"] == "signal"
    assert "signal_id" in broadcast_calls[0]
    assert "topic_id" in broadcast_calls[0]
    assert "severity" in broadcast_calls[0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_duplicate_signal_within_24h(
    db_pool, topic_threshold_2, sources_three_platforms
):
    """Criteria 2.30: second clustering run does NOT create duplicate signal."""
    base = [0.4] * 384

    for platform, source_id in list(sources_three_platforms.items())[:2]:
        for i in range(2):
            emb = _similar_embedding(base)
            await insert_item_with_embedding(
                pool=db_pool,
                topic_id=topic_threshold_2,
                source_id=source_id,
                text=f"Dedup signal test {platform} {i} {uuid.uuid4()}",
                url=f"https://example.com/dedup/{platform}/{i}/{uuid.uuid4()}",
                embedding=emb,
            )

    # First pass — cluster + signal
    await run_clustering(topic_threshold_2, db_pool)

    broadcast_1: list[dict] = []
    await check_signals(db_pool, lambda p: broadcast_1.append(p) or __import__('asyncio').sleep(0))

    async def noop(p): pass  # noqa: E704

    # Second pass — same clusters, same threshold — should NOT duplicate
    broadcast_2: list[dict] = []
    await check_signals(db_pool, lambda p: broadcast_2.append(p) or __import__('asyncio').sleep(0))

    async with db_pool.acquire() as conn:
        signal_count = await conn.fetchval("""
            SELECT COUNT(*) FROM signals
            WHERE topic_id = $1
              AND signal_type = 'multi_source_convergence'
        """, topic_threshold_2)

    # Signals created on second pass should all be deduplicated
    assert signal_count == len(broadcast_1), (
        f"Duplicate signals created: {signal_count} in DB vs {len(broadcast_1)} on first pass"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_signal_delivery_loop_pushes_within_10s(
    db_pool, topic_threshold_2, sources_three_platforms
):
    """Criteria 2.29: WebSocket delivery loop delivers a signal within 10 seconds.

    Simulates the API's signal_delivery_loop running alongside the analyst's
    signal_engine: after a cluster fires a signal (stored in DB with
    delivered_at=NULL), the delivery loop detects it and calls broadcast within
    the poll interval (≤5s) + processing overhead (≤5s) = ≤10s.
    """
    from anveshak.api.signal_delivery import signal_delivery_loop

    base = [0.5] * 384

    for platform, source_id in list(sources_three_platforms.items())[:2]:
        for i in range(2):
            emb = _similar_embedding(base)
            await insert_item_with_embedding(
                pool=db_pool,
                topic_id=topic_threshold_2,
                source_id=source_id,
                text=f"WS timing test {platform} {i} {uuid.uuid4()}",
                url=f"https://example.com/ws/{platform}/{i}/{uuid.uuid4()}",
                embedding=emb,
            )

    # Write signal to DB (analyst side — delivered_at=NULL)
    await run_clustering(topic_threshold_2, db_pool)
    async def noop(_): pass
    await check_signals(db_pool, noop)

    # Confirm at least one undelivered signal exists
    async with db_pool.acquire() as conn:
        undelivered = await conn.fetchval(
            "SELECT COUNT(*) FROM signals WHERE topic_id=$1 AND delivered_at IS NULL",
            topic_threshold_2,
        )
    assert undelivered >= 1, "Precondition: at least one undelivered signal must exist"

    # Run signal_delivery_loop in background; capture broadcast calls
    delivered: list[dict] = []

    async def capture_broadcast(payload: dict) -> None:
        delivered.append(payload)

    loop_task = asyncio.create_task(signal_delivery_loop(db_pool, capture_broadcast))

    try:
        # Wait up to 10 seconds for delivery (criterion 2.29)
        await asyncio.wait_for(
            _wait_for_delivery(delivered),
            timeout=10.0,
        )
    except asyncio.TimeoutError:
        pytest.fail("Signal was not delivered via WebSocket loop within 10 seconds (criterion 2.29)")
    finally:
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass

    assert len(delivered) >= 1
    assert delivered[0]["type"] == "signal"
    assert "signal_id" in delivered[0]
    assert "severity" in delivered[0]


async def _wait_for_delivery(delivered: list, poll_interval: float = 0.1) -> None:
    """Poll until at least one signal has been delivered."""
    while not delivered:
        await asyncio.sleep(poll_interval)
