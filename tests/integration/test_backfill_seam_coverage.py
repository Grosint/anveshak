"""Integration tests: cross-system seam coverage for backfilled items.

Tests the CONTRACT at system boundaries where backfilled items (linked via
topic_content_items) must be visible to downstream consumers:
  - Credibility cross-verification (BUG 3)
  - API entities, sentiment trend, trending keywords (GAPs 4-6)
  - Scraper INSERT → analyst load (GAP 7)
  - Social ingest → analyst load (GAP 8)

pytest.mark.integration — requires running Docker Compose (postgres).

Run with:
  uv run --package anveshak-tests pytest tests/integration/test_backfill_seam_coverage.py -v -m integration
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

import numpy as np
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _random_embedding(seed: int, dim: int = 384) -> list[float]:
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float64)
    vec /= np.linalg.norm(vec)
    return vec.tolist()


def _similar_embedding(base: list[float], seed: int, noise: float = 0.02) -> list[float]:
    rng = np.random.RandomState(seed)
    arr = np.array(base, dtype=np.float64)
    arr += rng.uniform(-noise, noise, size=len(arr))
    arr /= np.linalg.norm(arr)
    return arr.tolist()


async def _insert_content(
    pool, topic_id, source_id, text, embedding, language="en", labels_json=LABELS_JSON
):
    """Insert content_item with embedding. Returns item_id."""
    from tests.conftest import insert_content_item

    content_hash = hashlib.sha256(text.lower().strip().encode()).hexdigest()
    return await insert_content_item(
        pool,
        topic_id,
        source_id,
        text,
        content_hash=content_hash,
        embedding=embedding,
        language=language,
    )


async def _insert_content_with_labels(pool, topic_id, source_id, text, embedding, labels_str):
    """Insert content_item with custom labels JSON (for sentiment/keywords)."""
    item_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    content_hash = hashlib.sha256(text.lower().strip().encode()).hexdigest()
    url = f"https://example.com/test-{item_id[:8]}"
    embedding_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"

    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO content_items (
                id, topic_id, source_id, raw_text, clean_text, language,
                content_hash, url, captured_at, credibility_score_at_capture,
                embedding, created_at, updated_at, labels, org_id
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::vector,$12,$13,$14,$15)
            ON CONFLICT(content_hash) DO NOTHING""",
            item_id,
            topic_id,
            source_id,
            text,
            text,
            "en",
            content_hash,
            url,
            now,
            75.0,
            embedding_str,
            now,
            now,
            labels_str,
            "org-integration-test",
        )
    return item_id


async def _backfill_item(pool, topic_id, content_item_id, similarity=0.90):
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO topic_content_items (topic_id, content_item_id, similarity_score, assigned_at)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (topic_id, content_item_id) DO NOTHING""",
            topic_id,
            content_item_id,
            similarity,
            datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# BUG 3: Credibility cross-verification misses backfilled items
# ---------------------------------------------------------------------------


class TestCrossVerifyBackfilled:
    """SQL_CROSS_VERIFY_SOURCES must include sources of backfilled items in clusters."""

    async def test_cross_verify_includes_backfilled_source(
        self,
        db_pool,
        make_topic,
        make_source,
    ):
        """
        Scenario:
          - Source S (credibility=70, auto_score_enabled=True) contributes to Topic A
          - Topic A has a cluster with ISC >= 2 containing items from S and another source
          - One of S's items is backfilled to Topic B
          - Topic B also has a cluster (with ISC >= 2) containing the backfilled item
          - run_cross_verification_update(topic_B) should find S via backfilled item
        """
        from anveshak.analyst.credibility import run_cross_verification_update

        topic_a = await make_topic(name="Topic A - Owner")
        topic_b = await make_topic(name="Topic B - Backfilled")
        source_s = await make_source(name="Reuters", platform="rss", credibility_score=70.0)
        source_t = await make_source(name="NDTV", platform="web", credibility_score=70.0)

        # Enable auto-scoring on both sources
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE sources SET auto_score_enabled = TRUE WHERE id = ANY($1::text[])",
                [source_s, source_t],
            )

        base_emb = _random_embedding(seed=600)

        # Insert items for Topic B from both sources → forms a cluster with ISC=2
        item_t1 = await _insert_content(
            db_pool,
            topic_b,
            source_t,
            "NDTV reports PLA infrastructure at LAC sector alpha",
            embedding=_similar_embedding(base_emb, seed=610),
        )
        item_t2 = await _insert_content(
            db_pool,
            topic_b,
            source_t,
            "NDTV update on Chinese military construction near LAC region",
            embedding=_similar_embedding(base_emb, seed=611),
        )

        # Item owned by Topic A from source S → backfill to Topic B
        item_s = await _insert_content(
            db_pool,
            topic_a,
            source_s,
            "Reuters confirms Chinese bridge construction at Pangong Tso sector",
            embedding=_similar_embedding(base_emb, seed=612),
        )
        await _backfill_item(db_pool, topic_b, item_s)

        # Create a cluster for Topic B that includes all items
        cluster_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        centroid = _similar_embedding(base_emb, seed=620)
        centroid_str = "[" + ",".join(f"{x:.8f}" for x in centroid) + "]"

        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO narrative_clusters (
                    id, topic_id, label, item_count, embedding_centroid,
                    independent_source_count, created_at, updated_at, labels
                ) VALUES ($1, $2, $3, $4, $5::vector, $6, $7, $7, $8)""",
                cluster_id,
                topic_b,
                "LAC Activity",
                3,
                centroid_str,
                2,
                now,
                LABELS_JSON,
            )
            # Assign items to the cluster
            await conn.execute(
                "UPDATE content_items SET narrative_cluster_id = $1 WHERE id = ANY($2::text[])",
                cluster_id,
                [item_t1, item_t2, item_s],
            )

        # Record initial credibility
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT credibility_score FROM sources WHERE id = $1",
                source_s,
            )
        initial_score = row["credibility_score"]

        # Run cross-verification for Topic B
        updated = await run_cross_verification_update(db_pool, topic_b)

        # Source S should get a boost from Topic B's cluster (via backfilled item)
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT credibility_score FROM sources WHERE id = $1",
                source_s,
            )

        assert row["credibility_score"] > initial_score, (
            f"Source S credibility should be boosted via backfilled item in Topic B's cluster. "
            f"Initial: {initial_score}, current: {row['credibility_score']}. "
            f"Cross-verify updated {updated} sources."
        )


# ---------------------------------------------------------------------------
# GAP 4: API entities include backfilled items
# ---------------------------------------------------------------------------


class TestBackfillAPIEntities:
    """SQL_GET_TOPIC_ENTITIES already uses dual routing — verify with seam test."""

    async def test_entities_appear_for_backfilled_items(
        self,
        db_pool,
        make_topic,
        make_source,
    ):
        """
        Scenario:
          - Topic A owns article with extracted entity (PERSON: 'Xi Jinping')
          - Article backfilled to Topic B
          - get_topic_entities(topic_B) must include 'Xi Jinping'
        """
        from anveshak.api.db.topics import get_topic_entities

        topic_a = await make_topic(name="Topic A")
        topic_b = await make_topic(name="Topic B")
        source = await make_source(name="NDTV", platform="web")

        emb = _random_embedding(seed=700)
        item_id = await _insert_content(
            db_pool,
            topic_a,
            source,
            "Xi Jinping visits Aksai Chin region amid border tensions",
            embedding=emb,
        )

        # Insert extracted entity
        now = datetime.now(UTC)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO extracted_entities (id, content_item_id, entity_type, entity_text,
                   confidence, created_at, labels)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                str(uuid.uuid4()),
                item_id,
                "PERSON",
                "Xi Jinping",
                0.92,
                now,
                LABELS_JSON,
            )

        # Backfill to Topic B
        await _backfill_item(db_pool, topic_b, item_id)

        # Query entities for Topic B
        async with db_pool.acquire() as conn:
            entities = await get_topic_entities(conn, topic_b)

        entity_texts = [e["entity_text"] for e in entities]
        assert "Xi Jinping" in entity_texts, (
            f"'Xi Jinping' not found in Topic B entities. Got: {entity_texts}"
        )


# ---------------------------------------------------------------------------
# GAP 5: API sentiment trend includes backfilled items
# ---------------------------------------------------------------------------


class TestBackfillAPISentimentTrend:
    """SQL_SENTIMENT_TREND already uses dual routing — verify with seam test."""

    async def test_sentiment_trend_includes_backfilled(
        self,
        db_pool,
        make_topic,
        make_source,
    ):
        """
        Scenario:
          - Topic B owns 2 items with positive sentiment (compound=0.5)
          - 2 items with negative sentiment (compound=-0.8) backfilled from Topic A
          - get_sentiment_trend(topic_B) should reflect all 4 items (avg < 0)
        """
        from anveshak.api.db.topics import get_sentiment_trend

        topic_a = await make_topic(name="Topic A")
        topic_b = await make_topic(name="Topic B")
        source = await make_source(name="Source", platform="web")

        # Topic B's own items: positive sentiment
        positive_labels = json.dumps(
            {
                "classification": "OPEN",
                "domain": "osint",
                "owner_org": "anveshak",
                "sentiment": {"compound": 0.5},
            }
        )
        for i in range(2):
            await _insert_content_with_labels(
                db_pool,
                topic_b,
                source,
                f"Positive development at border region edition {i} unique text {uuid.uuid4().hex[:8]}",
                embedding=_random_embedding(seed=711 + i),
                labels_str=positive_labels,
            )

        # Topic A's items: negative sentiment, backfilled to Topic B
        negative_labels = json.dumps(
            {
                "classification": "OPEN",
                "domain": "osint",
                "owner_org": "anveshak",
                "sentiment": {"compound": -0.8},
            }
        )
        for i in range(2):
            item_id = await _insert_content_with_labels(
                db_pool,
                topic_a,
                source,
                f"Negative incident at border region edition {i} unique text {uuid.uuid4().hex[:8]}",
                embedding=_random_embedding(seed=721 + i),
                labels_str=negative_labels,
            )
            await _backfill_item(db_pool, topic_b, item_id)

        # Query sentiment trend for Topic B
        async with db_pool.acquire() as conn:
            trend = await get_sentiment_trend(conn, topic_b, days=7)

        # Should have data — if empty, items were filtered out
        assert len(trend) > 0, "Sentiment trend returned no data"

        # With all 4 items: avg = (0.5 + 0.5 + (-0.8) + (-0.8)) / 4 = -0.15
        # Without backfilled: avg = (0.5 + 0.5) / 2 = 0.5
        total_items = sum(day["item_count"] for day in trend)
        assert total_items >= 4, (
            f"Expected at least 4 items in trend (2 owned + 2 backfilled), got {total_items}. "
            "Backfilled items likely excluded."
        )


# ---------------------------------------------------------------------------
# GAP 6: API trending keywords include backfilled items
# ---------------------------------------------------------------------------


class TestBackfillAPITrendingKeywords:
    """SQL_TRENDING_KEYWORDS already uses dual routing — verify with seam test."""

    async def test_trending_keywords_include_backfilled(
        self,
        db_pool,
        make_topic,
        make_source,
    ):
        """
        Scenario:
          - Topic B owns items with keyword 'border'
          - Backfilled item has keywords 'LAC', 'PLA'
          - get_trending_keywords(topic_B) should include all keywords
        """
        from anveshak.api.db.topics import get_trending_keywords

        topic_a = await make_topic(name="Topic A")
        topic_b = await make_topic(name="Topic B")
        source = await make_source(name="Source", platform="web")

        # Topic B's own item with keyword 'border'
        owned_labels = json.dumps(
            {
                "classification": "OPEN",
                "domain": "osint",
                "owner_org": "anveshak",
                "keywords": ["border", "patrol"],
            }
        )
        await _insert_content_with_labels(
            db_pool,
            topic_b,
            source,
            f"Border patrol activities increased significantly {uuid.uuid4().hex[:8]}",
            embedding=_random_embedding(seed=730),
            labels_str=owned_labels,
        )

        # Backfilled item with keywords 'LAC', 'PLA'
        backfill_labels = json.dumps(
            {
                "classification": "OPEN",
                "domain": "osint",
                "owner_org": "anveshak",
                "keywords": ["LAC", "PLA"],
            }
        )
        item_id = await _insert_content_with_labels(
            db_pool,
            topic_a,
            source,
            f"PLA forces observed near LAC in eastern sector {uuid.uuid4().hex[:8]}",
            embedding=_random_embedding(seed=731),
            labels_str=backfill_labels,
        )
        await _backfill_item(db_pool, topic_b, item_id)

        # Query trending keywords for Topic B
        async with db_pool.acquire() as conn:
            keywords = await get_trending_keywords(conn, topic_b, days=7, limit=15)

        kw_set = {k["keyword"] for k in keywords}
        assert "border" in kw_set, f"Owned keyword 'border' missing. Got: {kw_set}"
        assert "LAC" in kw_set, f"Backfilled keyword 'LAC' missing. Got: {kw_set}"
        assert "PLA" in kw_set, f"Backfilled keyword 'PLA' missing. Got: {kw_set}"


# ---------------------------------------------------------------------------
# GAP 7: Scraper INSERT → analyst load_unclustered_embeddings
# ---------------------------------------------------------------------------


class TestScraperToAnalystSeam:
    """Verify scraper's exact SQL_INSERT_CONTENT is picked up by analyst clustering."""

    async def test_scraper_insert_picked_up_by_analyst(
        self,
        db_pool,
        make_topic,
        make_source,
    ):
        """
        Uses scraper's exact SQL constant to insert, then verifies analyst's
        load_unclustered_embeddings returns the item. Catches schema drift
        between scraper INSERT and analyst SELECT.
        """
        from anveshak.analyst.clustering import load_unclustered_embeddings
        from anveshak.scraper.jobs import SQL_INSERT_CONTENT

        topic_id = await make_topic(name="Scraper-Analyst Seam Test")
        source_id = await make_source(
            name="Test Web Source", platform="web", credibility_score=80.0
        )

        item_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        text = f"Article about LAC border activity from scraper {uuid.uuid4().hex[:8]}"
        content_hash = hashlib.sha256(text.lower().strip().encode()).hexdigest()
        clean_hash = hashlib.sha256(text.encode()).hexdigest()
        emb = _random_embedding(seed=800)
        embedding_str = "[" + ",".join(f"{x:.8f}" for x in emb) + "]"

        # Insert using scraper's exact SQL (17 params including content_quality, clean_hash, title, org_id)
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                SQL_INSERT_CONTENT,
                item_id,  # $1: id
                topic_id,  # $2: topic_id
                source_id,  # $3: source_id
                text,  # $4: raw_text
                text,  # $5: clean_text
                "en",  # $6: language
                content_hash,  # $7: content_hash
                "https://example.com/scraper-test",  # $8: url
                now,  # $9: captured_at
                80.0,  # $10: credibility_score_at_capture
                now,  # $11: created_at
                now,  # $12: updated_at
                LABELS_JSON,  # $13: labels
                "good",  # $14: content_quality
                clean_hash,  # $15: clean_hash
                "Test Article",  # $16: title
                "org-integration-test",  # $17: org_id
            )
            assert result is not None, "Scraper INSERT returned nothing (content_hash conflict?)"

            # Add embedding (analyst NLP would do this, but we need it for load_unclustered)
            await conn.execute(
                "UPDATE content_items SET embedding = $1::vector WHERE id = $2",
                embedding_str,
                item_id,
            )

        # Analyst loads unclustered embeddings
        rows = await load_unclustered_embeddings(topic_id, db_pool)
        item_ids = [r.content_item_id for r in rows]

        assert item_id in item_ids, (
            f"Scraper-inserted item {item_id} not found in analyst's unclustered embeddings. "
            f"Got {len(rows)} items. Schema drift between scraper INSERT and analyst SELECT?"
        )


# ---------------------------------------------------------------------------
# GAP 8: Social ingest → analyst load_unclustered_embeddings
# ---------------------------------------------------------------------------


class TestSocialToAnalystSeam:
    """Verify social ingest's exact SQL is picked up by analyst clustering."""

    async def test_social_ingest_picked_up_by_analyst(
        self,
        db_pool,
        make_topic,
        make_source,
    ):
        """
        Uses social ingest's exact SQL_INSERT_CONTENT to insert, adds embedding,
        then verifies analyst's load_unclustered_embeddings returns the item.
        """
        from anveshak.analyst.clustering import load_unclustered_embeddings
        from anveshak.social.ingest import SQL_INSERT_CONTENT as SOCIAL_INSERT

        topic_id = await make_topic(name="Social-Analyst Seam Test")
        source_id = await make_source(
            name="Telegram Test",
            url_or_handle="@testchannel",
            platform="telegram",
            credibility_score=75.0,
        )

        # Enable is_active for source lookup
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE sources SET is_active = TRUE WHERE id = $1",
                source_id,
            )

        item_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        text = f"Telegram message about LAC activity {uuid.uuid4().hex[:8]}"
        clean_text = text.lower().strip()
        content_hash = hashlib.sha256(clean_text.encode()).hexdigest()
        labels = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak","adapter_id":"telegram-v1"}'
        emb = _random_embedding(seed=810)
        embedding_str = "[" + ",".join(f"{x:.8f}" for x in emb) + "]"

        # Insert using social's exact SQL (16 params — includes forwarded_from + org_id)
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                SOCIAL_INSERT,
                item_id,  # $1: id
                topic_id,  # $2: topic_id
                source_id,  # $3: source_id
                text,  # $4: raw_text
                clean_text,  # $5: clean_text
                "en",  # $6: language
                content_hash,  # $7: content_hash
                "https://t.me/testchannel/123",  # $8: url
                now,  # $9: captured_at
                75.0,  # $10: credibility_score_at_capture
                now,  # $11: created_at
                now,  # $12: updated_at
                labels,  # $13: labels
                None,  # $14: forwarded_from_channel_id
                None,  # $15: forwarded_from_channel_name
                "org-integration-test",  # $16: org_id
            )
            assert result is not None, "Social INSERT returned nothing"

            # Analyst NLP adds embedding after ingest
            await conn.execute(
                "UPDATE content_items SET embedding = $1::vector WHERE id = $2",
                embedding_str,
                item_id,
            )

        # Analyst loads unclustered embeddings
        rows = await load_unclustered_embeddings(topic_id, db_pool)
        item_ids = [r.content_item_id for r in rows]

        assert item_id in item_ids, (
            f"Social-ingested item {item_id} not found in analyst's unclustered embeddings. "
            f"Got {len(rows)} items. Schema drift between social INSERT and analyst SELECT?"
        )
