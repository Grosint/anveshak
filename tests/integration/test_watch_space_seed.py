"""Seeding a Watch Space - issues #25 and #52.

Asserts the seeder produces a Watch Space that is a Topic in every technical
respect: it lists like one, owns sources like one, and is rerunnable without
duplicating anything.

Every definition in the Watch Space directory is seeded, not one named file.
A domain that is added as configuration and never proved to seed is a file
nobody runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.conftest import POSTGRES_URL, TEST_ORG_ID

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

WATCH_SPACE_DIR = Path("infra/configs/watch_spaces")
SPECS = sorted(WATCH_SPACE_DIR.glob("*.yaml"))


@pytest.fixture(params=SPECS, ids=lambda path: path.stem)
def spec(request):
    return request.param


@pytest.fixture
async def seeded(db_pool, ensure_org, spec):
    """Seed the Watch Space, then remove everything it created."""
    from scripts.seed_watch_space import seed

    await seed(spec, POSTGRES_URL, TEST_ORG_ID)
    name = yaml.safe_load(spec.read_text())["name"]

    async with db_pool.acquire() as conn:
        topic_id = await conn.fetchval(
            "SELECT id FROM topics WHERE name = $1 AND org_id = $2",
            name,
            TEST_ORG_ID,
        )

    yield topic_id

    async with db_pool.acquire() as conn:
        source_ids = [
            r["source_id"]
            for r in await conn.fetch(
                "SELECT source_id FROM topic_sources WHERE topic_id = $1", topic_id
            )
        ]
        await conn.execute("DELETE FROM topic_sources WHERE topic_id = $1", topic_id)
        if source_ids:
            await conn.execute(
                "DELETE FROM org_sources WHERE source_id = ANY($1::text[])", source_ids
            )
            await conn.execute("DELETE FROM sources WHERE id = ANY($1::text[])", source_ids)
        await conn.execute("DELETE FROM topics WHERE id = $1", topic_id)


class TestSeededWatchSpace:
    async def test_it_is_created_and_marked(self, db_pool, seeded):
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT is_watch_space, status, keywords, languages FROM topics WHERE id = $1",
                seeded,
            )
        assert row["is_watch_space"] is True
        assert row["status"] == "active"
        assert len(row["keywords"]) >= 10
        assert set(row["languages"]) >= {"en", "hi"}

    async def test_its_sources_are_linked(self, db_pool, seeded):
        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM topic_sources WHERE topic_id = $1", seeded
            )
        assert 30 <= count <= 50

    async def test_sources_are_visible_to_the_organisation(self, db_pool, seeded):
        """Sources are global; visibility runs through org_sources."""
        async with db_pool.acquire() as conn:
            unlinked = await conn.fetchval(
                """
                SELECT COUNT(*) FROM topic_sources ts
                WHERE ts.topic_id = $1
                  AND NOT EXISTS (
                      SELECT 1 FROM org_sources os
                      WHERE os.source_id = ts.source_id AND os.org_id = $2
                  )
                """,
                seeded,
                TEST_ORG_ID,
            )
        assert unlinked == 0

    async def test_seeding_twice_creates_nothing_extra(self, db_pool, seeded, spec):
        from scripts.seed_watch_space import seed

        name = yaml.safe_load(spec.read_text())["name"]

        async with db_pool.acquire() as conn:
            before = await conn.fetchval(
                "SELECT COUNT(*) FROM topic_sources WHERE topic_id = $1", seeded
            )

        await seed(spec, POSTGRES_URL, TEST_ORG_ID)

        async with db_pool.acquire() as conn:
            topics = await conn.fetchval(
                "SELECT COUNT(*) FROM topics WHERE name = $1 AND org_id = $2",
                name,
                TEST_ORG_ID,
            )
            after = await conn.fetchval(
                "SELECT COUNT(*) FROM topic_sources WHERE topic_id = $1", seeded
            )

        assert topics == 1
        assert after == before

    async def test_it_lists_like_any_other_topic(self, db_pool, seeded):
        """Criterion 10 of the epic: no second set of concepts to learn."""
        from anveshak.api.db.topics import list_topics_by_org

        async with db_pool.acquire() as conn:
            topics = await list_topics_by_org(conn, TEST_ORG_ID)

        watch_spaces = [t for t in topics if t["id"] == seeded]
        assert len(watch_spaces) == 1
        assert watch_spaces[0]["is_watch_space"] is True
