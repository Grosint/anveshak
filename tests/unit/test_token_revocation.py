"""Unit tests for token revocation enforcement.

Critical fix: is_token_revoked() exists but was never called in the auth
pipeline. After logout, revoked tokens must be rejected with 401.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestTokenRevocationEnforcement:
    """get_current_user must reject revoked tokens."""

    @pytest.mark.asyncio
    async def test_revoked_token_raises_401(self):
        """After revoke_token(), subsequent requests with that jti get 401."""
        from fastapi import HTTPException

        jti = str(uuid.uuid4())
        fake_payload = {
            "sub": "user-1",
            "username": "analyst",
            "role": "analyst",
            "org_id": "org-1",
            "jti": jti,
        }

        # Mock verify_token to return valid payload
        # Mock Redis to say token IS revoked
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)  # revoked

        with patch("anveshak.api.auth.jwt.verify_token", return_value=fake_payload):
            from anveshak.api.auth.jwt import get_current_user

            mock_creds = MagicMock()
            mock_creds.credentials = "fake.jwt.token"

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=mock_creds, redis=mock_redis)

            assert exc_info.value.status_code == 401
            assert "revoked" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_non_revoked_token_passes(self):
        """Valid, non-revoked token should return user payload normally."""
        jti = str(uuid.uuid4())
        fake_payload = {
            "sub": "user-1",
            "username": "analyst",
            "role": "analyst",
            "org_id": "org-1",
            "jti": jti,
        }

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)  # not revoked

        with patch("anveshak.api.auth.jwt.verify_token", return_value=fake_payload):
            from anveshak.api.auth.jwt import get_current_user

            mock_creds = MagicMock()
            mock_creds.credentials = "fake.jwt.token"

            result = await get_current_user(credentials=mock_creds, redis=mock_redis)
            assert result["sub"] == "user-1"
            assert result["jti"] == jti

    @pytest.mark.asyncio
    async def test_revocation_check_uses_blocklist_key(self):
        """is_token_revoked must check blocklist:{jti} key in Redis."""
        from anveshak.api.auth.jwt import is_token_revoked

        jti = "test-jti-123"
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)

        result = await is_token_revoked(mock_redis, jti)
        assert result is True
        mock_redis.exists.assert_called_once_with("blocklist:test-jti-123")

    @pytest.mark.asyncio
    async def test_redis_unavailable_allows_request(self):
        """If Redis is down, fail open — don't block all requests."""
        jti = str(uuid.uuid4())
        fake_payload = {
            "sub": "user-1",
            "username": "analyst",
            "role": "analyst",
            "org_id": "org-1",
            "jti": jti,
        }

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(side_effect=Exception("Redis connection lost"))

        with patch("anveshak.api.auth.jwt.verify_token", return_value=fake_payload):
            from anveshak.api.auth.jwt import get_current_user

            mock_creds = MagicMock()
            mock_creds.credentials = "fake.jwt.token"

            # Should NOT raise — fail open on Redis errors
            result = await get_current_user(credentials=mock_creds, redis=mock_redis)
            assert result["sub"] == "user-1"
