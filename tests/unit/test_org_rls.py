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
# 5. set_org_context() removed — dead code cleanup
# ===================================================================

class TestSetOrgContext:

    def test_set_org_context_removed(self):
        """set_org_context() was dead code — removed in security review.

        Application-level verify_topic_access() is the primary isolation
        mechanism. RLS policies in migration 008 still exist as a secondary
        safety net, but SET LOCAL is not called from application code.
        """
        import anveshak.api.db.pool as pool_mod
        assert not hasattr(pool_mod, "set_org_context"), (
            "set_org_context was dead code — should have been removed"
        )
