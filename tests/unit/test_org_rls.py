"""RED phase — Row-Level Security safety net tests (PR 4).

Tests for:
  1. The migration set carries RLS policy SQL
  2. set_org_context() function exists in pool.py
  3. Migrations enable RLS on correct tables
  4. Migrations create policies with current_setting pattern
  5. Migrations create anveshak_worker role with BYPASSRLS

These assert on migration *content*, never on a version filename: the RLS
migration was originally 008_rls_policies.py and has since been squashed
into 001_initial_schema.py.

pytest.mark.unit — no external dependencies (migration file content checks).
"""

from __future__ import annotations

import re

import pytest

from tests.helpers.migrations import migrations_sql

pytestmark = pytest.mark.unit


# ===================================================================
# 1. RLS SQL is present in the migration set
# ===================================================================


class TestRLSMigrationExists:
    def test_rls_migration_present(self):
        """Some live migration must enable row-level security."""
        assert "ENABLE ROW LEVEL SECURITY" in migrations_sql().upper()


# ===================================================================
# 2. RLS enabled on correct tables
# ===================================================================


# Root tables carrying org_id. See AGENTS.md "org_id placement, root tables only".
RLS_TABLES = ["topics", "content_items", "users", "credibility_audit_log"]


class TestRLSEnabledOnTables:
    @pytest.mark.parametrize("table", RLS_TABLES)
    def test_rls_enabled(self, table: str):
        """Each org-scoped root table must have RLS turned on."""
        content = migrations_sql().upper()
        assert f"ALTER TABLE {table.upper()} ENABLE ROW LEVEL SECURITY" in content

    @pytest.mark.parametrize("table", RLS_TABLES)
    def test_policy_created(self, table: str):
        """Enabling RLS without a policy denies every row, so require both."""
        pattern = rf"CREATE\s+POLICY\s+\w+\s+ON\s+{table}\b"
        assert re.search(pattern, migrations_sql(), re.IGNORECASE), (
            f"no RLS policy found for {table}"
        )


# ===================================================================
# 3. RLS policies use current_setting pattern
# ===================================================================


class TestRLSPolicies:
    def test_policies_use_current_setting(self):
        """Policies must use current_setting('app.current_org', true)."""
        content = migrations_sql().lower()
        assert "current_setting" in content
        assert "app.current_org" in content

    def test_policies_allow_empty_setting_for_superadmin(self):
        """Policies must allow access when setting is empty (super-admin bypass)."""
        content = migrations_sql()
        # Should have a condition like: OR current_setting(...) = ''
        assert "= ''" in content or "=''" in content


# ===================================================================
# 4. Worker role with BYPASSRLS
# ===================================================================


class TestWorkerRole:
    def test_creates_worker_role(self):
        """Migrations must create the anveshak_worker role."""
        content = migrations_sql().lower()
        assert "anveshak_worker" in content

    def test_worker_has_bypassrls(self):
        """Worker role must have BYPASSRLS privilege."""
        content = migrations_sql()
        assert "BYPASSRLS" in content


# ===================================================================
# 5. set_org_context() removed — dead code cleanup
# ===================================================================


class TestSetOrgContext:
    def test_set_org_context_removed(self):
        """set_org_context() was dead code — removed in security review.

        Application-level verify_topic_access() is the primary isolation
        mechanism. The RLS policies in the migration set still exist as a
        secondary safety net, but SET LOCAL is not called from application
        code.
        """
        import anveshak.api.db.pool as pool_mod

        assert not hasattr(pool_mod, "set_org_context"), (
            "set_org_context was dead code — should have been removed"
        )
