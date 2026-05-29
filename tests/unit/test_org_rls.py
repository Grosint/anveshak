"""RED phase — Row-Level Security safety net tests (PR 4).

Tests for:
  1. Migration 008 exists with RLS policy SQL
  2. set_org_context() function exists in pool.py
  3. Migration enables RLS on correct tables
  4. Migration creates policies with current_setting pattern
  5. Migration creates anveshak_worker role with BYPASSRLS

pytest.mark.unit — no external dependencies (migration file content checks).
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

MIGRATION_PATH = Path("services/api/migrations/versions/008_rls_policies.py")


# ===================================================================
# 1. Migration file exists
# ===================================================================

class TestRLSMigrationExists:

    def test_migration_008_exists(self):
        """Migration 008_rls_policies.py must exist."""
        assert MIGRATION_PATH.exists(), "Migration 008_rls_policies.py not found"


# ===================================================================
# 2. RLS enabled on correct tables
# ===================================================================

class TestRLSEnabledOnTables:

    def test_rls_on_topics(self):
        content = MIGRATION_PATH.read_text().lower()
        assert "enable row level security" in content
        assert "topics" in content

    def test_rls_on_content_items(self):
        content = MIGRATION_PATH.read_text().lower()
        assert "content_items" in content

    def test_rls_on_users(self):
        content = MIGRATION_PATH.read_text().lower()
        assert "users" in content

    def test_rls_on_credibility_audit_log(self):
        content = MIGRATION_PATH.read_text().lower()
        assert "credibility_audit_log" in content


# ===================================================================
# 3. RLS policies use current_setting pattern
# ===================================================================

class TestRLSPolicies:

    def test_policies_use_current_setting(self):
        """Policies must use current_setting('app.current_org', true)."""
        content = MIGRATION_PATH.read_text().lower()
        assert "current_setting" in content
        assert "app.current_org" in content

    def test_policies_allow_empty_setting_for_superadmin(self):
        """Policies must allow access when setting is empty (super-admin bypass)."""
        content = MIGRATION_PATH.read_text()
        # Should have a condition like: OR current_setting(...) = ''
        assert "= ''" in content or "=''" in content


# ===================================================================
# 4. Worker role with BYPASSRLS
# ===================================================================

class TestWorkerRole:

    def test_creates_worker_role(self):
        """Migration must create anveshak_worker role."""
        content = MIGRATION_PATH.read_text().lower()
        assert "anveshak_worker" in content

    def test_worker_has_bypassrls(self):
        """Worker role must have BYPASSRLS privilege."""
        content = MIGRATION_PATH.read_text()
        assert "BYPASSRLS" in content


# ===================================================================
# 5. set_org_context() in pool.py
# ===================================================================

class TestSetOrgContext:

    @pytest.mark.asyncio
    async def test_set_org_context_exists(self):
        """set_org_context() function must exist in pool module."""
        from services.api.anveshak.api.db.pool import set_org_context

        assert callable(set_org_context)

    @pytest.mark.asyncio
    async def test_set_org_context_executes_set_local(self):
        """set_org_context() must execute SET LOCAL app.current_org."""
        from unittest.mock import AsyncMock
        from services.api.anveshak.api.db.pool import set_org_context

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        await set_org_context(mock_conn, "org-nia")

        mock_conn.execute.assert_awaited_once()
        call_args = mock_conn.execute.call_args[0][0]
        assert "set local" in call_args.lower() or "SET LOCAL" in call_args
        assert "app.current_org" in call_args

    @pytest.mark.asyncio
    async def test_set_org_context_with_none_sets_empty(self):
        """set_org_context(conn, None) sets empty string (super-admin bypass)."""
        from unittest.mock import AsyncMock
        from services.api.anveshak.api.db.pool import set_org_context

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        await set_org_context(mock_conn, None)

        call_args = mock_conn.execute.call_args[0][0]
        assert "''" in call_args
