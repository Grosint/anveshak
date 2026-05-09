"""Tests for auth routes and JWT functions.

Validates login flow, password verification, token creation, and token verification.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---- Test 1: Successful login returns access token ----

@pytest.mark.unit
async def test_login_success(mock_conn: AsyncMock) -> None:
    """Valid credentials should return an access_token with token_type=bearer."""
    from services.api.anveshak.api.auth.jwt import pwd_context

    hashed = pwd_context.hash("correct-password")
    mock_conn.fetchrow = AsyncMock(
        return_value={"id": "user-001", "password_hash": hashed}
    )

    with patch(
        "services.api.anveshak.api.routes.auth.auth_db.get_user_by_username",
        new=AsyncMock(return_value={"id": "user-001", "password_hash": hashed}),
    ):
        from services.api.anveshak.api.routes.auth import login, LoginRequest

        req = LoginRequest(username="analyst", password="correct-password")
        # Inject mock DB via dependency override simulation
        result = await login(req, db=mock_conn)

    assert "access_token" in result
    assert result["token_type"] == "bearer"
    assert len(result["access_token"]) > 0


# ---- Test 2: Wrong password raises 401 ----

@pytest.mark.unit
async def test_login_wrong_password(mock_conn: AsyncMock) -> None:
    """Invalid password should raise HTTPException 401."""
    from fastapi import HTTPException
    from services.api.anveshak.api.auth.jwt import pwd_context

    hashed = pwd_context.hash("real-password")

    with patch(
        "services.api.anveshak.api.routes.auth.auth_db.get_user_by_username",
        new=AsyncMock(return_value={"id": "user-001", "password_hash": hashed}),
    ):
        from services.api.anveshak.api.routes.auth import login, LoginRequest

        req = LoginRequest(username="analyst", password="wrong-password")
        with pytest.raises(HTTPException) as exc_info:
            await login(req, db=mock_conn)

    assert exc_info.value.status_code == 401
    assert "Invalid credentials" in exc_info.value.detail


# ---- Test 3: User not found raises 401 ----

@pytest.mark.unit
async def test_login_user_not_found(mock_conn: AsyncMock) -> None:
    """Non-existent username should raise HTTPException 401."""
    from fastapi import HTTPException

    with patch(
        "services.api.anveshak.api.routes.auth.auth_db.get_user_by_username",
        new=AsyncMock(return_value=None),
    ):
        from services.api.anveshak.api.routes.auth import login, LoginRequest

        req = LoginRequest(username="ghost", password="anything")
        with pytest.raises(HTTPException) as exc_info:
            await login(req, db=mock_conn)

    assert exc_info.value.status_code == 401


# ---- Test 4: create_access_token produces a valid JWT ----

@pytest.mark.unit
def test_create_access_token_structure() -> None:
    """Token should have 3 dot-separated parts (header.payload.signature)."""
    with patch("services.api.anveshak.api.auth.jwt.settings") as mock_settings:
        mock_settings.jwt_secret_key = "test-secret-key-for-unit-tests"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_expire_minutes = 30

        from services.api.anveshak.api.auth.jwt import create_access_token

        token = create_access_token(subject="user-42", username="analyst")

    parts = token.split(".")
    assert len(parts) == 3, "JWT must have header.payload.signature"


# ---- Test 5: verify_token round-trips with create_access_token ----

@pytest.mark.unit
def test_verify_token_roundtrip() -> None:
    """A token created by create_access_token should be verifiable by verify_token."""
    with patch("services.api.anveshak.api.auth.jwt.settings") as mock_settings:
        mock_settings.jwt_secret_key = "test-secret-key-for-unit-tests"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_expire_minutes = 30

        from services.api.anveshak.api.auth.jwt import create_access_token, verify_token

        token = create_access_token(subject="user-99", username="admin")
        payload = verify_token(token)

    assert payload["sub"] == "user-99"
    assert payload["username"] == "admin"


# ---- Test 6: verify_token rejects tampered token ----

@pytest.mark.unit
def test_verify_token_rejects_tampered() -> None:
    """A tampered token should raise HTTPException 401."""
    from fastapi import HTTPException

    with patch("services.api.anveshak.api.auth.jwt.settings") as mock_settings:
        mock_settings.jwt_secret_key = "test-secret-key-for-unit-tests"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_expire_minutes = 30

        from services.api.anveshak.api.auth.jwt import create_access_token, verify_token

        token = create_access_token(subject="user-1")
        # Tamper with the signature
        tampered = token[:-5] + "XXXXX"

        with pytest.raises(HTTPException) as exc_info:
            verify_token(tampered)

    assert exc_info.value.status_code == 401


# ---- Test 7: verify_token rejects expired token ----

@pytest.mark.unit
def test_verify_token_rejects_expired() -> None:
    """A token with negative expiry should be rejected."""
    from fastapi import HTTPException

    with patch("services.api.anveshak.api.auth.jwt.settings") as mock_settings:
        mock_settings.jwt_secret_key = "test-secret-key-for-unit-tests"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_expire_minutes = 30

        from services.api.anveshak.api.auth.jwt import create_access_token, verify_token

        # Create an already-expired token
        token = create_access_token(
            subject="user-expired",
            expires_delta=timedelta(seconds=-10),
        )

        with pytest.raises(HTTPException) as exc_info:
            verify_token(token)

    assert exc_info.value.status_code == 401
    assert "Invalid or expired token" in exc_info.value.detail


# ---- Test 8: pwd_context hash and verify round-trip ----

@pytest.mark.unit
def test_pwd_context_roundtrip() -> None:
    """Bcrypt hash+verify should round-trip correctly."""
    from services.api.anveshak.api.auth.jwt import pwd_context

    password = "s3cur3-p@ssw0rd!"
    hashed = pwd_context.hash(password)

    assert hashed != password  # not stored in plaintext
    assert pwd_context.verify(password, hashed) is True
    assert pwd_context.verify("wrong-password", hashed) is False
