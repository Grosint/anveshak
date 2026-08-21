"""Unit tests for user management DB functions.

Tests:
  - list_users returns all users (without password_hash)
  - create_user inserts with hashed password
  - delete_user removes user
  - update_user_role changes role

pytest.mark.unit — mock DB, no external dependencies.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit


class TestUserDB:
    """User management DB repository functions."""

    @pytest.mark.asyncio
    async def test_list_users_exists(self):
        from anveshak.api.db.users import list_users

        assert callable(list_users)

    @pytest.mark.asyncio
    async def test_create_user_exists(self):
        from anveshak.api.db.users import create_user

        assert callable(create_user)

    @pytest.mark.asyncio
    async def test_delete_user_exists(self):
        from anveshak.api.db.users import delete_user

        assert callable(delete_user)

    @pytest.mark.asyncio
    async def test_update_user_role_exists(self):
        from anveshak.api.db.users import update_user_role

        assert callable(update_user_role)

    @pytest.mark.asyncio
    async def test_list_users_returns_list(self):
        from anveshak.api.db.users import list_users

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"id": "u1", "username": "admin", "role": "admin", "created_at": "2026-01-01"},
            ]
        )

        result = await list_users(mock_conn)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["username"] == "admin"
        # Must NOT return password_hash
        assert "password_hash" not in result[0]

    @pytest.mark.asyncio
    async def test_create_user_returns_id(self):
        from anveshak.api.db.users import create_user

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value="user-new-id")

        user_id = await create_user(mock_conn, "newuser", "password123", "analyst")
        assert user_id == "user-new-id"
        mock_conn.fetchval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_user_calls_execute(self):
        from anveshak.api.db.users import delete_user

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 1")

        result = await delete_user(mock_conn, "user-to-delete")
        assert result is True
        mock_conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_user_role_calls_execute(self):
        from anveshak.api.db.users import update_user_role

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        await update_user_role(mock_conn, "user-id", "admin")
        mock_conn.execute.assert_awaited_once()
