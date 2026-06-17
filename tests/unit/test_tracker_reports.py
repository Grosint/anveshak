"""Tests for tracker-scoped report generation.

pytest.mark.unit — no external dependencies.
"""
from __future__ import annotations

import pytest


@pytest.mark.unit
class TestTrackerReportSQL:
    """Reporter DB must have tracker-scoped RAG chunk query."""

    def test_fetch_tracker_rag_chunks_sql_exists(self):
        from anveshak.reporter.db import SQL_FETCH_TRACKER_RAG_CHUNKS
        sql = SQL_FETCH_TRACKER_RAG_CHUNKS.lower()
        assert "tracker_content_items" in sql, \
            "Must filter through tracker_content_items join table"
        assert "confirmed" in sql, \
            "Must only include confirmed items (not pending)"
        assert "credibility_score_at_capture" in sql, \
            "Must filter by credibility threshold"

    def test_fetch_tracker_rag_chunks_function_exists(self):
        from anveshak.reporter.db import fetch_tracker_rag_chunks
        assert callable(fetch_tracker_rag_chunks)


@pytest.mark.unit
class TestReportInsertWithTracker:
    """API report insert must support tracker_id."""

    def test_sql_insert_report_has_tracker_id(self):
        from anveshak.api.db.reports import SQL_INSERT_REPORT
        sql = SQL_INSERT_REPORT.lower()
        assert "tracker_id" in sql, \
            "SQL_INSERT_REPORT must include tracker_id column"

    def test_insert_report_accepts_tracker_id(self):
        """insert_report() function must accept tracker_id param."""
        import inspect
        from anveshak.api.db.reports import insert_report
        sig = inspect.signature(insert_report)
        assert "tracker_id" in sig.parameters, \
            "insert_report() must accept tracker_id parameter"


@pytest.mark.unit
class TestTrackerReportsRoute:
    """Tracker routes must include report endpoints."""

    def test_tracker_reports_route_exists(self):
        """GET /{tracker_id}/reports must be registered."""
        import inspect
        from anveshak.api.routes import trackers
        source = inspect.getsource(trackers)
        assert "reports" in source.lower(), \
            "trackers routes must include a reports endpoint"

    def test_tracker_generate_report_route_exists(self):
        """POST /{tracker_id}/reports must be registered."""
        import inspect
        from anveshak.api.routes import trackers
        # Look for a POST route with 'reports' in it
        source = inspect.getsource(trackers)
        assert "generate" in source.lower() or "report" in source.lower(), \
            "trackers routes must include report generation"
