"""Integration test: backfilled items must appear in reporter RAG + location queries.

Tests the CONTRACT between backfill (writes to topic_content_items)
and reporter service (reads content for report generation). The bugs:
  - SQL_FETCH_RAG_CHUNKS used WHERE topic_id = $1, ignoring topic_content_items
  - SQL_FETCH_TOPIC_LOCATION_ENTITIES same issue

pytest.mark.integration — requires running Docker Compose (postgres).

Run with:
  uv run --package anveshak-tests pytest tests/integration/test_backfill_reporter_contract.py -v -m integration
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import numpy as np
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


# ---------------------------------------------------------------------------
# Helpers (same pattern as test_backfill_clustering_contract.py)
# ---------------------------------------------------------------------------


def _random_embedding(seed: int, dim: int = 384) -> list[float]:
    """L2-normalised random embedding."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float64)
    vec /= np.linalg.norm(vec)
    return vec.tolist()


async def _insert_content(pool, topic_id, source_id, text, embedding, language="en"):
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


async def _backfill_item(pool, topic_id, content_item_id, similarity=0.90):
    """Insert into topic_content_items (simulates backfill output)."""
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
# Test 1: Reporter RAG chunks include backfilled items (BUG 1)
# ---------------------------------------------------------------------------


class TestRAGChunksIncludeBackfilled:
    """SQL_FETCH_RAG_CHUNKS must include items from topic_content_items."""

    async def test_rag_chunks_include_backfilled_item(self, db_pool, make_topic, make_source):
        """
        Scenario:
          - Topic A owns article X with embedding
          - Topic B has article X backfilled via topic_content_items
          - fetch_rag_chunks(topic_B) must return article X
        """
        from anveshak.reporter.db import fetch_rag_chunks

        topic_a = await make_topic(name="Topic A - Owner")
        topic_b = await make_topic(name="Topic B - Backfilled")
        source = await make_source(name="Reuters", platform="rss", credibility_score=85.0)

        emb = _random_embedding(seed=500)

        item_id = await _insert_content(
            db_pool,
            topic_a,
            source,
            "PLA bridge construction at Pangong Tso sector detected by satellite",
            embedding=emb,
        )

        await _backfill_item(db_pool, topic_b, item_id)

        # Query RAG chunks for Topic B using same embedding as query vector
        results = await fetch_rag_chunks(
            db_pool,
            topic_b,
            query_embedding=emb,
            credibility_min=0.0,
            top_k=10,
        )

        result_ids = [r["id"] for r in results]
        assert item_id in result_ids, (
            f"Backfilled item {item_id} not found in Topic B's RAG chunks. "
            f"Got {len(results)} results: {result_ids}"
        )

    async def test_rag_chunks_include_both_owned_and_backfilled(
        self,
        db_pool,
        make_topic,
        make_source,
    ):
        """Topic B should see its own items AND backfilled items in RAG."""
        from anveshak.reporter.db import fetch_rag_chunks

        topic_a = await make_topic(name="Topic A")
        topic_b = await make_topic(name="Topic B")
        source_rss = await make_source(name="Reuters", platform="rss", credibility_score=80.0)
        source_web = await make_source(name="NDTV", platform="web", credibility_score=80.0)

        base_emb = _random_embedding(seed=510)

        # 2 items owned by Topic B
        item_b1 = await _insert_content(
            db_pool,
            topic_b,
            source_web,
            "India monitors Chinese activity at Line of Actual Control edition one",
            embedding=base_emb,
        )
        item_b2 = await _insert_content(
            db_pool,
            topic_b,
            source_web,
            "India monitors Chinese activity at Line of Actual Control edition two",
            embedding=_random_embedding(seed=511),
        )

        # 1 item owned by Topic A, backfilled to B
        item_a = await _insert_content(
            db_pool,
            topic_a,
            source_rss,
            "Reuters reports on Chinese military infrastructure near LAC",
            embedding=_random_embedding(seed=512),
        )
        await _backfill_item(db_pool, topic_b, item_a)

        results = await fetch_rag_chunks(
            db_pool,
            topic_b,
            query_embedding=base_emb,
            credibility_min=0.0,
            top_k=10,
        )

        result_ids = {r["id"] for r in results}
        assert item_b1 in result_ids, "Owned item b1 missing"
        assert item_b2 in result_ids, "Owned item b2 missing"
        assert item_a in result_ids, "Backfilled item missing from RAG chunks"
        assert len(result_ids) >= 3


# ---------------------------------------------------------------------------
# Test 2: Reporter location entities include backfilled items (BUG 2)
# ---------------------------------------------------------------------------


class TestLocationEntitiesIncludeBackfilled:
    """SQL_FETCH_TOPIC_LOCATION_ENTITIES must include backfilled items."""

    async def test_location_entities_include_backfilled(self, db_pool, make_topic, make_source):
        """
        Scenario:
          - Topic A owns an article with extracted entity (GPE: 'Pangong Tso')
          - Article backfilled to Topic B
          - fetch_topic_location_entities(topic_B) must return 'Pangong Tso'
        """
        from anveshak.reporter.db import fetch_topic_location_entities

        topic_a = await make_topic(name="Topic A")
        topic_b = await make_topic(name="Topic B")
        source = await make_source(name="NDTV", platform="web")

        emb = _random_embedding(seed=520)
        item_id = await _insert_content(
            db_pool,
            topic_a,
            source,
            "PLA forces spotted near Pangong Tso lake in Ladakh region",
            embedding=emb,
        )

        # Insert extracted entity for this item
        entity_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO extracted_entities (id, content_item_id, entity_type, entity_text,
                   confidence, created_at, labels)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                entity_id,
                item_id,
                "GPE",
                "Pangong Tso",
                0.95,
                now,
                LABELS_JSON,
            )

        # Backfill to Topic B
        await _backfill_item(db_pool, topic_b, item_id)

        # Query location entities for Topic B
        locations = await fetch_topic_location_entities(db_pool, topic_b)

        assert "Pangong Tso" in locations, (
            f"'Pangong Tso' not found in Topic B's location entities. "
            f"Got: {locations}. Backfilled items likely excluded."
        )
