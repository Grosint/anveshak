"""RED phase — code review fix tests.

Tests for:
  F1: logout must inject Redis and actually call revoke_token
  F2: auth.py must not import math
  F3: route files must not import get_current_user (only rbac.py uses it)
  W3: export endpoints must call audit_db.log_action
  W4: security middleware must not import settings inside dispatch()

pytest.mark.unit — no external dependencies.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROUTES_DIR = Path("services/api/anveshak/api/routes")


# ===================================================================
# F1: logout must use Redis dependency injection
# ===================================================================

class TestLogoutRedisInjection:
    """logout() must inject Redis via FastAPI Depends, not default None."""

    def test_logout_has_redis_dependency(self):
        """logout() signature must use Depends() for redis, not bare None."""
        source = (ROUTES_DIR / "auth.py").read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "logout":
                # Find the 'redis' parameter
                for arg in node.args.args:
                    if arg.arg == "redis":
                        # It must NOT have a bare None default — must use Depends()
                        # Check defaults: logout(user=Depends(...), redis=Depends(...))
                        break
                # Check that "redis=None" is NOT in the source
                func_source = ast.get_source_segment(source, node)
                assert "redis=None" not in func_source, (
                    "logout() must inject redis via Depends(), not default None"
                )
                return

        pytest.fail("logout() function not found in auth.py")


# ===================================================================
# F2: no unused math import in auth.py
# ===================================================================

class TestNoUnusedMathImport:
    """auth.py must not import math (unused)."""

    def test_no_math_import(self):
        source = (ROUTES_DIR / "auth.py").read_text()
        assert "import math" not in source, "auth.py has unused 'import math'"


# ===================================================================
# F3: no unused get_current_user imports in route files
# ===================================================================

class TestNoUnusedGetCurrentUserImports:
    """Route files that use require_role() must not also import get_current_user."""

    # auth.py is exempt — it uses get_current_user directly for logout/me
    MUST_NOT_IMPORT = [
        "content.py",
        "export.py",
        "intelligence.py",
        "reports.py",
        "signals.py",
        "sources.py",
        "system.py",
        "topics.py",
        "users.py",
        "vision.py",
    ]

    @pytest.mark.parametrize("filename", MUST_NOT_IMPORT)
    def test_no_get_current_user_import(self, filename):
        source = (ROUTES_DIR / filename).read_text()
        assert "get_current_user" not in source, (
            f"{filename} imports get_current_user but uses require_role() — remove unused import"
        )


# ===================================================================
# W3: export endpoints must have audit trail
# ===================================================================

class TestExportAuditTrail:
    """Export route file must import and call audit_db.log_action."""

    def test_export_imports_audit(self):
        source = (ROUTES_DIR / "export.py").read_text()
        assert "audit" in source.lower(), (
            "export.py must import audit_db for compliance logging"
        )

    def test_export_calls_log_action(self):
        source = (ROUTES_DIR / "export.py").read_text()
        assert "log_action" in source, (
            "export.py must call log_action() to audit data exports"
        )


# ===================================================================
# W4: security middleware must import settings at module level
# ===================================================================

class TestGetRedisReturnType:
    """_get_redis() must have a return type annotation."""

    def test_get_redis_has_return_annotation(self):
        source = (ROUTES_DIR / "auth.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_get_redis":
                assert node.returns is not None, (
                    "_get_redis() at line {} missing return type annotation"
                    .format(node.lineno)
                )
                return
        pytest.fail("_get_redis() not found in auth.py")


class TestSecurityMiddlewareImport:
    """Settings import must be at module level, not inside dispatch()."""

    def test_no_import_inside_dispatch(self):
        source = Path("services/api/anveshak/api/middleware/security.py").read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "dispatch":
                # Check for any import statements inside dispatch
                for child in ast.walk(node):
                    if isinstance(child, (ast.Import, ast.ImportFrom)):
                        # json/base64 imports in _extract_analyst_id are okay
                        # but 'from ..settings import settings' inside dispatch is not
                        if isinstance(child, ast.ImportFrom) and child.module and "settings" in child.module:
                            pytest.fail(
                                f"security.py:dispatch() has 'from ..settings import settings' "
                                f"at line {child.lineno} — move to module level"
                            )
