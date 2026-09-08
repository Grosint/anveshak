"""Concern facet against a real database — issue #36, ADR 0001.

The load-bearing assertion: applying a filter changes which clusters come
back and does not change the order of the ones that remain.
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import TEST_ORG_ID

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

LABELS = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


async def _seed_cluster(db_pool, topic_id, source_id, *, label, isc, items, concern):
    cluster_id = str(uuid.uuid4())
    concern_json = (
        f'{{"classification":"OPEN","domain":"osint","owner_org":"anveshak","concern":{concern}}}'
        if concern
        else LABELS
    )
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO narrative_clusters (
                id, topic_id, label, item_count, independent_source_count,
                created_at, updated_at, labels
            )
            VALUES ($1, $2, $3, $4, $5, NOW(), NOW(), $6::jsonb)
            """,
            cluster_id,
            topic_id,
            label,
            items,
            isc,
            LABELS,
        )
        for i in range(items):
            await conn.execute(
                """
                INSERT INTO content_items (
                    id, topic_id, source_id, narrative_cluster_id, org_id,
                    raw_text, clean_text, content_hash, captured_at, labels
                )
                VALUES ($1, $2, $3, $4, $5, $6, $6, $7, NOW(), $8::jsonb)
                """,
                str(uuid.uuid4()),
                topic_id,
                source_id,
                cluster_id,
                TEST_ORG_ID,
                f"concern item {label} {i}",
                f"{cluster_id}-{i}",
                concern_json,
            )
    return cluster_id


@pytest.fixture
async def seeded(db_pool, make_topic, make_source):
    topic_id = await make_topic(name="Integration Test Topic concern")
    source_id = await make_source(name="Test Source concern")

    # Ordered by propagation: wide (6) then mid (4) then narrow (2).
    wide = await _seed_cluster(
        db_pool,
        topic_id,
        source_id,
        label="Wide spread",
        isc=6,
        items=3,
        concern='{"financial_fraud": 2}',
    )
    mid = await _seed_cluster(
        db_pool, topic_id, source_id, label="Mid spread", isc=4, items=3, concern=None
    )
    narrow = await _seed_cluster(
        db_pool,
        topic_id,
        source_id,
        label="Narrow spread",
        isc=2,
        items=3,
        concern='{"financial_fraud": 9}',
    )

    yield {"topic_id": topic_id, "wide": wide, "mid": mid, "narrow": narrow}

    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM content_items WHERE topic_id = $1", topic_id)
        await conn.execute("DELETE FROM narrative_clusters WHERE topic_id = $1", topic_id)


class TestFilteringChangesMembershipNotOrdering:
    async def test_the_unfiltered_list_is_ordered_by_propagation(self, db_pool, seeded):
        from anveshak.api.db.concern import list_clusters_by_concern

        async with db_pool.acquire() as conn:
            clusters = await list_clusters_by_concern(
                conn, seeded["topic_id"], org_id=TEST_ORG_ID, categories=[]
            )

        assert [c["label"] for c in clusters] == ["Wide spread", "Mid spread", "Narrow spread"]

    async def test_a_filter_removes_non_matching_clusters(self, db_pool, seeded):
        from anveshak.api.db.concern import list_clusters_by_concern

        async with db_pool.acquire() as conn:
            clusters = await list_clusters_by_concern(
                conn,
                seeded["topic_id"],
                org_id=TEST_ORG_ID,
                categories=["financial_fraud"],
            )

        assert {c["label"] for c in clusters} == {"Wide spread", "Narrow spread"}

    async def test_the_filter_does_not_reorder(self, db_pool, seeded):
        """Narrow scores 9 against Wide's 2, and Wide still comes first."""
        from anveshak.api.db.concern import list_clusters_by_concern

        async with db_pool.acquire() as conn:
            clusters = await list_clusters_by_concern(
                conn,
                seeded["topic_id"],
                org_id=TEST_ORG_ID,
                categories=["financial_fraud"],
            )

        assert [c["label"] for c in clusters] == ["Wide spread", "Narrow spread"]

    async def test_a_category_nothing_carries_returns_nothing(self, db_pool, seeded):
        from anveshak.api.db.concern import list_clusters_by_concern

        async with db_pool.acquire() as conn:
            clusters = await list_clusters_by_concern(
                conn,
                seeded["topic_id"],
                org_id=TEST_ORG_ID,
                categories=["cross_border_coordination"],
            )

        assert clusters == []

    async def test_concern_scores_are_aggregated_from_content(self, db_pool, seeded):
        from anveshak.api.db.concern import list_clusters_by_concern

        async with db_pool.acquire() as conn:
            clusters = await list_clusters_by_concern(
                conn, seeded["topic_id"], org_id=TEST_ORG_ID, categories=[]
            )

        wide = next(c for c in clusters if c["label"] == "Wide spread")
        assert wide["concern"]["financial_fraud"] == 6  # 3 items at 2 each

    async def test_another_org_sees_nothing(self, db_pool, seeded):
        from anveshak.api.db.concern import list_clusters_by_concern

        async with db_pool.acquire() as conn:
            clusters = await list_clusters_by_concern(
                conn, seeded["topic_id"], org_id="org-someone-else", categories=[]
            )

        assert clusters == []
