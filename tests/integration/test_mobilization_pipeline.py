"""Seeded content through to a fired Mobilization signal — issue #33."""

from __future__ import annotations

import json
import uuid

import pytest

from tests.conftest import TEST_ORG_ID

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

LABELS = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'

ENGLISH_CALL = (
    "All are invited to join the gathering outside the collectorate. "
    "Everyone gather at Town Square tomorrow at 4pm."
)
HINDI_CALL = "सभी लोग कल सुबह कलेक्ट्रेट पर पहुंचें। जुलूस निकालेंगे।"
ORDINARY = "The district administration said the situation remained calm overnight."


@pytest.fixture
async def topic(db_pool, make_topic):
    topic_id = await make_topic(name="Integration Test Topic mobilization")
    yield topic_id
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM signals WHERE topic_id = $1", topic_id)
        await conn.execute("DELETE FROM content_items WHERE topic_id = $1", topic_id)
        await conn.execute("DELETE FROM narrative_clusters WHERE topic_id = $1", topic_id)


async def _seed(db_pool, topic_id, source_id, texts, language="en", label="Assembly call"):
    cluster_id = str(uuid.uuid4())
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO narrative_clusters (
                id, topic_id, label, item_count, independent_source_count,
                created_at, updated_at, labels
            )
            VALUES ($1, $2, $3, $4, 1, NOW(), NOW(), $5::jsonb)
            """,
            cluster_id,
            topic_id,
            label,
            len(texts),
            LABELS,
        )
        for i, text in enumerate(texts):
            await conn.execute(
                """
                INSERT INTO content_items (
                    id, topic_id, source_id, narrative_cluster_id, org_id,
                    raw_text, clean_text, language, content_hash, captured_at, labels
                )
                VALUES ($1, $2, $3, $4, $5, $6, $6, $7, $8, NOW(), $9::jsonb)
                """,
                str(uuid.uuid4()),
                topic_id,
                source_id,
                cluster_id,
                TEST_ORG_ID,
                text,
                language,
                f"{cluster_id}-{i}",
                LABELS,
            )
    return cluster_id


async def _noop(_payload) -> None:
    """Broadcast stub."""


class TestPipeline:
    async def test_an_english_call_fires_a_signal(self, db_pool, topic, make_source):
        from anveshak.analyst.mobilization import check_mobilization_calls

        source = await make_source(name="Test Source mob en")
        cluster_id = await _seed(db_pool, topic, source, [ENGLISH_CALL, ENGLISH_CALL + " Again."])

        assert await check_mobilization_calls(db_pool, _noop) == 1

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT signal_type, description, evidence FROM signals WHERE cluster_id = $1",
                cluster_id,
            )
        assert row["signal_type"] == "mobilization_call"
        assert "Matched phrase" in row["description"]

    async def test_a_hindi_call_fires_a_signal(self, db_pool, topic, make_source):
        from anveshak.analyst.mobilization import check_mobilization_calls

        source = await make_source(name="Test Source mob hi")
        cluster_id = await _seed(
            db_pool, topic, source, [HINDI_CALL, HINDI_CALL + " फिर।"], language="hi"
        )

        assert await check_mobilization_calls(db_pool, _noop) == 1

        async with db_pool.acquire() as conn:
            raw = await conn.fetchval(
                "SELECT evidence FROM signals WHERE cluster_id = $1", cluster_id
            )
        evidence = raw if isinstance(raw, dict) else json.loads(raw)
        assert evidence["matched_phrase"]
        assert evidence["lexicon_version"] >= 1

    async def test_ordinary_reporting_fires_nothing(self, db_pool, topic, make_source):
        from anveshak.analyst.mobilization import check_mobilization_calls

        source = await make_source(name="Test Source mob none")
        await _seed(db_pool, topic, source, [ORDINARY, ORDINARY + " Again."])

        assert await check_mobilization_calls(db_pool, _noop) == 0

    async def test_the_matched_phrase_is_always_carried(self, db_pool, topic, make_source):
        from anveshak.analyst.mobilization import check_mobilization_calls

        source = await make_source(name="Test Source mob phrase")
        cluster_id = await _seed(db_pool, topic, source, [ENGLISH_CALL, ENGLISH_CALL + " Again."])
        await check_mobilization_calls(db_pool, _noop)

        async with db_pool.acquire() as conn:
            raw = await conn.fetchval(
                "SELECT evidence FROM signals WHERE cluster_id = $1", cluster_id
            )
        evidence = raw if isinstance(raw, dict) else json.loads(raw)
        assert evidence["matched_phrase"]
        assert evidence["content_item_ids"]

    async def test_the_description_never_predicts_an_event(self, db_pool, topic, make_source):
        from anveshak.analyst.mobilization import check_mobilization_calls

        source = await make_source(name="Test Source mob wording")
        cluster_id = await _seed(db_pool, topic, source, [ENGLISH_CALL, ENGLISH_CALL + " Again."])
        await check_mobilization_calls(db_pool, _noop)

        async with db_pool.acquire() as conn:
            description = await conn.fetchval(
                "SELECT description FROM signals WHERE cluster_id = $1", cluster_id
            )
        lowered = description.lower()
        for word in ("will occur", "expected", "likely", "probability", "imminent", "threat"):
            assert word not in lowered

    async def test_it_does_not_refire_within_the_dedup_window(self, db_pool, topic, make_source):
        from anveshak.analyst.mobilization import check_mobilization_calls

        source = await make_source(name="Test Source mob dedup")
        await _seed(db_pool, topic, source, [ENGLISH_CALL, ENGLISH_CALL + " Again."])

        assert await check_mobilization_calls(db_pool, _noop) == 1
        assert await check_mobilization_calls(db_pool, _noop) == 0

    async def test_a_single_item_does_not_fire(self, db_pool, topic, make_source):
        from anveshak.analyst.mobilization import check_mobilization_calls

        source = await make_source(name="Test Source mob single")
        await _seed(db_pool, topic, source, [ENGLISH_CALL])

        assert await check_mobilization_calls(db_pool, _noop) == 0
