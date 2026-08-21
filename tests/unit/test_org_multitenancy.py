"""RED phase — Organization multi-tenancy tests (PR 1).

Tests for:
  1. JWT includes org_id claim
  2. Auth DB fetches org_id from user record
  3. Login embeds org_id in token
  4. /me endpoint returns org_id
  5. RBAC helpers: get_user_org, is_super_admin, require_org_context
  6. Organization DB CRUD: create, list, get, update
  7. User creation with org_id
  8. User listing filtered by org_id

pytest.mark.unit — no external dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tests.helpers.migrations import migrations_sql

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_token(
    subject: str = "user-1",
    username: str = "analyst",
    role: str = "analyst",
    org_id: str | None = "org-test",
) -> str:
    with patch("services.api.anveshak.api.auth.jwt.settings") as s:
        s.jwt_secret_key = "test-secret-for-org-tests"
        s.jwt_algorithm = "HS256"
        s.jwt_expire_minutes = 30
        from services.api.anveshak.api.auth.jwt import create_access_token

        return create_access_token(
            subject=subject,
            username=username,
            role=role,
            org_id=org_id,
        )


# ===================================================================
# 1. JWT payload includes org_id
# ===================================================================


class TestJWTOrgId:
    def test_token_contains_org_id(self):
        """Token payload must include org_id."""
        with patch("services.api.anveshak.api.auth.jwt.settings") as s:
            s.jwt_secret_key = "test-secret-for-org-tests"
            s.jwt_algorithm = "HS256"
            s.jwt_expire_minutes = 30
            from services.api.anveshak.api.auth.jwt import (
                create_access_token,
                verify_token,
            )

            token = create_access_token(
                subject="user-1",
                username="analyst",
                role="analyst",
                org_id="org-nia",
            )
            payload = verify_token(token)

        assert payload["org_id"] == "org-nia"

    def test_super_admin_token_has_null_org_id(self):
        """Super-admin token has org_id=None (null in JWT)."""
        with patch("services.api.anveshak.api.auth.jwt.settings") as s:
            s.jwt_secret_key = "test-secret-for-org-tests"
            s.jwt_algorithm = "HS256"
            s.jwt_expire_minutes = 30
            from services.api.anveshak.api.auth.jwt import (
                create_access_token,
                verify_token,
            )

            token = create_access_token(
                subject="sa-1",
                username="superadmin",
                role="super-admin",
                org_id=None,
            )
            payload = verify_token(token)

        assert payload.get("org_id") is None

    def test_org_id_defaults_to_none(self):
        """If org_id is not provided, it defaults to None."""
        with patch("services.api.anveshak.api.auth.jwt.settings") as s:
            s.jwt_secret_key = "test-secret-for-org-tests"
            s.jwt_algorithm = "HS256"
            s.jwt_expire_minutes = 30
            from services.api.anveshak.api.auth.jwt import (
                create_access_token,
                verify_token,
            )

            token = create_access_token(subject="user-1")
            payload = verify_token(token)

        # org_id should be None or absent when not provided
        assert payload.get("org_id") is None


# ===================================================================
# 2. Auth DB returns org_id
# ===================================================================


class TestAuthDBOrgId:
    def test_sql_includes_org_id(self):
        """SQL query for user lookup must select org_id."""
        from services.api.anveshak.api.db.auth import SQL_GET_USER_BY_USERNAME

        assert "org_id" in SQL_GET_USER_BY_USERNAME.lower()


# ===================================================================
# 3. Login embeds org_id in token
# ===================================================================


class TestLoginWithOrgId:
    @pytest.mark.asyncio
    async def test_login_returns_token_with_org_id(self, mock_conn):
        """Login response token must contain the user's org_id."""
        from services.api.anveshak.api.auth.jwt import pwd_context

        hashed = pwd_context.hash("password")

        with (
            patch(
                "services.api.anveshak.api.routes.auth.auth_db.get_user_by_username",
                new=AsyncMock(
                    return_value={
                        "id": "user-1",
                        "password_hash": hashed,
                        "role": "analyst",
                        "org_id": "org-nia",
                    }
                ),
            ),
            patch("services.api.anveshak.api.auth.jwt.settings") as s,
        ):
            s.jwt_secret_key = "test-secret-for-org-tests"
            s.jwt_algorithm = "HS256"
            s.jwt_expire_minutes = 30
            from services.api.anveshak.api.auth.jwt import verify_token
            from services.api.anveshak.api.routes.auth import LoginRequest, login

            result = await login(
                LoginRequest(username="analyst", password="password"),
                db=mock_conn,
            )
            payload = verify_token(result["access_token"])

        assert payload["org_id"] == "org-nia"


# ===================================================================
# 4. /me returns org_id
# ===================================================================


class TestAuthMeOrgId:
    @pytest.mark.asyncio
    async def test_me_returns_org_id(self):
        """GET /auth/me must include org_id in response."""
        from services.api.anveshak.api.routes.auth import me

        user = {
            "sub": "u1",
            "username": "analyst1",
            "role": "analyst",
            "jti": "x",
            "org_id": "org-nia",
        }
        result = await me(user=user)
        assert result["org_id"] == "org-nia"

    @pytest.mark.asyncio
    async def test_me_returns_null_org_for_super_admin(self):
        """GET /auth/me returns org_id=None for super-admin."""
        from services.api.anveshak.api.routes.auth import me

        user = {
            "sub": "sa-1",
            "username": "superadmin",
            "role": "super-admin",
            "jti": "x",
        }
        result = await me(user=user)
        assert result.get("org_id") is None


# ===================================================================
# 5. RBAC org helpers
# ===================================================================


class TestRBACOrgHelpers:
    def test_get_user_org_returns_org_id(self):
        """get_user_org() extracts org_id from user dict."""
        from services.api.anveshak.api.auth.rbac import get_user_org

        user = {"sub": "u1", "role": "analyst", "org_id": "org-nia"}
        assert get_user_org(user) == "org-nia"

    def test_get_user_org_returns_none_for_super_admin(self):
        """get_user_org() returns None when org_id is absent."""
        from services.api.anveshak.api.auth.rbac import get_user_org

        user = {"sub": "sa-1", "role": "super-admin"}
        assert get_user_org(user) is None

    def test_is_super_admin_true(self):
        """is_super_admin() returns True for super-admin role."""
        from services.api.anveshak.api.auth.rbac import is_super_admin

        user = {"sub": "sa-1", "role": "super-admin"}
        assert is_super_admin(user) is True

    def test_is_super_admin_false_for_admin(self):
        """is_super_admin() returns False for org admin."""
        from services.api.anveshak.api.auth.rbac import is_super_admin

        user = {"sub": "u1", "role": "admin"}
        assert is_super_admin(user) is False

    def test_require_org_context_returns_org_id(self):
        """require_org_context() returns org_id for regular user."""
        from services.api.anveshak.api.auth.rbac import require_org_context

        user = {"sub": "u1", "role": "analyst", "org_id": "org-nia"}
        assert require_org_context(user) == "org-nia"

    def test_require_org_context_raises_for_missing_org(self):
        """require_org_context() raises 400 when org_id is missing."""
        from fastapi import HTTPException

        from services.api.anveshak.api.auth.rbac import require_org_context

        user = {"sub": "sa-1", "role": "super-admin"}
        with pytest.raises(HTTPException) as exc_info:
            require_org_context(user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_super_admin_passes_require_role(self):
        """super-admin passes require_role('super-admin')."""
        from services.api.anveshak.api.auth.rbac import require_role

        dep = require_role("super-admin")
        user = {"sub": "sa-1", "username": "sa", "role": "super-admin", "jti": "x"}
        result = await dep(user)
        assert result == user


# ===================================================================
# 6. Organization DB CRUD
# ===================================================================


class TestOrganizationDB:
    @pytest.mark.asyncio
    async def test_create_org_returns_id(self):
        """create_organization() inserts and returns org ID."""
        from services.api.anveshak.api.db.organizations import create_organization

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value="org-new-id")

        org_id = await create_organization(mock_conn, "NIA", "nia")
        assert org_id == "org-new-id"
        mock_conn.fetchval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_orgs_returns_list(self):
        """list_organizations() returns list of dicts."""
        from services.api.anveshak.api.db.organizations import list_organizations

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": "org-1",
                    "name": "NIA",
                    "slug": "nia",
                    "is_active": True,
                    "created_at": "2026-01-01",
                    "updated_at": "2026-01-01",
                },
            ]
        )

        result = await list_organizations(mock_conn)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "NIA"

    @pytest.mark.asyncio
    async def test_get_org_returns_dict(self):
        """get_organization() returns a single org dict or None."""
        from services.api.anveshak.api.db.organizations import get_organization

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "id": "org-1",
                "name": "NIA",
                "slug": "nia",
                "is_active": True,
            }
        )

        result = await get_organization(mock_conn, "org-1")
        assert result is not None
        assert result["slug"] == "nia"

    @pytest.mark.asyncio
    async def test_get_org_returns_none_for_missing(self):
        """get_organization() returns None for non-existent org."""
        from services.api.anveshak.api.db.organizations import get_organization

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await get_organization(mock_conn, "org-nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_org_calls_execute(self):
        """update_organization() updates name and is_active."""
        from services.api.anveshak.api.db.organizations import update_organization

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        await update_organization(mock_conn, "org-1", name="NIA Updated", is_active=False)
        mock_conn.execute.assert_awaited_once()


# ===================================================================
# 7. User creation with org_id
# ===================================================================


class TestUserCreateWithOrg:
    @pytest.mark.asyncio
    async def test_create_user_accepts_org_id(self):
        """create_user() must accept org_id parameter."""
        from anveshak.api.db.users import create_user

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value="user-new")

        user_id = await create_user(
            mock_conn,
            "newuser",
            "password123",
            "analyst",
            org_id="org-nia",
        )
        assert user_id == "user-new"
        mock_conn.fetchval.assert_awaited_once()

        # Verify org_id was passed as SQL parameter
        call_args = mock_conn.fetchval.call_args
        sql_params = call_args[0]
        assert "org-nia" in sql_params

    @pytest.mark.asyncio
    async def test_sql_create_user_includes_org_id(self):
        """SQL_CREATE_USER must include org_id column."""
        from anveshak.api.db.users import SQL_CREATE_USER

        assert "org_id" in SQL_CREATE_USER.lower()


# ===================================================================
# 8. User listing with org filter
# ===================================================================


class TestUserListWithOrg:
    @pytest.mark.asyncio
    async def test_list_users_returns_org_id(self):
        """list_users() results must include org_id field."""
        from anveshak.api.db.users import list_users

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": "u1",
                    "username": "a",
                    "role": "analyst",
                    "org_id": "org-nia",
                    "created_at": "2026-01-01",
                    "updated_at": "2026-01-01",
                },
            ]
        )

        result = await list_users(mock_conn)
        assert result[0]["org_id"] == "org-nia"

    @pytest.mark.asyncio
    async def test_list_users_by_org_exists(self):
        """list_users_by_org() function must exist for org-scoped listing."""
        from anveshak.api.db.users import list_users_by_org

        assert callable(list_users_by_org)

    @pytest.mark.asyncio
    async def test_list_users_by_org_filters(self):
        """list_users_by_org() passes org_id to SQL filter."""
        from anveshak.api.db.users import list_users_by_org

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        await list_users_by_org(mock_conn, "org-nia")
        call_args = mock_conn.fetch.call_args
        assert "org-nia" in call_args[0]


# ===================================================================
# 9. Organization route handlers
# ===================================================================


class TestOrgRoutes:
    @pytest.mark.asyncio
    async def test_list_orgs_route_calls_db(self):
        """GET /organizations calls list_organizations."""
        with patch(
            "services.api.anveshak.api.routes.organizations.org_db.list_organizations",
            new=AsyncMock(return_value=[{"id": "org-1", "name": "NIA", "slug": "nia"}]),
        ):
            from services.api.anveshak.api.routes.organizations import list_organizations

            mock_conn = AsyncMock()
            user = {"sub": "sa-1", "role": "super-admin", "jti": "x"}
            result = await list_organizations(db=mock_conn, _user=user)

        assert len(result) == 1
        assert result[0]["name"] == "NIA"

    @pytest.mark.asyncio
    async def test_create_org_route_returns_id(self):
        """POST /organizations returns org_id."""
        with patch(
            "services.api.anveshak.api.routes.organizations.org_db.create_organization",
            new=AsyncMock(return_value="org-new"),
        ):
            from services.api.anveshak.api.routes.organizations import (
                CreateOrgRequest,
                create_organization,
            )

            mock_conn = AsyncMock()
            user = {"sub": "sa-1", "role": "super-admin", "jti": "x"}
            req = CreateOrgRequest(name="NIA", slug="nia")
            result = await create_organization(req=req, db=mock_conn, _user=user)

        assert result["org_id"] == "org-new"

    @pytest.mark.asyncio
    async def test_get_org_route_returns_org(self):
        """GET /organizations/{id} returns org dict."""
        with patch(
            "services.api.anveshak.api.routes.organizations.org_db.get_organization",
            new=AsyncMock(return_value={"id": "org-1", "name": "NIA", "slug": "nia"}),
        ):
            from services.api.anveshak.api.routes.organizations import get_organization

            mock_conn = AsyncMock()
            user = {"sub": "sa-1", "role": "super-admin", "jti": "x"}
            result = await get_organization(org_id="org-1", db=mock_conn, _user=user)

        assert result["name"] == "NIA"

    @pytest.mark.asyncio
    async def test_get_org_route_404_for_missing(self):
        """GET /organizations/{id} returns 404 for non-existent org."""
        from fastapi import HTTPException

        with patch(
            "services.api.anveshak.api.routes.organizations.org_db.get_organization",
            new=AsyncMock(return_value=None),
        ):
            from services.api.anveshak.api.routes.organizations import get_organization

            mock_conn = AsyncMock()
            user = {"sub": "sa-1", "role": "super-admin", "jti": "x"}
            with pytest.raises(HTTPException) as exc_info:
                await get_organization(org_id="missing", db=mock_conn, _user=user)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_org_route(self):
        """PATCH /organizations/{id} returns updated confirmation."""
        with (
            patch(
                "services.api.anveshak.api.routes.organizations.org_db.get_organization",
                new=AsyncMock(return_value={"id": "org-1", "name": "NIA"}),
            ),
            patch(
                "services.api.anveshak.api.routes.organizations.org_db.update_organization",
                new=AsyncMock(),
            ),
        ):
            from services.api.anveshak.api.routes.organizations import (
                UpdateOrgRequest,
                update_organization,
            )

            mock_conn = AsyncMock()
            user = {"sub": "sa-1", "role": "super-admin", "jti": "x"}
            req = UpdateOrgRequest(name="NIA Updated")
            result = await update_organization(
                org_id="org-1",
                req=req,
                db=mock_conn,
                _user=user,
            )

        assert result["updated"] is True


# ===================================================================
# 10. Migration file exists
# ===================================================================


class TestMigration:
    """Assert on migration *content*, never on a version filename.

    The org schema arrived as 007_organizations.py and has since been
    squashed into 001_initial_schema.py; path-based assertions broke.
    """

    def test_migration_creates_organizations_table(self):
        """Migrations must CREATE TABLE organizations."""
        assert "CREATE TABLE organizations" in migrations_sql()

    def test_migration_creates_org_sources_table(self):
        """Migrations must create the org_sources visibility table."""
        assert "CREATE TABLE org_sources" in migrations_sql()

    @pytest.mark.parametrize("table", ["users", "topics"])
    def test_migration_gives_table_an_org_id(self, table: str):
        """users and topics are root tables, so each carries its own org_id.

        Accepts either form: an inline column in the squashed CREATE TABLE,
        or an ADD COLUMN in a later incremental migration.
        """
        sql = migrations_sql()
        create_block = re.search(
            rf"CREATE TABLE {table} \((.*?)\n *\)", sql, re.DOTALL | re.IGNORECASE
        )
        inline = bool(create_block and "org_id" in create_block.group(1))
        added = bool(re.search(rf"{table} ADD COLUMN org_id", sql, re.IGNORECASE))
        assert inline or added, f"{table} has no org_id column in any migration"

    def test_migration_references_organizations_fk(self):
        """org_id columns must be FK-constrained, not free-text."""
        assert "REFERENCES organizations(id)" in migrations_sql()


# ===================================================================
# 10b. Seed data provides the default organization
# ===================================================================


class TestSeedDefaultOrg:
    """The default org used to be backfilled by migration 007.

    Post-squash the schema is created fresh with nothing to backfill, so
    the default org now comes from the demo seed instead. Assert there, or
    a seed that stops creating it fails silently at demo time.
    """

    @pytest.mark.parametrize("seed", ["seed_demo.sql", "seed_demo_full.sql"])
    def test_seed_creates_default_org(self, seed: str):
        content = (REPO_ROOT / "scripts" / seed).read_text()
        assert "INSERT INTO organizations" in content
        assert "org-anshul" in content


# ===================================================================
# 11. Frontend AuthContext includes org_id
# ===================================================================


class TestFrontendOrgId:
    def test_auth_context_has_org_id(self):
        """AuthContext.tsx JWTPayload must include org_id field."""
        content = (REPO_ROOT / "frontend" / "src" / "contexts" / "AuthContext.tsx").read_text()
        assert "org_id" in content
