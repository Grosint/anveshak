"""The seeded demonstration analyst, checked at the API seam - issue #41.

The claim this file defends is that organisation isolation is real rather than
described. It is asserted the way an evaluating officer would test it: log in
over HTTP as the seeded analyst, then ask the API what that analyst can see.

Unit tests cover the seed plan without a database. Here the plan is applied to
real PostgreSQL and driven through the real FastAPI application, because the
interesting failures live in the seams: a password hash the login route cannot
verify, a JWT missing org_id, or a list route that forgets to filter.

Requires: Docker Compose (PostgreSQL). Run: make test-integration
"""

from __future__ import annotations

import uuid
from typing import AsyncIterator

import asyncpg
import httpx
import pytest
from anveshak.api.db.pool import get_db
from anveshak.api.main import app
from anveshak.api.middleware.rate_limit import _windows

from scripts.seed_demo_org import apply_plan, build_plan, warn_about_stale_accounts

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

LABELS = '{"classification":"OPEN","domain":"osint"}'

ANALYST_PASSWORD = "seam-analyst-password"
SUPERADMIN_PASSWORD = "seam-superadmin-password"

SEED_ENV = {
    "ANVESHAK_DEMO_ANALYST_USERNAME": "seam-analyst@anveshak.test",
    "ANVESHAK_DEMO_ANALYST_PASSWORD": ANALYST_PASSWORD,
    "ANVESHAK_DEMO_ADMIN_USERNAME": "seam-admin@anveshak.test",
    "ANVESHAK_DEMO_ADMIN_PASSWORD": "seam-admin-password",
    "ANVESHAK_DEMO_SUPERADMIN_USERNAME": "seam-superadmin@anveshak.test",
    "ANVESHAK_DEMO_SUPERADMIN_PASSWORD": SUPERADMIN_PASSWORD,
}


async def _create_org(conn: asyncpg.Connection, slug: str) -> str:
    org_id = f"org-{slug}"
    await conn.execute(
        "INSERT INTO organizations (id, name, slug, is_active, created_at, updated_at, labels) "
        "VALUES ($1, $2, $3, true, NOW(), NOW(), $4::jsonb) ON CONFLICT (id) DO NOTHING",
        org_id,
        slug,
        slug,
        LABELS,
    )
    return org_id


async def _create_topic(conn: asyncpg.Connection, name: str, org_id: str) -> str:
    topic_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO topics (id, name, keywords, signal_threshold, status, "
        "created_at, updated_at, labels, org_id) "
        "VALUES ($1, $2, $3, 2, 'active', NOW(), NOW(), $4::jsonb, $5)",
        topic_id,
        name,
        ["seam"],
        LABELS,
        org_id,
    )
    return topic_id


@pytest.fixture
async def seeded(db_pool: asyncpg.Pool) -> AsyncIterator[dict[str, str]]:
    """Seed the demonstration organisation plus a second, unrelated one."""
    plan = build_plan(SEED_ENV)
    other_slug = "seam-other"

    async with db_pool.acquire() as conn:
        await apply_plan(conn, plan)
        other_org = await _create_org(conn, other_slug)
        own_topic = await _create_topic(conn, "Seam own topic", plan.org_id)
        other_topic = await _create_topic(conn, "Seam other topic", other_org)

    yield {
        "org_id": plan.org_id,
        "other_org_id": other_org,
        "own_topic": own_topic,
        "other_topic": other_topic,
    }

    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM topics WHERE id = ANY($1::text[])", [own_topic, other_topic]
        )
        # By username, not by id: an account that already existed keeps its
        # own id through ON CONFLICT (username) DO UPDATE, so deleting by the
        # derived id would silently delete nothing.
        await conn.execute(
            "DELETE FROM users WHERE username = ANY($1::text[])",
            [a.username for a in plan.accounts],
        )
        # The seeded organisation stays: it is the one the SQL corpus and the
        # other integration tests share. Only the org this test invented goes.
        await conn.execute("DELETE FROM organizations WHERE id = $1", other_org)


@pytest.fixture
async def client(db_pool: asyncpg.Pool) -> AsyncIterator[httpx.AsyncClient]:
    """The real application, talking to the test database.

    The lifespan is not run: it would open a second pool against the
    development database and pre-warm Ollama, neither of which this test wants.
    """

    # Login is rate limited to 10 per minute per IP, and every test here logs
    # in. Without this the later tests read as 429 rather than as themselves.
    _windows.clear()

    async def _override_get_db() -> AsyncIterator[asyncpg.Connection]:
        async with db_pool.acquire() as conn:
            yield conn

    app.dependency_overrides[get_db] = _override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://seam") as http:
        yield http
    app.dependency_overrides.pop(get_db, None)


async def _login(client: httpx.AsyncClient, username: str, password: str) -> httpx.Response:
    return await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. The seeded analyst can authenticate
# ---------------------------------------------------------------------------


class TestSeededAnalystAuthenticates:
    async def test_login_with_the_seeded_password_succeeds(
        self, client: httpx.AsyncClient, seeded: dict[str, str]
    ) -> None:
        response = await _login(
            client, SEED_ENV["ANVESHAK_DEMO_ANALYST_USERNAME"], ANALYST_PASSWORD
        )
        assert response.status_code == 200, response.text
        assert response.json()["access_token"]

    async def test_login_with_a_wrong_password_fails(
        self, client: httpx.AsyncClient, seeded: dict[str, str]
    ) -> None:
        response = await _login(
            client, SEED_ENV["ANVESHAK_DEMO_ANALYST_USERNAME"], ANALYST_PASSWORD + "-wrong"
        )
        assert response.status_code == 401

    async def test_token_carries_the_analyst_role_and_organisation(
        self, client: httpx.AsyncClient, seeded: dict[str, str]
    ) -> None:
        login = await _login(client, SEED_ENV["ANVESHAK_DEMO_ANALYST_USERNAME"], ANALYST_PASSWORD)
        me = await client.get("/api/v1/auth/me", headers=_auth(login.json()["access_token"]))
        assert me.status_code == 200, me.text
        assert me.json()["role"] == "analyst"
        assert me.json()["org_id"] == seeded["org_id"]

    async def test_a_rerun_of_the_seed_keeps_the_login_working(
        self,
        client: httpx.AsyncClient,
        seeded: dict[str, str],
        db_pool: asyncpg.Pool,
    ) -> None:
        # Reproducibility is the point of the script: seeding twice must not
        # produce a duplicate username error or a stale hash.
        async with db_pool.acquire() as conn:
            await apply_plan(conn, build_plan(SEED_ENV))
        response = await _login(
            client, SEED_ENV["ANVESHAK_DEMO_ANALYST_USERNAME"], ANALYST_PASSWORD
        )
        assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# 2. The analyst sees their organisation only
# ---------------------------------------------------------------------------


class TestOrganisationIsolationAtTheSeam:
    async def test_analyst_sees_their_own_topic(
        self, client: httpx.AsyncClient, seeded: dict[str, str]
    ) -> None:
        login = await _login(client, SEED_ENV["ANVESHAK_DEMO_ANALYST_USERNAME"], ANALYST_PASSWORD)
        topics = await client.get("/api/v1/topics", headers=_auth(login.json()["access_token"]))
        assert topics.status_code == 200, topics.text
        assert seeded["own_topic"] in {t["id"] for t in topics.json()}

    async def test_analyst_does_not_see_another_organisations_topic(
        self, client: httpx.AsyncClient, seeded: dict[str, str]
    ) -> None:
        login = await _login(client, SEED_ENV["ANVESHAK_DEMO_ANALYST_USERNAME"], ANALYST_PASSWORD)
        topics = await client.get("/api/v1/topics", headers=_auth(login.json()["access_token"]))
        assert seeded["other_topic"] not in {t["id"] for t in topics.json()}

    async def test_another_organisations_topic_is_404_by_id(
        self, client: httpx.AsyncClient, seeded: dict[str, str]
    ) -> None:
        # Isolation has to hold on direct access too, not only on the list.
        login = await _login(client, SEED_ENV["ANVESHAK_DEMO_ANALYST_USERNAME"], ANALYST_PASSWORD)
        response = await client.get(
            f"/api/v1/topics/{seeded['other_topic']}",
            headers=_auth(login.json()["access_token"]),
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 3. The super-admin is platform-wide
# ---------------------------------------------------------------------------


class TestSeededSuperAdmin:
    async def test_super_admin_sees_both_organisations_topics(
        self, client: httpx.AsyncClient, seeded: dict[str, str]
    ) -> None:
        login = await _login(
            client, SEED_ENV["ANVESHAK_DEMO_SUPERADMIN_USERNAME"], SUPERADMIN_PASSWORD
        )
        assert login.status_code == 200, login.text
        topics = await client.get("/api/v1/topics", headers=_auth(login.json()["access_token"]))
        ids = {t["id"] for t in topics.json()}
        assert {seeded["own_topic"], seeded["other_topic"]} <= ids

    async def test_super_admin_may_create_an_organisation(
        self,
        client: httpx.AsyncClient,
        seeded: dict[str, str],
        db_pool: asyncpg.Pool,
    ) -> None:
        # User story 1: the role exists so that organisations can be created.
        login = await _login(
            client, SEED_ENV["ANVESHAK_DEMO_SUPERADMIN_USERNAME"], SUPERADMIN_PASSWORD
        )
        created = await client.post(
            "/api/v1/organizations",
            json={"name": "Seam Created Org", "slug": "seam-created"},
            headers=_auth(login.json()["access_token"]),
        )
        assert created.status_code == 201, created.text
        org_id = created.json()["org_id"]
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM organizations WHERE id = $1", org_id)

    async def test_analyst_may_not_create_an_organisation(
        self, client: httpx.AsyncClient, seeded: dict[str, str]
    ) -> None:
        login = await _login(client, SEED_ENV["ANVESHAK_DEMO_ANALYST_USERNAME"], ANALYST_PASSWORD)
        response = await client.post(
            "/api/v1/organizations",
            json={"name": "Seam Forbidden Org", "slug": "seam-forbidden"},
            headers=_auth(login.json()["access_token"]),
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# 4. Rerunning the seed against a database that has moved on
# ---------------------------------------------------------------------------


class TestRerunAgainstExistingRows:
    async def test_a_rotated_password_replaces_the_old_one(
        self,
        client: httpx.AsyncClient,
        seeded: dict[str, str],
        db_pool: asyncpg.Pool,
    ) -> None:
        rotated = dict(SEED_ENV, ANVESHAK_DEMO_ANALYST_PASSWORD="rotated-analyst-password")
        async with db_pool.acquire() as conn:
            await apply_plan(conn, build_plan(rotated))

        stale = await _login(client, SEED_ENV["ANVESHAK_DEMO_ANALYST_USERNAME"], ANALYST_PASSWORD)
        fresh = await _login(
            client, SEED_ENV["ANVESHAK_DEMO_ANALYST_USERNAME"], "rotated-analyst-password"
        )
        assert stale.status_code == 401
        assert fresh.status_code == 200, fresh.text

    async def test_a_deactivated_organisation_stays_deactivated(
        self,
        client: httpx.AsyncClient,
        seeded: dict[str, str],
        db_pool: asyncpg.Pool,
    ) -> None:
        # Reactivating an org an operator switched off would be this script
        # overruling them.
        plan = build_plan(SEED_ENV)
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE organizations SET is_active = false WHERE id = $1", plan.org_id
            )
            await apply_plan(conn, plan)
            is_active = await conn.fetchval(
                "SELECT is_active FROM organizations WHERE id = $1", plan.org_id
            )
        assert is_active is False

    async def test_a_renamed_account_is_reported_rather_than_left_silent(
        self,
        client: httpx.AsyncClient,
        seeded: dict[str, str],
        db_pool: asyncpg.Pool,
    ) -> None:
        renamed = dict(SEED_ENV, ANVESHAK_DEMO_ANALYST_USERNAME="seam-renamed@anveshak.test")
        plan = build_plan(renamed)
        async with db_pool.acquire() as conn:
            await apply_plan(conn, plan)
            try:
                stale = await warn_about_stale_accounts(conn, plan)
                assert SEED_ENV["ANVESHAK_DEMO_ANALYST_USERNAME"] in stale
            finally:
                await conn.execute(
                    "DELETE FROM users WHERE username = $1", "seam-renamed@anveshak.test"
                )
