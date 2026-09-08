"""Actor View organisation isolation — issue #35.

A handle is addressable by name, so a caller can ask for any handle they can
guess. These assert the query returns nothing across an organisation
boundary even when the handle exists on the other side.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import TEST_ORG_ID

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

OTHER_ORG_ID = "org-actor-view-other"
HANDLE = "publicaccount"


@pytest.fixture
async def other_org(db_pool):
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
            VALUES ($1, 'Other Org', 'actor-view-other', NOW(), NOW(),
                    '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            OTHER_ORG_ID,
        )
    return OTHER_ORG_ID


@pytest.fixture
async def scenario(db_pool, make_topic, make_source, other_org):
    """One handle posting in two topics owned by two organisations."""
    mine = await make_topic(name="Integration Test Topic actor mine")
    source_id = await make_source(name="Test Source actor", platform="twitter")

    theirs = str(uuid.uuid4())
    created_content: list[str] = []

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO topics (id, name, keywords, signal_threshold, status,
                                org_id, created_at, updated_at, labels)
            VALUES ($1, 'Integration Test Topic actor theirs', '{}', 2, 'active', $2,
                    NOW(), NOW(),
                    '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
            """,
            theirs,
            OTHER_ORG_ID,
        )

        for topic_id, org_id, count in ((mine, TEST_ORG_ID, 3), (theirs, OTHER_ORG_ID, 5)):
            for i in range(count):
                content_id = str(uuid.uuid4())
                created_content.append(content_id)
                await conn.execute(
                    """
                    INSERT INTO content_items (
                        id, topic_id, source_id, org_id, raw_text, clean_text,
                        content_hash, captured_at, published_at, labels
                    )
                    VALUES ($1, $2, $3, $4, $5, $5, $6, $7, $8, $9::jsonb)
                    """,
                    content_id,
                    topic_id,
                    source_id,
                    org_id,
                    f"post {content_id}",
                    content_id,
                    datetime.now(UTC),
                    datetime.now(UTC) - timedelta(days=i),
                    '{"classification":"OPEN","domain":"social","owner_org":"anveshak",'
                    f'"author_handle":"@{HANDLE}",'
                    '"engagement":{"likes":10,"views":100}}',
                )

    yield {"mine": mine, "theirs": theirs}

    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM content_items WHERE id = ANY($1::text[])", created_content)
        await conn.execute("DELETE FROM topics WHERE id = $1", theirs)
        await conn.execute("DELETE FROM organizations WHERE id = $1", OTHER_ORG_ID)


class TestActorViewIsolation:
    async def test_it_returns_the_handle_content_in_my_topic(self, db_pool, scenario):
        from anveshak.api.db.actors import list_actor_content

        async with db_pool.acquire() as conn:
            content = await list_actor_content(
                conn, scenario["mine"], f"@{HANDLE}", org_id=TEST_ORG_ID
            )
        assert len(content) == 3

    async def test_it_returns_nothing_across_an_org_boundary(self, db_pool, scenario):
        """The other organisation's topic exists and carries the same handle."""
        from anveshak.api.db.actors import list_actor_content

        async with db_pool.acquire() as conn:
            content = await list_actor_content(
                conn, scenario["theirs"], f"@{HANDLE}", org_id=TEST_ORG_ID
            )
        assert content == []

    async def test_the_summary_is_org_scoped_too(self, db_pool, scenario):
        from anveshak.api.db.actors import get_actor_summary

        async with db_pool.acquire() as conn:
            mine = await get_actor_summary(conn, scenario["mine"], HANDLE, org_id=TEST_ORG_ID)
            theirs = await get_actor_summary(conn, scenario["theirs"], HANDLE, org_id=TEST_ORG_ID)

        assert mine["post_count"] == 3
        assert theirs["post_count"] == 0

    async def test_activity_is_org_scoped_too(self, db_pool, scenario):
        from anveshak.api.db.actors import get_actor_activity

        async with db_pool.acquire() as conn:
            mine = await get_actor_activity(conn, scenario["mine"], HANDLE, org_id=TEST_ORG_ID)
            theirs = await get_actor_activity(conn, scenario["theirs"], HANDLE, org_id=TEST_ORG_ID)

        assert sum(day["post_count"] for day in mine) == 3
        assert theirs == []

    async def test_a_handle_matches_with_or_without_the_at_prefix(self, db_pool, scenario):
        from anveshak.api.db.actors import list_actor_content

        async with db_pool.acquire() as conn:
            with_at = await list_actor_content(
                conn, scenario["mine"], f"@{HANDLE}", org_id=TEST_ORG_ID
            )
            without_at = await list_actor_content(
                conn, scenario["mine"], HANDLE.upper(), org_id=TEST_ORG_ID
            )

        assert len(with_at) == len(without_at) == 3

    async def test_engagement_is_aggregated(self, db_pool, scenario):
        from anveshak.api.db.actors import get_actor_summary

        async with db_pool.acquire() as conn:
            summary = await get_actor_summary(conn, scenario["mine"], HANDLE, org_id=TEST_ORG_ID)

        assert summary["total_likes"] == 30
        assert summary["total_views"] == 300

    async def test_no_actor_row_is_written_by_reading(self, db_pool, scenario):
        """The view creates nothing. There is no table it could create it in."""
        from anveshak.api.db.actors import get_actor_summary

        async with db_pool.acquire() as conn:
            await get_actor_summary(conn, scenario["mine"], HANDLE, org_id=TEST_ORG_ID)
            exists = await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name LIKE 'actor%'"
            )
        assert exists == 0
