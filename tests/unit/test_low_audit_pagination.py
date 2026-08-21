"""Unit tests for audit trail pagination — LOW-24.

Audit trail must support offset-based pagination for large datasets.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestAuditTrailPagination:
    def test_get_audit_trail_accepts_offset(self):
        """get_audit_trail() must accept an offset parameter."""
        import inspect

        from anveshak.api.db.audit import get_audit_trail

        sig = inspect.signature(get_audit_trail)
        assert "offset" in sig.parameters, (
            "get_audit_trail must accept offset parameter for pagination"
        )

    def test_audit_trail_route_accepts_offset(self):
        """GET /system/audit-trail must accept offset query param."""
        import inspect

        from anveshak.api.routes.system import get_audit_trail as route_fn

        source = inspect.getsource(route_fn)
        assert "offset" in source, "Audit trail route must accept offset query parameter"

    def test_sql_queries_support_offset(self):
        """SQL queries must include OFFSET clause."""
        from anveshak.api.db.audit import SQL_GET_AUDIT_TRAIL_ALL

        sql = SQL_GET_AUDIT_TRAIL_ALL.lower()
        assert "offset" in sql, "SQL_GET_AUDIT_TRAIL_ALL must support OFFSET for pagination"
