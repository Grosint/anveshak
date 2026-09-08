"""Sentiment Timeline aggregate against a real database — issue #29."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import TEST_ORG_ID

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

LABELS = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'
OTHER_ORG_ID = "org-timeline-other"


@pytest.fixture
async def other_org(db_pool):
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
            VALUES ($1, 'Other Org', 'timeline-other', NOW(), NOW(), $2::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            OTHER_ORG_ID,
            LABELS,
        )
    yield OTHER_ORG_ID
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM organizations WHERE id = $1", OTHER_ORG_ID)


@pytest.fixture
async def seeded(db_pool, make_topic, make_source):
    topic_id = await make_topic(name="Integration Test Topic timeline")
    source_id = await make_source(name="Test Source timeline", platform="twitter")
    now = datetime.now(UTC)

    plan = [
        # (days ago, stance, hostility)
        (1, "supporting", 0.1),
        (1, "supporting", 0.2),
        (1, "opposing", 0.6),
        (2, "opposing", 0.7),
        (2, "neutral", 0.3),
        (3, "unsupported_language", None),
    ]

    async with db_pool.acquire() as conn:
        for i, (days_ago, stance, hostility) in enumerate(plan):
            await conn.execute(
                """
                INSERT INTO content_items (
                    id, topic_id, source_id, org_id, raw_text, clean_text,
                    content_hash, captured_at, published_at, stance, hostility, labels
                )
                VALUES ($1, $2, $3, $4, $5, $5, $6, NOW(), $7, $8, $9, $10::jsonb)
                """,
                str(uuid.uuid4()),
                topic_id,
                source_id,
                TEST_ORG_ID,
                f"timeline item {i}",
                f"timeline-{topic_id}-{i}",
                now - timedelta(days=days_ago),
                stance,
                hostility,
                LABELS,
            )
        # Two items with no publication time: excluded, and reported.
        for i in range(2):
            await conn.execute(
                """
                INSERT INTO content_items (
                    id, topic_id, source_id, org_id, raw_text, clean_text,
                    content_hash, captured_at, published_at, labels
                )
                VALUES ($1, $2, $3, $4, $5, $5, $6, NOW(), NULL, $7::jsonb)
                """,
                str(uuid.uuid4()),
                topic_id,
                source_id,
                TEST_ORG_ID,
                f"timeline undated {i}",
                f"timeline-undated-{topic_id}-{i}",
                LABELS,
            )

    yield topic_id

    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM content_items WHERE topic_id = $1", topic_id)


class TestBuckets:
    async def test_stance_series_are_separate(self, db_pool, seeded):
        from anveshak.api.db.timeline import get_timeline

        async with db_pool.acquire() as conn:
            result = await get_timeline(conn, seeded, org_id=TEST_ORG_ID, days=30)

        totals = {"supporting": 0, "opposing": 0, "neutral": 0}
        for bucket in result["buckets"]:
            for key in totals:
                totals[key] += bucket[key]

        assert totals == {"supporting": 2, "opposing": 2, "neutral": 1}

    async def test_mean_hostility_excludes_unscored_items(self, db_pool, seeded):
        from anveshak.api.db.timeline import get_timeline

        async with db_pool.acquire() as conn:
            result = await get_timeline(conn, seeded, org_id=TEST_ORG_ID, days=30)

        # The unsupported_language item has NULL hostility and must not drag
        # the mean toward zero.
        sampled = sum(b["hostility_sample_count"] for b in result["buckets"])
        assert sampled == 5
        for bucket in result["buckets"]:
            if bucket["mean_hostility"] is not None:
                assert 0.0 <= bucket["mean_hostility"] <= 1.0

    async def test_unreadable_content_is_counted_separately(self, db_pool, seeded):
        from anveshak.api.db.timeline import get_timeline

        async with db_pool.acquire() as conn:
            result = await get_timeline(conn, seeded, org_id=TEST_ORG_ID, days=30)

        unsupported = sum(b["unsupported_language"] for b in result["buckets"])
        assert unsupported == 1

    async def test_items_without_a_publication_time_are_excluded_and_counted(self, db_pool, seeded):
        from anveshak.api.db.timeline import get_timeline

        async with db_pool.acquire() as conn:
            result = await get_timeline(conn, seeded, org_id=TEST_ORG_ID, days=30)

        plotted = sum(b["total"] for b in result["buckets"])
        assert plotted == 6
        assert result["excluded_no_publication_time"] == 2

    async def test_a_long_range_rolls_up_to_weekly(self, db_pool, seeded):
        from anveshak.api.db.timeline import get_timeline

        async with db_pool.acquire() as conn:
            daily = await get_timeline(conn, seeded, org_id=TEST_ORG_ID, days=30)
            weekly = await get_timeline(conn, seeded, org_id=TEST_ORG_ID, days=200)

        assert daily["bucket"] == "day"
        assert weekly["bucket"] == "week"
        assert len(weekly["buckets"]) <= len(daily["buckets"])


class TestPercentageView:
    async def test_absolute_is_the_default(self, db_pool, seeded):
        from anveshak.api.db.timeline import get_timeline

        async with db_pool.acquire() as conn:
            result = await get_timeline(conn, seeded, org_id=TEST_ORG_ID, days=30)

        assert result["as_percentage"] is False
        assert any(b["supporting"] in (0, 1, 2) for b in result["buckets"])

    async def test_percentages_sum_to_a_hundred_within_a_bucket(self, db_pool, seeded):
        from anveshak.api.db.timeline import get_timeline

        async with db_pool.acquire() as conn:
            result = await get_timeline(
                conn, seeded, org_id=TEST_ORG_ID, days=30, as_percentage=True
            )

        for bucket in result["buckets"]:
            if bucket["total"]:
                share = (
                    bucket["supporting"]
                    + bucket["opposing"]
                    + bucket["neutral"]
                    + bucket["unsupported_language"]
                )
                assert share == pytest.approx(100.0, abs=0.05)


class TestDataAvailability:
    async def test_a_constrained_platform_is_reported(self, db_pool, seeded):
        from anveshak.api.db.timeline import get_timeline

        async with db_pool.acquire() as conn:
            result = await get_timeline(conn, seeded, org_id=TEST_ORG_ID, days=30)

        platforms = {p["platform"] for p in result["constrained_platforms"]}
        assert "twitter" in platforms


class TestOrgIsolation:
    async def test_another_org_sees_nothing(self, db_pool, seeded, other_org):
        from anveshak.api.db.timeline import get_timeline

        async with db_pool.acquire() as conn:
            result = await get_timeline(conn, seeded, org_id=other_org, days=30)

        assert result["buckets"] == []
        assert result["excluded_no_publication_time"] == 0
        assert result["constrained_platforms"] == []
