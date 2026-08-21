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
import hashlib
import math
import random
import uuid
from datetime import UTC, datetime

import asyncpg
import pytest
from anveshak.analyst.clustering import run_clustering
from anveshak.analyst.signal_engine import check_signals

# ---------------------------------------------------------------------------
# Fixtures (using root conftest make_topic / make_source)
# ---------------------------------------------------------------------------


@pytest.fixture
async def topic_threshold_2(make_topic):
    """Topic with signal_threshold=2 to trigger signal on 2 platforms."""
    return await make_topic(
        name="Cluster Signal Test Topic",
        keywords=["defence", "IAF"],
        signal_threshold=2,
    )


@pytest.fixture
async def sources_three_platforms(make_source):
    """Three sources from distinct platforms."""
    ids = {}
    platforms = {
        "telegram": "t.me/iaf_news",
        "reddit": "r/IndianDefence",
        "web": "https://indiandefence.com",
    }
    for platform, handle in platforms.items():
        sid = await make_source(
            name=f"Source {platform}",
            url_or_handle=handle,
            platform=platform,
            credibility_score=70.0,
        )
        ids[platform] = sid
    return ids


@pytest.fixture
async def sources_four_platforms(make_source):
    """Four sources from distinct platforms for production-load test."""
    ids = {}
    platforms = {
        "telegram": "t.me/defence_news",
        "reddit": "r/IndianMilitary",
        "web": "https://defencenews.in",
        "bluesky": "defence.bsky.social",
    }
    for platform, handle in platforms.items():
        sid = await make_source(
            name=f"Source {platform}",
            url_or_handle=handle,
            platform=platform,
            credibility_score=70.0,
        )
        ids[platform] = sid
    return ids


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
    item_id = str(uuid.uuid4())
    content_hash = hashlib.sha256(text.lower().encode()).hexdigest()
    embedding_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO content_items (
                id, topic_id, source_id, raw_text, clean_text, language,
                content_hash, url, captured_at, credibility_score_at_capture,
                embedding, created_at, updated_at, labels, org_id
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::vector,$12,$13,$14,$15)
            ON CONFLICT(content_hash) DO NOTHING
        """,
            item_id,
            topic_id,
            source_id,
            text,
            text,
            "en",
            content_hash,
            url,
            now,
            70.0,
            embedding_str,
            now,
            now,
            '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}',
            "org-integration-test",
        )
    return item_id


def _l2_normalize(vec: list[float]) -> list[float]:
    """L2-normalize a vector to unit length (matching sentence-transformers output)."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def _random_base(seed: int, dim: int = 384) -> list[float]:
    """Generate a diverse, L2-normalized base vector (mimics sentence-transformers)."""
    _rng = random.Random(seed)
    vec = [_rng.gauss(0, 1) for _ in range(dim)]
    return _l2_normalize(vec)


def _similar_embedding(base: list[float], noise: float = 0.03) -> list[float]:
    """Generate a perturbed, L2-normalized embedding that clusters together."""
    perturbed = [x + random.uniform(-noise, noise) for x in base]
    return _l2_normalize(perturbed)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cluster_forms_from_multi_platform_items(
    db_pool, topic_threshold_2, sources_three_platforms
):
    """Criteria 2.26: 5+ items from 3 platforms → cluster forms."""
    base = _random_base(seed=101)

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
    base = _random_base(seed=202)

    for platform, source_id in sources_three_platforms.items():
        for i in range(5):  # 5 items per platform = 15 items total
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
        rows = await conn.fetch(
            """
            SELECT independent_source_count, item_count
            FROM narrative_clusters
            WHERE topic_id = $1
            ORDER BY item_count DESC
            LIMIT 1
        """,
            topic_threshold_2,
        )

    assert rows, "At least one cluster should exist"
    best = rows[0]
    assert best["independent_source_count"] == 3, (
        f"Expected 3 independent sources, got {best['independent_source_count']}"
    )
    assert best["item_count"] > best["independent_source_count"], (
        "item_count should exceed platform count (9 items vs 3 platforms)"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_signal_fires_when_threshold_met(db_pool, topic_threshold_2, sources_three_platforms):
    """Criteria 2.28: threshold=2, 2+ platforms → signal fires."""
    base = _random_base(seed=303)

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
async def test_no_duplicate_signal_within_24h(db_pool, topic_threshold_2, sources_three_platforms):
    """Criteria 2.30: second clustering run does NOT create duplicate signal."""
    base = _random_base(seed=404)

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
    await check_signals(db_pool, lambda p: broadcast_1.append(p) or __import__("asyncio").sleep(0))

    async def noop(p):
        pass  # noqa: E704

    # Second pass — same clusters, same threshold — should NOT duplicate
    broadcast_2: list[dict] = []
    await check_signals(db_pool, lambda p: broadcast_2.append(p) or __import__("asyncio").sleep(0))

    async with db_pool.acquire() as conn:
        signal_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM signals
            WHERE topic_id = $1
              AND signal_type = 'multi_source_convergence'
        """,
            topic_threshold_2,
        )

    # Signals created on second pass should all be deduplicated
    assert signal_count == len(broadcast_1), (
        f"Duplicate signals created: {signal_count} in DB vs {len(broadcast_1)} on first pass"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_signal_delivery_loop_pushes_within_10s(
    db_pool, topic_threshold_2, sources_three_platforms
):
    """Criteria 2.29: WebSocket delivery loop delivers a signal within 10 seconds."""
    from anveshak.api.signal_delivery import signal_delivery_loop

    base = _random_base(seed=505)

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

    async def noop(_):
        pass

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
        await asyncio.wait_for(
            _wait_for_delivery(delivered),
            timeout=10.0,
        )
    except asyncio.TimeoutError:
        pytest.fail(
            "Signal was not delivered via WebSocket loop within 10 seconds (criterion 2.29)"
        )
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


# ---------------------------------------------------------------------------
# Scenario 2: Production load — 100 articles across 5 narratives
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_production_load_100_articles_5_narratives(
    db_pool, topic_threshold_2, sources_four_platforms
):
    """Scenario 2: 100 articles from 5 narratives across 4 platforms."""
    import time

    narrative_seeds = [1001, 1002, 1003, 1004, 1005]
    platforms = list(sources_four_platforms.keys())
    items_inserted = 0

    for seed in narrative_seeds:
        base = _random_base(seed=seed)
        for platform in platforms:
            source_id = sources_four_platforms[platform]
            for i in range(5):
                emb = _similar_embedding(base)
                await insert_item_with_embedding(
                    pool=db_pool,
                    topic_id=topic_threshold_2,
                    source_id=source_id,
                    text=f"Narrative {seed} {platform} article {i} {uuid.uuid4()}",
                    url=f"https://example.com/prod/{seed}/{platform}/{i}/{uuid.uuid4()}",
                    embedding=emb,
                )
                items_inserted += 1

    assert items_inserted == 100

    start = time.monotonic()
    cluster_ids = await run_clustering(topic_threshold_2, db_pool)
    elapsed = time.monotonic() - start

    assert len(cluster_ids) == 5, f"Expected 5 clusters, got {len(cluster_ids)}"
    assert elapsed < 2.0, f"Clustering took {elapsed:.2f}s, expected <2s"

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT independent_source_count, item_count
            FROM narrative_clusters
            WHERE topic_id = $1
            ORDER BY item_count DESC
        """,
            topic_threshold_2,
        )

    assert len(rows) == 5
    for row in rows:
        assert row["independent_source_count"] == 4, (
            f"Expected ISC=4, got {row['independent_source_count']}"
        )
        assert row["item_count"] == 20, f"Expected 20 items per cluster, got {row['item_count']}"


# ---------------------------------------------------------------------------
# Scenario 5: Incremental arrival
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_incremental_arrival_new_batch(db_pool, topic_threshold_2, sources_three_platforms):
    """Scenario 5: existing clusters + new batch → correct assignment."""
    base = _random_base(seed=5001)

    # Phase 1: insert 10 items, cluster
    for platform, source_id in sources_three_platforms.items():
        for i in range(3):
            emb = _similar_embedding(base)
            await insert_item_with_embedding(
                pool=db_pool,
                topic_id=topic_threshold_2,
                source_id=source_id,
                text=f"Phase1 {platform} {i} {uuid.uuid4()}",
                url=f"https://example.com/incr/p1/{platform}/{i}/{uuid.uuid4()}",
                embedding=emb,
            )
    emb = _similar_embedding(base)
    first_platform = list(sources_three_platforms.keys())[0]
    first_source = sources_three_platforms[first_platform]
    await insert_item_with_embedding(
        pool=db_pool,
        topic_id=topic_threshold_2,
        source_id=first_source,
        text=f"Phase1 extra {uuid.uuid4()}",
        url=f"https://example.com/incr/p1/extra/{uuid.uuid4()}",
        embedding=emb,
    )

    cluster_ids_p1 = await run_clustering(topic_threshold_2, db_pool)
    assert len(cluster_ids_p1) >= 1, "Phase 1 should form at least 1 cluster"

    # Phase 2: insert 4 more similar items
    for i in range(4):
        emb = _similar_embedding(base)
        await insert_item_with_embedding(
            pool=db_pool,
            topic_id=topic_threshold_2,
            source_id=first_source,
            text=f"Phase2 new {i} {uuid.uuid4()}",
            url=f"https://example.com/incr/p2/{i}/{uuid.uuid4()}",
            embedding=emb,
        )

    await run_clustering(topic_threshold_2, db_pool)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT item_count FROM narrative_clusters
            WHERE topic_id = $1
        """,
            topic_threshold_2,
        )

    total_items = sum(r["item_count"] for r in rows)
    assert total_items == 14, f"Expected 14 total items (10+4), got {total_items}"
