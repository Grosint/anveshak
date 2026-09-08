"""Seeded content through to a fired Manufactured Narrative signal — #32."""

from __future__ import annotations

import uuid

import pytest
from anveshak.analyst.settings import settings

from tests.conftest import TEST_ORG_ID

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

LABELS = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'
CLAIM = "The same claim repeated verbatim across many accounts"


async def _seed_cluster(
    db_pool,
    topic_id: str,
    source_ids: list[str],
    *,
    items: int,
    accounts: int,
    label: str,
) -> str:
    cluster_id = str(uuid.uuid4())
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
            len(source_ids),
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
                source_ids[i % len(source_ids)],
                cluster_id,
                TEST_ORG_ID,
                f"{CLAIM}. Variation {i}.",
                f"{cluster_id}-{i}",
                '{"classification":"OPEN","domain":"social","owner_org":"anveshak",'
                f'"author_handle":"@amp{i % accounts}"}}',
            )
    return cluster_id


@pytest.fixture
async def topic(db_pool, make_topic):
    topic_id = await make_topic(name="Integration Test Topic manufactured")
    yield topic_id
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM signals WHERE topic_id = $1", topic_id)
        await conn.execute("DELETE FROM content_items WHERE topic_id = $1", topic_id)
        await conn.execute("DELETE FROM narrative_clusters WHERE topic_id = $1", topic_id)


class TestPipeline:
    async def test_amplification_fires_a_signal(self, db_pool, topic, make_source):
        from anveshak.analyst.manufactured import check_manufactured_narratives

        sources = [await make_source(name="Test Source amp 0")]
        cluster_id = await _seed_cluster(
            db_pool,
            topic,
            sources,
            items=settings.manufactured_min_item_count + 10,
            accounts=settings.manufactured_min_account_count + 3,
            label="Amplified narrative",
        )

        fired = await check_manufactured_narratives(db_pool, _noop)
        assert fired == 1

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT signal_type, description, evidence FROM signals WHERE cluster_id = $1",
                cluster_id,
            )

        assert row["signal_type"] == "manufactured_narrative"
        assert "independent" in row["description"]

    async def test_the_signal_carries_the_items_that_fired_it(self, db_pool, topic, make_source):
        import json

        from anveshak.analyst.manufactured import check_manufactured_narratives

        sources = [await make_source(name="Test Source amp evidence")]
        await _seed_cluster(
            db_pool,
            topic,
            sources,
            items=settings.manufactured_min_item_count + 10,
            accounts=settings.manufactured_min_account_count + 3,
            label="Amplified with evidence",
        )
        await check_manufactured_narratives(db_pool, _noop)

        async with db_pool.acquire() as conn:
            raw = await conn.fetchval(
                "SELECT evidence FROM signals WHERE topic_id = $1 "
                "AND signal_type = 'manufactured_narrative'",
                topic,
            )
        evidence = raw if isinstance(raw, dict) else json.loads(raw)

        assert evidence["content_item_ids"]
        assert CLAIM in evidence["repeated_claim"]
        assert evidence["margins"]["item_count"] >= 0

    async def test_wide_independent_sourcing_fires_nothing(self, db_pool, topic, make_source):
        """That is reporting, and the convergence signal already covers it."""
        from anveshak.analyst.manufactured import check_manufactured_narratives

        sources = [
            await make_source(name=f"Test Source reported {i}")
            for i in range(settings.manufactured_max_independent_sources + 2)
        ]
        await _seed_cluster(
            db_pool,
            topic,
            sources,
            items=settings.manufactured_min_item_count + 10,
            accounts=settings.manufactured_min_account_count + 3,
            label="Widely reported",
        )

        assert await check_manufactured_narratives(db_pool, _noop) == 0

    async def test_one_loud_account_fires_nothing(self, db_pool, topic, make_source):
        from anveshak.analyst.manufactured import check_manufactured_narratives

        sources = [await make_source(name="Test Source loud")]
        await _seed_cluster(
            db_pool,
            topic,
            sources,
            items=settings.manufactured_min_item_count + 10,
            accounts=1,
            label="One loud account",
        )

        assert await check_manufactured_narratives(db_pool, _noop) == 0

    async def test_it_does_not_refire_within_the_dedup_window(self, db_pool, topic, make_source):
        from anveshak.analyst.manufactured import check_manufactured_narratives

        sources = [await make_source(name="Test Source dedup amp")]
        await _seed_cluster(
            db_pool,
            topic,
            sources,
            items=settings.manufactured_min_item_count + 10,
            accounts=settings.manufactured_min_account_count + 3,
            label="Dedup check",
        )

        assert await check_manufactured_narratives(db_pool, _noop) == 1
        assert await check_manufactured_narratives(db_pool, _noop) == 0


async def _noop(_payload) -> None:
    """Broadcast stub."""
