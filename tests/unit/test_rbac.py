"""RED phase — RBAC and token revocation tests.

Tests for:
  - require_role() dependency: enforces role-based access control
  - Token revocation: jti-based blocklisting via Redis
  - JWT payload: includes role and jti fields
  - Logout endpoint: revokes current token
  - JWT startup guard: rejects default secret
  - CORS hardening: explicit method list

pytest.mark.unit — no external dependencies.
"""
from __future__ import annotations

from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper: create a token with role + jti for testing
# ---------------------------------------------------------------------------

def _make_token(
    subject: str = "user-1",
    username: str = "analyst",
    role: str = "analyst",
) -> str:
    """Create a JWT with the expected new payload (role + jti)."""
    with patch("services.api.anveshak.api.auth.jwt.settings") as s:
        s.jwt_secret_key = "test-secret-for-rbac-tests"
        s.jwt_algorithm = "HS256"
        s.jwt_expire_minutes = 30
        from services.api.anveshak.api.auth.jwt import create_access_token

        return create_access_token(subject=subject, username=username, role=role)


# ===================================================================
# 1. JWT payload now includes role and jti
# ===================================================================

class TestJWTPayload:
    """JWT tokens must include role and jti (JWT ID) fields."""

    def test_token_contains_role(self):
        """Token payload must include the user's role."""
        with patch("services.api.anveshak.api.auth.jwt.settings") as s:
            s.jwt_secret_key = "test-secret-for-rbac-tests"
            s.jwt_algorithm = "HS256"
            s.jwt_expire_minutes = 30
            from services.api.anveshak.api.auth.jwt import (
                create_access_token,
                verify_token,
            )

            token = create_access_token(
                subject="user-1", username="admin_user", role="admin"
            )
            payload = verify_token(token)

        assert payload["role"] == "admin"

    def test_token_contains_jti(self):
        """Token payload must include a unique jti (JWT ID)."""
        with patch("services.api.anveshak.api.auth.jwt.settings") as s:
            s.jwt_secret_key = "test-secret-for-rbac-tests"
            s.jwt_algorithm = "HS256"
            s.jwt_expire_minutes = 30
            from services.api.anveshak.api.auth.jwt import (
                create_access_token,
                verify_token,
            )

            token = create_access_token(subject="user-1", role="analyst")
            payload = verify_token(token)

        assert "jti" in payload
        assert len(payload["jti"]) == 36  # UUID format

    def test_two_tokens_have_different_jti(self):
        """Each token must have a unique jti."""
        with patch("services.api.anveshak.api.auth.jwt.settings") as s:
            s.jwt_secret_key = "test-secret-for-rbac-tests"
            s.jwt_algorithm = "HS256"
            s.jwt_expire_minutes = 30
            from services.api.anveshak.api.auth.jwt import (
                create_access_token,
                verify_token,
            )

            t1 = create_access_token(subject="user-1", role="analyst")
            t2 = create_access_token(subject="user-1", role="analyst")
            p1 = verify_token(t1)
            p2 = verify_token(t2)

        assert p1["jti"] != p2["jti"]

    def test_role_defaults_to_analyst(self):
        """If role is not provided, it defaults to 'analyst'."""
        with patch("services.api.anveshak.api.auth.jwt.settings") as s:
            s.jwt_secret_key = "test-secret-for-rbac-tests"
            s.jwt_algorithm = "HS256"
            s.jwt_expire_minutes = 30
            from services.api.anveshak.api.auth.jwt import (
                create_access_token,
                verify_token,
            )

            token = create_access_token(subject="user-1")
            payload = verify_token(token)

        assert payload["role"] == "analyst"


# ===================================================================
# 2. require_role() dependency
# ===================================================================

class TestRequireRole:
    """require_role() must enforce role-based access control."""

    @pytest.mark.asyncio
    async def test_admin_passes_admin_check(self):
        """Admin user passes require_role('admin')."""
        from services.api.anveshak.api.auth.rbac import require_role

        dep = require_role("admin")
        user = {"sub": "u1", "username": "a", "role": "admin", "jti": "x"}
        result = await dep(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_analyst_fails_admin_check(self):
        """Analyst user is rejected by require_role('admin')."""
        from fastapi import HTTPException
        from services.api.anveshak.api.auth.rbac import require_role

        dep = require_role("admin")
        user = {"sub": "u1", "username": "a", "role": "analyst", "jti": "x"}
        with pytest.raises(HTTPException) as exc_info:
            await dep(user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_analyst_passes_analyst_or_admin_check(self):
        """Analyst passes require_role('analyst', 'admin')."""
        from services.api.anveshak.api.auth.rbac import require_role

        dep = require_role("analyst", "admin")
        user = {"sub": "u1", "username": "a", "role": "analyst", "jti": "x"}
        result = await dep(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_admin_passes_analyst_or_admin_check(self):
        """Admin passes require_role('analyst', 'admin')."""
        from services.api.anveshak.api.auth.rbac import require_role

        dep = require_role("analyst", "admin")
        user = {"sub": "u1", "username": "a", "role": "admin", "jti": "x"}
        result = await dep(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_viewer_fails_analyst_or_admin_check(self):
        """Viewer is rejected by require_role('analyst', 'admin')."""
        from fastapi import HTTPException
        from services.api.anveshak.api.auth.rbac import require_role

        dep = require_role("analyst", "admin")
        user = {"sub": "u1", "username": "v", "role": "viewer", "jti": "x"}
        with pytest.raises(HTTPException) as exc_info:
            await dep(user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_passes_viewer_check(self):
        """Viewer passes require_role('viewer', 'analyst', 'admin') — i.e. all roles."""
        from services.api.anveshak.api.auth.rbac import require_role

        dep = require_role("viewer", "analyst", "admin")
        user = {"sub": "u1", "username": "v", "role": "viewer", "jti": "x"}
        result = await dep(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_error_message_includes_role(self):
        """403 detail must say which roles were required."""
        from fastapi import HTTPException
        from services.api.anveshak.api.auth.rbac import require_role

        dep = require_role("admin")
        user = {"sub": "u1", "username": "a", "role": "analyst", "jti": "x"}
        with pytest.raises(HTTPException) as exc_info:
            await dep(user)
        assert "admin" in exc_info.value.detail.lower()


# ===================================================================
# 3. Token revocation
# ===================================================================

class TestTokenRevocation:
    """Revoked tokens must be rejected by verify_token."""

    @pytest.mark.asyncio
    async def test_revoke_token_stores_in_redis(self):
        """revoke_token() must SET a Redis key for the jti."""
        from services.api.anveshak.api.auth.jwt import revoke_token

        mock_redis = AsyncMock()
        jti = "test-jti-001"
        ttl_seconds = 3600

        await revoke_token(mock_redis, jti, ttl_seconds)

        mock_redis.setex.assert_awaited_once_with(
            f"blocklist:{jti}", ttl_seconds, "1"
        )

    @pytest.mark.asyncio
    async def test_is_token_revoked_true(self):
        """is_token_revoked() returns True when jti is in Redis blocklist."""
        from services.api.anveshak.api.auth.jwt import is_token_revoked

        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1

        assert await is_token_revoked(mock_redis, "revoked-jti") is True
        mock_redis.exists.assert_awaited_once_with("blocklist:revoked-jti")

    @pytest.mark.asyncio
    async def test_is_token_revoked_false(self):
        """is_token_revoked() returns False when jti is NOT in Redis blocklist."""
        from services.api.anveshak.api.auth.jwt import is_token_revoked

        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0

        assert await is_token_revoked(mock_redis, "valid-jti") is False


# ===================================================================
# 4. Login includes role in token
# ===================================================================

class TestLoginWithRole:
    """Login endpoint must fetch role and include it in JWT."""

    @pytest.mark.asyncio
    async def test_login_returns_token_with_role(self, mock_conn):
        """Login response token must contain the user's role when decoded."""
        from services.api.anveshak.api.auth.jwt import pwd_context

        hashed = pwd_context.hash("password")

        with patch(
            "services.api.anveshak.api.routes.auth.auth_db.get_user_by_username",
            new=AsyncMock(return_value={
                "id": "user-1",
                "password_hash": hashed,
                "role": "admin",
            }),
        ), patch("services.api.anveshak.api.auth.jwt.settings") as s:
            s.jwt_secret_key = "test-secret-for-rbac-tests"
            s.jwt_algorithm = "HS256"
            s.jwt_expire_minutes = 30
            from services.api.anveshak.api.auth.jwt import verify_token
            from services.api.anveshak.api.routes.auth import login, LoginRequest

            result = await login(LoginRequest(username="admin", password="password"), db=mock_conn)
            payload = verify_token(result["access_token"])

        assert payload["role"] == "admin"


# ===================================================================
# 5. Logout endpoint
# ===================================================================

class TestLogout:
    """POST /auth/logout must revoke the current token."""

    @pytest.mark.asyncio
    async def test_logout_revokes_token(self):
        """Logout must call revoke_token with the jti from the current token."""
        with patch("services.api.anveshak.api.auth.jwt.settings") as s:
            s.jwt_secret_key = "test-secret-for-rbac-tests"
            s.jwt_algorithm = "HS256"
            s.jwt_expire_minutes = 30
            from services.api.anveshak.api.auth.jwt import (
                create_access_token,
                verify_token,
            )
            from services.api.anveshak.api.routes.auth import logout

            token = create_access_token(subject="user-1", role="analyst")
            payload = verify_token(token)

            mock_redis = AsyncMock()
            mock_redis.setex = AsyncMock()

            result = await logout(user=payload, redis=mock_redis)

        assert result["status"] == "logged_out"
        mock_redis.setex.assert_awaited_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == f"blocklist:{payload['jti']}"


# ===================================================================
# 6. GET /auth/me
# ===================================================================

class TestAuthMe:
    """GET /auth/me must return current user info."""

    @pytest.mark.asyncio
    async def test_me_returns_user_info(self):
        """GET /auth/me returns sub, username, role."""
        from services.api.anveshak.api.routes.auth import me

        user = {"sub": "u1", "username": "analyst1", "role": "analyst", "jti": "x"}
        result = await me(user=user)
        assert result["user_id"] == "u1"
        assert result["username"] == "analyst1"
        assert result["role"] == "analyst"


# ===================================================================
# 7. Auth DB fetches role
# ===================================================================

class TestAuthDBRole:
    """get_user_by_username must return role field for JWT embedding."""

    @pytest.mark.asyncio
    async def test_get_user_by_username_includes_role(self, mock_conn):
        """SQL query must select role alongside id and password_hash."""
        from services.api.anveshak.api.db.auth import SQL_GET_USER_BY_USERNAME

        assert "role" in SQL_GET_USER_BY_USERNAME.lower()


# ===================================================================
# 8. CORS hardening
# ===================================================================

class TestCORSHardening:
    """CORS must not use allow_methods=["*"]."""

    def test_cors_explicit_methods(self):
        """CORS middleware must use explicit method list, not wildcard."""
        import ast
        import inspect
        from pathlib import Path

        main_path = Path("services/api/anveshak/api/main.py")
        source = main_path.read_text()

        # Check that allow_methods does NOT contain "*"
        assert 'allow_methods=["*"]' not in source, \
            "CORS allow_methods must not be wildcard — use explicit method list"

    def test_cors_origins_from_settings(self):
        """CORS allow_origins should reference settings, not be hardcoded."""
        from pathlib import Path

        main_path = Path("services/api/anveshak/api/main.py")
        source = main_path.read_text()

        # Should reference settings for origins
        assert "settings" in source.split("allow_origins")[1].split("\n")[0] or \
               "API_ALLOWED_ORIGINS" in source or \
               "allowed_origins" in source, \
            "CORS origins should be configurable via settings"


# ===================================================================
# 9. JWT startup guard
# ===================================================================

class TestJWTStartupGuard:
    """API must refuse to start if JWT secret is the default."""

    def test_validate_jwt_secret_rejects_default(self):
        """validate_jwt_secret() must raise when secret is 'change-me-in-production'."""
        from services.api.anveshak.api.auth.jwt import validate_jwt_secret

        with pytest.raises(ValueError, match="change-me-in-production"):
            validate_jwt_secret("change-me-in-production")

    def test_validate_jwt_secret_accepts_real_secret(self):
        """validate_jwt_secret() must not raise for a non-default secret."""
        from services.api.anveshak.api.auth.jwt import validate_jwt_secret

        # Should not raise
        validate_jwt_secret("my-real-production-secret-key-2026")
