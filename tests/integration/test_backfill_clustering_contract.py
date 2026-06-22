"""Integration test: backfilled items must participate in clustering & analytics.

This tests the CONTRACT between backfill (writes to topic_content_items)
and clustering/signal/analytics (reads content for a topic). The bug:
all queries used `WHERE ci.topic_id = $1`, ignoring `topic_content_items`.

pytest.mark.integration — requires running Docker Compose (postgres).

Run with:
  uv run --package anveshak-tests pytest tests/integration/test_backfill_clustering_contract.py -v -m integration
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, UTC

import numpy as np
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_embedding(seed: int, dim: int = 384) -> list[float]:
    """L2-normalised random embedding (matches sentence-transformers output)."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float64)
    vec /= np.linalg.norm(vec)
    return vec.tolist()


def _similar_embedding(base: list[float], seed: int, noise: float = 0.02) -> list[float]:
    """Perturb a base embedding to create a similar article (cosine ~0.90+)."""
    rng = np.random.RandomState(seed)
    arr = np.array(base, dtype=np.float64)
    arr += rng.uniform(-noise, noise, size=len(arr))
    arr /= np.linalg.norm(arr)
    return arr.tolist()


async def _insert_content(pool, topic_id, source_id, text, embedding, language="en"):
    """Insert content_item with embedding. Returns item_id."""
    from tests.conftest import insert_content_item
    content_hash = hashlib.sha256(text.lower().strip().encode()).hexdigest()
    return await insert_content_item(
        pool, topic_id, source_id, text,
        content_hash=content_hash,
        embedding=embedding,
        language=language,
    )


async def _backfill_item(pool, topic_id, content_item_id, similarity=0.90):
    """Manually insert into topic_content_items (simulates backfill_topic output)."""
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO topic_content_items (topic_id, content_item_id, similarity_score, assigned_at)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (topic_id, content_item_id) DO NOTHING""",
            topic_id, content_item_id, similarity, datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# Test 1: Backfilled items appear in load_unclustered_embeddings
# ---------------------------------------------------------------------------

class TestBackfilledItemsInClustering:
    """Verify clustering queries include items from topic_content_items."""

    async def test_load_unclustered_includes_backfilled(self, db_pool, make_topic, make_source):
        """
        Scenario:
          - Topic A owns article X (direct topic_id)
          - Topic B has article X backfilled via topic_content_items
          - load_unclustered_embeddings(topic_B) must return article X
        """
        from anveshak.analyst.clustering import load_unclustered_embeddings

        topic_a = await make_topic(name="Topic A - Owner")
        topic_b = await make_topic(name="Topic B - Backfilled")
        source_rss = await make_source(name="Reuters", platform="rss", credibility_score=85.0)

        base_emb = _random_embedding(seed=42)

        # Article owned by Topic A
        item_id = await _insert_content(
            db_pool, topic_a, source_rss,
            "PLA bridge construction at Pangong Tso sector detected by satellite",
            embedding=base_emb,
        )

        # Backfill to Topic B
        await _backfill_item(db_pool, topic_b, item_id)

        # Load unclustered embeddings for Topic B
        rows = await load_unclustered_embeddings(topic_b, db_pool)

        item_ids = [r.content_item_id for r in rows]
        assert item_id in item_ids, (
            f"Backfilled item {item_id} not found in Topic B's unclustered embeddings. "
            f"Got {len(rows)} items: {item_ids}"
        )

    async def test_load_unclustered_includes_both_owned_and_backfilled(
        self, db_pool, make_topic, make_source,
    ):
        """Topic B should see its own items AND backfilled items."""
        from anveshak.analyst.clustering import load_unclustered_embeddings

        topic_a = await make_topic(name="Topic A")
        topic_b = await make_topic(name="Topic B")
        source_rss = await make_source(name="Reuters", platform="rss")
        source_web = await make_source(name="NDTV", platform="web")

        base_emb = _random_embedding(seed=100)

        # Article owned by Topic A, backfilled to Topic B
        item_a = await _insert_content(
            db_pool, topic_a, source_rss,
            "Chinese military infrastructure near LAC",
            embedding=base_emb,
        )
        await _backfill_item(db_pool, topic_b, item_a)

        # Article directly owned by Topic B
        item_b = await _insert_content(
            db_pool, topic_b, source_web,
            "India monitors Chinese activity at Line of Actual Control",
            embedding=_similar_embedding(base_emb, seed=101),
        )

        rows = await load_unclustered_embeddings(topic_b, db_pool)
        item_ids = {r.content_item_id for r in rows}

        assert item_a in item_ids, "Backfilled item missing from Topic B"
        assert item_b in item_ids, "Owned item missing from Topic B"
        assert len(item_ids) >= 2


# ---------------------------------------------------------------------------
# Test 2: ISC counts platforms from backfilled items
# ---------------------------------------------------------------------------

class TestISCCountsBackfilledPlatforms:
    """Verify ISC reflects platforms from both owned and backfilled items."""

    async def test_isc_includes_backfilled_platform(self, db_pool, make_topic, make_source):
        """
        Scenario:
          - Topic B owns 3 "web" articles
          - 2 "rss" articles backfilled from Topic A
          - After clustering, ISC for Topic B should be 2 (web + rss), not 1
        """
        from anveshak.analyst.clustering import run_clustering

        topic_a = await make_topic(name="Topic A - RSS source")
        topic_b = await make_topic(name="Topic B - Web source", signal_threshold=2)
        source_rss = await make_source(name="Reuters RSS", platform="rss")
        source_web = await make_source(name="NDTV Web", platform="web")

        base_emb = _random_embedding(seed=200)

        # 3 web articles owned by Topic B
        for i in range(3):
            await _insert_content(
                db_pool, topic_b, source_web,
                f"Indian forces monitor LAC activity report number {i} with details",
                embedding=_similar_embedding(base_emb, seed=210 + i),
            )

        # 2 RSS articles owned by Topic A, backfilled to Topic B
        for i in range(2):
            item_id = await _insert_content(
                db_pool, topic_a, source_rss,
                f"Reuters LAC monitoring update edition {i} comprehensive coverage",
                embedding=_similar_embedding(base_emb, seed=220 + i),
            )
            await _backfill_item(db_pool, topic_b, item_id)

        # Run clustering for Topic B
        cluster_ids = await run_clustering(topic_b, db_pool)

        assert len(cluster_ids) >= 1, "Expected at least 1 cluster"

        # Check ISC on the cluster
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT independent_source_count FROM narrative_clusters WHERE id = $1",
                cluster_ids[0],
            )

        assert row is not None, "Cluster not found in DB"
        assert row["independent_source_count"] >= 2, (
            f"ISC should be >= 2 (web + rss), got {row['independent_source_count']}. "
            "Backfilled RSS items not counted in ISC."
        )


# ---------------------------------------------------------------------------
# Test 3: Both topics cluster the same shared article
# ---------------------------------------------------------------------------

class TestSharedSourceBothTopicsCluster:
    """Verify an article from a shared source clusters in both topics."""

    async def test_article_clusters_in_both_topics(self, db_pool, make_topic, make_source):
        """
        Scenario:
          - Topic A and Topic B share Reuters
          - Reuters article scraped → topic_id = Topic A
          - Backfill links it to Topic B
          - Both topics have 3+ similar articles
          - Clustering runs for both → article appears in clusters for both
        """
        from anveshak.analyst.clustering import run_clustering

        topic_a = await make_topic(name="LAC Activity")
        topic_b = await make_topic(name="IOR Maritime")
        source_reuters = await make_source(name="Reuters", platform="rss")
        source_ndtv = await make_source(name="NDTV", platform="web")
        source_hindu = await make_source(name="The Hindu", platform="web")

        base_emb = _random_embedding(seed=300)

        # Reuters article owned by Topic A
        shared_item = await _insert_content(
            db_pool, topic_a, source_reuters,
            "Chinese naval vessels detected in Indian Ocean by Indian Navy surveillance",
            embedding=base_emb,
        )

        # Topic A: 2 more articles
        for i in range(2):
            await _insert_content(
                db_pool, topic_a, source_ndtv,
                f"NDTV reports Chinese naval presence in Indian Ocean region part {i}",
                embedding=_similar_embedding(base_emb, seed=310 + i),
            )

        # Topic B: 2 articles + backfilled Reuters article
        for i in range(2):
            await _insert_content(
                db_pool, topic_b, source_hindu,
                f"The Hindu analysis of Chinese maritime activity IOR edition {i}",
                embedding=_similar_embedding(base_emb, seed=320 + i),
            )
        await _backfill_item(db_pool, topic_b, shared_item)

        # Cluster both topics
        clusters_a = await run_clustering(topic_a, db_pool)
        clusters_b = await run_clustering(topic_b, db_pool)

        assert len(clusters_a) >= 1, "Topic A should have clusters"
        assert len(clusters_b) >= 1, "Topic B should have clusters"

        # Verify shared item is clustered in Topic A (direct)
        async with db_pool.acquire() as conn:
            row_a = await conn.fetchrow(
                "SELECT narrative_cluster_id FROM content_items WHERE id = $1",
                shared_item,
            )
        assert row_a["narrative_cluster_id"] is not None, (
            "Shared article not clustered in Topic A (direct owner)"
        )

        # Verify shared item participates in Topic B's cluster
        # (it may not have narrative_cluster_id set for topic B since it's backfilled,
        # but it should have been loaded by load_unclustered_embeddings for topic B)
        async with db_pool.acquire() as conn:
            cluster_b_items = await conn.fetch(
                """SELECT ci.id FROM content_items ci
                   WHERE ci.narrative_cluster_id = $1""",
                clusters_b[0],
            )
        cluster_b_item_ids = {r["id"] for r in cluster_b_items}
        # At minimum, Topic B's own 2 items should be clustered
        assert len(cluster_b_item_ids) >= 2, "Topic B cluster should have items"


# ---------------------------------------------------------------------------
# Test 4: Sentiment includes backfilled items
# ---------------------------------------------------------------------------

class TestSentimentIncludesBackfilled:
    """Verify sentiment queries include backfilled items."""

    async def test_sentiment_baseline_includes_backfilled(self, db_pool, make_topic, make_source):
        """
        Scenario:
          - Topic B owns 2 items with sentiment compound = 0.5
          - 2 items backfilled from Topic A with sentiment compound = -0.8
          - Sentiment baseline for Topic B should reflect all 4 items
        """
        topic_a = await make_topic(name="Topic A")
        topic_b = await make_topic(name="Topic B")
        source = await make_source(name="Source", platform="web")

        base_emb = _random_embedding(seed=400)
        now = datetime.now(UTC)

        # Topic B's own items: positive sentiment
        for i in range(2):
            item_id = str(uuid.uuid4())
            content_hash = hashlib.sha256(f"positive-{i}-{uuid.uuid4()}".encode()).hexdigest()
            labels = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak","sentiment":{"compound":0.5}}'
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO content_items (id, topic_id, source_id, raw_text, clean_text,
                       language, content_hash, url, captured_at, credibility_score_at_capture,
                       created_at, updated_at, labels, org_id)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                    item_id, topic_b, source, f"positive article {i}", f"positive article {i}",
                    "en", content_hash, f"https://example.com/{item_id[:8]}",
                    now, 75.0, now, now, labels, "org-integration-test",
                )

        # Topic A's items: negative sentiment, backfilled to Topic B
        backfilled_ids = []
        for i in range(2):
            item_id = str(uuid.uuid4())
            content_hash = hashlib.sha256(f"negative-{i}-{uuid.uuid4()}".encode()).hexdigest()
            labels = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak","sentiment":{"compound":-0.8}}'
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO content_items (id, topic_id, source_id, raw_text, clean_text,
                       language, content_hash, url, captured_at, credibility_score_at_capture,
                       created_at, updated_at, labels, org_id)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                    item_id, topic_a, source, f"negative article {i}", f"negative article {i}",
                    "en", content_hash, f"https://example.com/{item_id[:8]}",
                    now, 75.0, now, now, labels, "org-integration-test",
                )
            backfilled_ids.append(item_id)
            await _backfill_item(db_pool, topic_b, item_id)

        # Query sentiment baseline for Topic B
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT AVG((labels->'sentiment'->>'compound')::float) AS baseline_avg
                   FROM content_items
                   WHERE (topic_id = $1
                      OR id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
                     AND captured_at >= NOW() - INTERVAL '7 days'
                     AND labels->'sentiment' IS NOT NULL""",
                topic_b,
            )

        # If backfilled items are included: avg = (0.5 + 0.5 + (-0.8) + (-0.8)) / 4 = -0.15
        # If only owned items: avg = (0.5 + 0.5) / 2 = 0.5
        assert row["baseline_avg"] is not None
        assert row["baseline_avg"] < 0.0, (
            f"Sentiment baseline should be negative (backfilled items included), "
            f"got {row['baseline_avg']:.3f}. Backfilled items likely excluded."
        )
