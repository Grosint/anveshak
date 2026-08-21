"""Migration tests for the org multi-tenancy and RLS schema.

Checks that the organizations table, org_id columns, org_sources table,
and RLS policies exist after migration. This schema originally arrived as
007_organizations and 008_rls_policies, both since squashed into
001_initial_schema, so nothing here names a migration file.

Schema only. The default org is seed data, not migration data: migration 007
backfilled it, the squashed schema creates the tables empty, and
scripts/seed_demo.sql owns it now. The test DB is never seeded, so asserting
it here could only ever skip. That assertion lives in
tests/unit/test_org_multitenancy.py::TestSeedDefaultOrg, against the seed SQL.

Requires: Docker Compose (PostgreSQL), migrations applied.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.migration, pytest.mark.asyncio]


class TestOrgSchema:
    async def test_organizations_table_exists(self, db_pool):
        async with db_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'organizations')"
            )
        assert exists, "organizations table must exist"

    async def test_org_sources_table_exists(self, db_pool):
        async with db_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'org_sources')"
            )
        assert exists, "org_sources table must exist"

    async def test_topics_has_org_id_column(self, db_pool):
        async with db_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'topics' AND column_name = 'org_id')"
            )
        assert exists, "topics.org_id column must exist"

    async def test_users_has_org_id_column(self, db_pool):
        async with db_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'org_id')"
            )
        assert exists, "users.org_id column must exist"

    async def test_content_items_has_org_id_column(self, db_pool):
        async with db_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'content_items' AND column_name = 'org_id')"
            )
        assert exists, "content_items.org_id column must exist"

    async def test_credibility_audit_log_has_org_id_column(self, db_pool):
        async with db_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'credibility_audit_log' AND column_name = 'org_id')"
            )
        assert exists, "credibility_audit_log.org_id column must exist"

    async def test_topics_org_id_index_exists(self, db_pool):
        async with db_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_indexes "
                "WHERE tablename = 'topics' AND indexname = 'idx_topics_org')"
            )
        assert exists, "idx_topics_org index must exist"


class TestRLSSchema:
    async def test_rls_enabled_on_topics(self, db_pool):
        async with db_pool.acquire() as conn:
            enabled = await conn.fetchval(
                "SELECT relrowsecurity FROM pg_class WHERE relname = 'topics'"
            )
        assert enabled is True, "RLS must be enabled on topics"

    async def test_rls_enabled_on_content_items(self, db_pool):
        async with db_pool.acquire() as conn:
            enabled = await conn.fetchval(
                "SELECT relrowsecurity FROM pg_class WHERE relname = 'content_items'"
            )
        assert enabled is True, "RLS must be enabled on content_items"

    async def test_rls_enabled_on_users(self, db_pool):
        async with db_pool.acquire() as conn:
            enabled = await conn.fetchval(
                "SELECT relrowsecurity FROM pg_class WHERE relname = 'users'"
            )
        assert enabled is True, "RLS must be enabled on users"

    async def test_rls_policy_exists_for_topics(self, db_pool):
        async with db_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_policies "
                "WHERE tablename = 'topics' AND policyname = 'org_isolation_topics')"
            )
        assert exists, "RLS policy org_isolation_topics must exist"
