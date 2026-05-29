"""Integration tests — multi-tenancy org isolation with real PostgreSQL.

Tests verify that org_id filtering actually works at the database level,
not just in mocked unit tests. These catch SQL bugs that mocks can't.

Requires: Docker Compose (PostgreSQL), migration 007+008 applied.
Run: make test-integration or pytest tests/integration/ -m integration
"""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

LABELS = '{"classification":"OPEN","domain":"osint"}'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_org(conn, name: str, slug: str) -> str:
    org_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO organizations (id, name, slug, is_active, created_at, updated_at, labels) "
        "VALUES ($1, $2, $3, true, NOW(), NOW(), $4::jsonb)",
        org_id, name, slug, LABELS,
    )
    return org_id


async def _create_topic(conn, name: str, org_id: str) -> str:
    topic_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO topics (id, name, keywords, signal_threshold, status, "
        "created_at, updated_at, labels, org_id) "
        "VALUES ($1, $2, $3, 2, 'active', NOW(), NOW(), $4::jsonb, $5)",
        topic_id, name, ["test"], LABELS, org_id,
    )
    return topic_id


async def _create_source(conn, name: str, org_id: str) -> str:
    source_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO sources (id, name, url_or_handle, platform, credibility_score, "
        "is_active, created_at, updated_at, labels, org_id) "
        "VALUES ($1, $2, $3, 'web', 75.0, true, NOW(), NOW(), $4::jsonb, $5)",
        source_id, name, f"https://{name.lower().replace(' ', '-')}.com", LABELS, org_id,
    )
    # Link to org_sources
    await conn.execute(
        "INSERT INTO org_sources (org_id, source_id) VALUES ($1, $2)",
        org_id, source_id,
    )
    return source_id


# ---------------------------------------------------------------------------
# 1. Topic isolation
# ---------------------------------------------------------------------------

class TestTopicOrgIsolation:

    async def test_list_topics_by_org_returns_only_own_topics(self, db_conn):
        """Topics from org-B must not appear in org-A's list."""
        from anveshak.api.db.topics import list_topics_by_org

        org_a = await _create_org(db_conn, "Org A", f"org-a-{uuid.uuid4().hex[:6]}")
        org_b = await _create_org(db_conn, "Org B", f"org-b-{uuid.uuid4().hex[:6]}")

        topic_a = await _create_topic(db_conn, "Topic Alpha", org_a)
        topic_b = await _create_topic(db_conn, "Topic Beta", org_b)

        topics_for_a = await list_topics_by_org(db_conn, org_a)
        topics_for_b = await list_topics_by_org(db_conn, org_b)

        topic_ids_a = {t["id"] for t in topics_for_a}
        topic_ids_b = {t["id"] for t in topics_for_b}

        assert topic_a in topic_ids_a
        assert topic_b not in topic_ids_a
        assert topic_b in topic_ids_b
        assert topic_a not in topic_ids_b

    async def test_verify_topic_access_blocks_cross_org(self, db_conn):
        """verify_topic_access raises 404 for wrong org."""
        from fastapi import HTTPException
        from anveshak.api.db.topics import verify_topic_access

        org_a = await _create_org(db_conn, "Org A", f"org-a-{uuid.uuid4().hex[:6]}")
        org_b = await _create_org(db_conn, "Org B", f"org-b-{uuid.uuid4().hex[:6]}")
        topic_a = await _create_topic(db_conn, "Topic Alpha", org_a)

        # User from org-B tries to access org-A's topic
        user_b = {"sub": "u1", "role": "analyst", "org_id": org_b}
        with pytest.raises(HTTPException) as exc_info:
            await verify_topic_access(db_conn, topic_a, user_b)
        assert exc_info.value.status_code == 404

    async def test_verify_topic_access_allows_same_org(self, db_conn):
        """verify_topic_access passes for same org."""
        from anveshak.api.db.topics import verify_topic_access

        org_a = await _create_org(db_conn, "Org A", f"org-a-{uuid.uuid4().hex[:6]}")
        topic_a = await _create_topic(db_conn, "Topic Alpha", org_a)

        user_a = {"sub": "u1", "role": "analyst", "org_id": org_a}
        # Should not raise
        await verify_topic_access(db_conn, topic_a, user_a)

    async def test_verify_topic_access_super_admin_bypass(self, db_conn):
        """Super-admin bypasses topic access check."""
        from anveshak.api.db.topics import verify_topic_access

        org_a = await _create_org(db_conn, "Org A", f"org-a-{uuid.uuid4().hex[:6]}")
        topic_a = await _create_topic(db_conn, "Topic Alpha", org_a)

        super_admin = {"sub": "sa-1", "role": "super-admin"}
        # Should not raise — super-admin sees all
        await verify_topic_access(db_conn, topic_a, super_admin)


# ---------------------------------------------------------------------------
# 2. Source isolation via org_sources
# ---------------------------------------------------------------------------

class TestSourceOrgIsolation:

    async def test_list_sources_by_org_filters_via_org_sources(self, db_conn):
        """Only sources linked in org_sources are visible to the org."""
        from anveshak.api.db.sources import list_sources_by_org

        org_a = await _create_org(db_conn, "Org A", f"org-a-{uuid.uuid4().hex[:6]}")
        org_b = await _create_org(db_conn, "Org B", f"org-b-{uuid.uuid4().hex[:6]}")

        src_a = await _create_source(db_conn, "Source Alpha", org_a)
        src_b = await _create_source(db_conn, "Source Beta", org_b)

        sources_for_a = await list_sources_by_org(db_conn, org_a)
        source_ids_a = {s["id"] for s in sources_for_a}

        assert src_a in source_ids_a
        assert src_b not in source_ids_a

    async def test_verify_source_access_blocks_invisible_source(self, db_conn):
        """verify_source_access raises 404 for source not in org_sources."""
        from fastapi import HTTPException
        from anveshak.api.db.sources import verify_source_access

        org_a = await _create_org(db_conn, "Org A", f"org-a-{uuid.uuid4().hex[:6]}")
        org_b = await _create_org(db_conn, "Org B", f"org-b-{uuid.uuid4().hex[:6]}")
        src_b = await _create_source(db_conn, "Source Beta", org_b)

        user_a = {"sub": "u1", "role": "analyst", "org_id": org_a}
        with pytest.raises(HTTPException) as exc_info:
            await verify_source_access(db_conn, src_b, user_a)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 3. User isolation
# ---------------------------------------------------------------------------

class TestUserOrgIsolation:

    async def test_list_users_by_org_filters(self, db_conn):
        """list_users_by_org returns only users in that org."""
        from anveshak.api.db.users import list_users_by_org, create_user

        org_a = await _create_org(db_conn, "Org A", f"org-a-{uuid.uuid4().hex[:6]}")
        org_b = await _create_org(db_conn, "Org B", f"org-b-{uuid.uuid4().hex[:6]}")

        user_a_name = f"user-a-{uuid.uuid4().hex[:6]}@test"
        user_b_name = f"user-b-{uuid.uuid4().hex[:6]}@test"
        await create_user(db_conn, user_a_name, "pass123", "analyst", org_id=org_a)
        await create_user(db_conn, user_b_name, "pass123", "analyst", org_id=org_b)

        users_a = await list_users_by_org(db_conn, org_a)
        usernames_a = {u["username"] for u in users_a}

        assert user_a_name in usernames_a
        assert user_b_name not in usernames_a


# ---------------------------------------------------------------------------
# 4. Organization CRUD
# ---------------------------------------------------------------------------

class TestOrganizationCRUD:

    async def test_create_and_get_org(self, db_conn):
        """Create an org and retrieve it."""
        from anveshak.api.db.organizations import create_organization, get_organization

        slug = f"test-{uuid.uuid4().hex[:6]}"
        org_id = await create_organization(db_conn, "Test Org", slug)
        assert org_id is not None

        org = await get_organization(db_conn, org_id)
        assert org is not None
        assert org["name"] == "Test Org"
        assert org["slug"] == slug
        assert org["is_active"] is True

    async def test_list_organizations(self, db_conn):
        """List returns created orgs."""
        from anveshak.api.db.organizations import create_organization, list_organizations

        slug = f"list-{uuid.uuid4().hex[:6]}"
        await create_organization(db_conn, "List Test Org", slug)

        orgs = await list_organizations(db_conn)
        slugs = {o["slug"] for o in orgs}
        assert slug in slugs

    async def test_update_organization(self, db_conn):
        """Update org name and active status."""
        from anveshak.api.db.organizations import (
            create_organization, get_organization, update_organization,
        )

        slug = f"upd-{uuid.uuid4().hex[:6]}"
        org_id = await create_organization(db_conn, "Original Name", slug)

        await update_organization(db_conn, org_id, name="Updated Name", is_active=False)

        org = await get_organization(db_conn, org_id)
        assert org["name"] == "Updated Name"
        assert org["is_active"] is False


# ---------------------------------------------------------------------------
# 5. Signal isolation (signals inherit org via topic)
# ---------------------------------------------------------------------------

class TestSignalOrgIsolation:

    async def test_list_signals_by_org_filters_via_topic(self, db_conn):
        """Signals only appear for the org that owns the topic."""
        from anveshak.api.db.signals import list_signals_by_org

        org_a = await _create_org(db_conn, "Org A", f"org-a-{uuid.uuid4().hex[:6]}")
        org_b = await _create_org(db_conn, "Org B", f"org-b-{uuid.uuid4().hex[:6]}")

        topic_a = await _create_topic(db_conn, "Topic A", org_a)
        topic_b = await _create_topic(db_conn, "Topic B", org_b)

        # Insert signals for each topic
        sig_a = str(uuid.uuid4())
        sig_b = str(uuid.uuid4())
        for sig_id, tid in [(sig_a, topic_a), (sig_b, topic_b)]:
            await db_conn.execute(
                "INSERT INTO signals (id, topic_id, signal_type, description, "
                "status, created_at, updated_at, labels) "
                "VALUES ($1, $2, 'threshold_breach', 'test', 'new', NOW(), NOW(), $3::jsonb)",
                sig_id, tid, LABELS,
            )

        signals_a = await list_signals_by_org(db_conn, "new", org_a)
        signal_ids_a = {s["id"] for s in signals_a}

        assert sig_a in signal_ids_a
        assert sig_b not in signal_ids_a
