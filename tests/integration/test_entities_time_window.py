"""Integration test: SQL_GET_TOPIC_ENTITIES must have a time window.

Without a time window, this query scans ALL extracted_entities for a topic.
At 1M items × 50 entities = 50M rows aggregated on every API call.
Sentiment trend and trending keywords already have time windows — entities must too.

pytest.mark.integration — requires running PostgreSQL.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, UTC

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestEntitiesTimeWindow:
    """SQL_GET_TOPIC_ENTITIES must accept a days parameter and filter by it."""

    async def test_get_topic_entities_accepts_days_param(self, db_pool, make_topic, make_source):
        """get_topic_entities(conn, topic_id, days) must accept a days parameter."""
        from anveshak.api.db.topics import get_topic_entities

        topic_id = await make_topic(name="Entities Window Test")
        source_id = await make_source(name="Test Source", platform="web")

        async with db_pool.acquire() as conn:
            # Should accept days parameter without error
            result = await get_topic_entities(conn, topic_id, days=30)
            assert isinstance(result, list)

    async def test_entities_filtered_by_time_window(self, db_pool, make_topic, make_source):
        """Only entities from content within the time window should be returned."""
        from anveshak.api.db.topics import get_topic_entities

        topic_id = await make_topic(name="Entities Time Filter")
        source_id = await make_source(name="Reuters", platform="rss")

        now = datetime.now(UTC)
        old_date = now - timedelta(days=60)

        async with db_pool.acquire() as conn:
            # Insert recent content item + entity
            recent_id = str(uuid.uuid4())
            recent_hash = hashlib.sha256(f"recent-{uuid.uuid4()}".encode()).hexdigest()
            labels = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'
            await conn.execute(
                """INSERT INTO content_items (id, topic_id, source_id, raw_text, clean_text,
                   language, content_hash, url, captured_at, credibility_score_at_capture,
                   created_at, updated_at, labels, org_id)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                recent_id, topic_id, source_id, "recent article about PLA", "recent article about PLA",
                "en", recent_hash, f"https://example.com/{recent_id[:8]}",
                now, 75.0, now, now, labels, "org-integration-test",
            )
            await conn.execute(
                """INSERT INTO extracted_entities (id, content_item_id, entity_type, entity_text,
                   confidence, created_at, labels)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                str(uuid.uuid4()), recent_id, "ORG", "PLA",
                0.95, now, labels,
            )

            # Insert old content item + entity (60 days ago)
            old_id = str(uuid.uuid4())
            old_hash = hashlib.sha256(f"old-{uuid.uuid4()}".encode()).hexdigest()
            await conn.execute(
                """INSERT INTO content_items (id, topic_id, source_id, raw_text, clean_text,
                   language, content_hash, url, captured_at, credibility_score_at_capture,
                   created_at, updated_at, labels, org_id)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                old_id, topic_id, source_id, "old article about DRDO", "old article about DRDO",
                "en", old_hash, f"https://example.com/{old_id[:8]}",
                old_date, 75.0, old_date, old_date, labels, "org-integration-test",
            )
            await conn.execute(
                """INSERT INTO extracted_entities (id, content_item_id, entity_type, entity_text,
                   confidence, created_at, labels)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                str(uuid.uuid4()), old_id, "ORG", "DRDO",
                0.90, old_date, labels,
            )

            # Query with 30-day window — should only see PLA, not DRDO
            entities = await get_topic_entities(conn, topic_id, days=30)

        entity_texts = [e["entity_text"] for e in entities]
        assert "PLA" in entity_texts, "Recent entity PLA should be in 30-day window"
        assert "DRDO" not in entity_texts, (
            "Old entity DRDO (60 days ago) should be excluded by 30-day window"
        )
