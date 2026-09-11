"""Content feed date filter against real PostgreSQL - issue #49.

A backfilled Source is collected today and published months ago. Filtering
the evidence feed to the week the story ran must return those items, which
only holds if the query filters on publication time. The mocked unit tests
pin the SQL shape; these pin that the SQL means what it says.

Requires: make up (PostgreSQL running)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest
from anveshak.api.db.topics import get_topic_content

from tests.conftest import LABELS_JSON, TEST_ORG_ID

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

# The week the analyst wants to read.
WINDOW_FROM = datetime(2026, 3, 2, 0, 0, tzinfo=UTC)
WINDOW_TO = datetime(2026, 3, 8, 23, 59, 59, 999999, tzinfo=UTC)

# Collection happened long after publication, as it does for any backfill.
COLLECTED = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


async def _insert(
    pool: asyncpg.Pool,
    topic_id: str,
    source_id: str,
    text: str,
    *,
    published_at: datetime | None,
    captured_at: datetime,
) -> str:
    item_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO content_items (
                id, topic_id, source_id, org_id, raw_text, clean_text, language,
                content_hash, url, captured_at, published_at,
                credibility_score_at_capture, created_at, updated_at, labels
            )
            VALUES ($1,$2,$3,$4,$5,$5,'en',$6,$7,$8,$9,75.0,$8,$8,$10)
            """,
            item_id,
            topic_id,
            source_id,
            TEST_ORG_ID,
            text,
            item_id,  # content_hash — unique per row, these are not duplicates
            f"https://example.com/{item_id[:8]}",
            captured_at,
            published_at,
            LABELS_JSON,
        )
    return item_id


@pytest.fixture
async def cleanup_content(db_pool: asyncpg.Pool):
    created: list[str] = []
    yield created
    if created:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM content_items WHERE id = ANY($1::text[])", created)


async def _feed(db_pool: asyncpg.Pool, topic_id: str, **kwargs: Any) -> list[dict[str, Any]]:
    async with db_pool.acquire() as conn:
        return await get_topic_content(
            conn,
            topic_id,
            kwargs.pop("limit", 50),
            kwargs.pop("offset", 0),
            None,
            None,
            **kwargs,
        )


class TestFilterReadsPublicationTime:
    async def test_published_in_window_is_returned_though_collected_outside_it(
        self, db_pool, make_topic, make_source, cleanup_content
    ) -> None:
        """The backfill case the filter exists for."""
        topic_id = await make_topic(name="Date filter published in window")
        source_id = await make_source(name="Date filter source in window")
        item_id = await _insert(
            db_pool,
            topic_id,
            source_id,
            "published during the window, collected months later",
            published_at=datetime(2026, 3, 4, 9, 0, tzinfo=UTC),
            captured_at=COLLECTED,
        )
        cleanup_content.append(item_id)

        rows = await _feed(db_pool, topic_id, date_from=WINDOW_FROM, date_to=WINDOW_TO)

        assert [r["id"] for r in rows] == [item_id]

    async def test_published_outside_window_is_excluded_though_collected_inside_it(
        self, db_pool, make_topic, make_source, cleanup_content
    ) -> None:
        """Capture time inside the window must not pull in an older story."""
        topic_id = await make_topic(name="Date filter published outside window")
        source_id = await make_source(name="Date filter source outside window")
        item_id = await _insert(
            db_pool,
            topic_id,
            source_id,
            "published long before the window, collected during it",
            published_at=datetime(2025, 11, 20, 9, 0, tzinfo=UTC),
            captured_at=datetime(2026, 3, 4, 9, 0, tzinfo=UTC),
        )
        cleanup_content.append(item_id)

        rows = await _feed(db_pool, topic_id, date_from=WINDOW_FROM, date_to=WINDOW_TO)

        assert rows == []

    async def test_unknown_publication_time_falls_back_to_capture_time(
        self, db_pool, make_topic, make_source, cleanup_content
    ) -> None:
        """Evidence with no publication time stays reachable, not hidden."""
        topic_id = await make_topic(name="Date filter null publication time")
        source_id = await make_source(name="Date filter source null pubtime")
        item_id = await _insert(
            db_pool,
            topic_id,
            source_id,
            "no publication time, captured inside the window",
            published_at=None,
            captured_at=datetime(2026, 3, 4, 9, 0, tzinfo=UTC),
        )
        cleanup_content.append(item_id)

        rows = await _feed(db_pool, topic_id, date_from=WINDOW_FROM, date_to=WINDOW_TO)

        assert [r["id"] for r in rows] == [item_id]

    async def test_end_of_window_day_is_included(
        self, db_pool, make_topic, make_source, cleanup_content
    ) -> None:
        topic_id = await make_topic(name="Date filter last day")
        source_id = await make_source(name="Date filter source last day")
        item_id = await _insert(
            db_pool,
            topic_id,
            source_id,
            "published late on the last day of the window",
            published_at=datetime(2026, 3, 8, 23, 45, tzinfo=UTC),
            captured_at=COLLECTED,
        )
        cleanup_content.append(item_id)

        rows = await _feed(db_pool, topic_id, date_from=WINDOW_FROM, date_to=WINDOW_TO)

        assert [r["id"] for r in rows] == [item_id]

    async def test_no_bounds_returns_everything(
        self, db_pool, make_topic, make_source, cleanup_content
    ) -> None:
        topic_id = await make_topic(name="Date filter unbounded")
        source_id = await make_source(name="Date filter source unbounded")
        for offset_day, published in ((1, datetime(2026, 3, 4, tzinfo=UTC)), (2, None)):
            item_id = await _insert(
                db_pool,
                topic_id,
                source_id,
                f"unbounded item {offset_day}",
                published_at=published,
                captured_at=COLLECTED,
            )
            cleanup_content.append(item_id)

        rows = await _feed(db_pool, topic_id)

        assert len(rows) == 2

    async def test_feed_row_carries_publication_time(
        self, db_pool, make_topic, make_source, cleanup_content
    ) -> None:
        """The card shows the timestamp the filter acted on, so the row carries it."""
        topic_id = await make_topic(name="Date filter row shape")
        source_id = await make_source(name="Date filter source row shape")
        published = datetime(2026, 3, 4, 9, 0, tzinfo=UTC)
        item_id = await _insert(
            db_pool,
            topic_id,
            source_id,
            "row shape item",
            published_at=published,
            captured_at=COLLECTED,
        )
        cleanup_content.append(item_id)

        rows = await _feed(db_pool, topic_id)

        assert rows[0]["published_at"] == published
        assert rows[0]["captured_at"] == COLLECTED


class TestFilterComposesWithPagination:
    async def test_pages_cover_the_filtered_set_only(
        self, db_pool, make_topic, make_source, cleanup_content
    ) -> None:
        """Filtering in the query means a page is a page of matches, not of rows."""
        topic_id = await make_topic(name="Date filter pagination")
        source_id = await make_source(name="Date filter source pagination")

        in_window = []
        for day in (3, 4, 5):
            item_id = await _insert(
                db_pool,
                topic_id,
                source_id,
                f"in window, published on March {day}",
                published_at=datetime(2026, 3, day, 10, 0, tzinfo=UTC),
                captured_at=datetime(2026, 9, 1, 12, day, tzinfo=UTC),
            )
            in_window.append(item_id)
            cleanup_content.append(item_id)

        for day in (10, 11):
            item_id = await _insert(
                db_pool,
                topic_id,
                source_id,
                f"outside window, published on January {day}",
                published_at=datetime(2026, 1, day, 10, 0, tzinfo=UTC),
                captured_at=datetime(2026, 9, 1, 13, day, tzinfo=UTC),
            )
            cleanup_content.append(item_id)

        first = await _feed(
            db_pool, topic_id, limit=2, offset=0, date_from=WINDOW_FROM, date_to=WINDOW_TO
        )
        second = await _feed(
            db_pool, topic_id, limit=2, offset=2, date_from=WINDOW_FROM, date_to=WINDOW_TO
        )

        assert len(first) == 2
        assert len(second) == 1
        assert sorted(r["id"] for r in first + second) == sorted(in_window)
