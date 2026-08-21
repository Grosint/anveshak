"""Unit tests for template-topic linking API endpoints.

Verifies:
  POST   /api/v1/topics/{topic_id}/templates/{template_id}  — link
  DELETE /api/v1/topics/{topic_id}/templates/{template_id}  — unlink
  GET    /api/v1/topics/{topic_id}/templates                — list

pytest.mark.unit -- no external dependencies.
"""

from __future__ import annotations

import pytest

_DB_MOD = "anveshak.api.db.identifiers"


@pytest.mark.unit
class TestTemplateLinkingSQLExists:
    """DB layer must have SQL constants for template linking."""

    def test_sql_link_template(self):
        from anveshak.api.db.identifiers import SQL_LINK_TEMPLATE

        sql = SQL_LINK_TEMPLATE.lower()
        assert "topic_templates" in sql
        assert "insert" in sql
        assert "on conflict" in sql

    def test_sql_unlink_template(self):
        from anveshak.api.db.identifiers import SQL_UNLINK_TEMPLATE

        sql = SQL_UNLINK_TEMPLATE.lower()
        assert "topic_templates" in sql
        assert "delete" in sql

    def test_sql_list_topic_templates(self):
        from anveshak.api.db.identifiers import SQL_LIST_TOPIC_TEMPLATES

        sql = SQL_LIST_TOPIC_TEMPLATES.lower()
        assert "scam_templates" in sql
        assert "topic_templates" in sql


@pytest.mark.unit
class TestTemplateLinkingDBFunctions:
    """DB layer must have async functions for template CRUD."""

    def test_link_template_function(self):
        from anveshak.api.db import identifiers as db

        assert hasattr(db, "link_template"), "link_template function missing"
        assert callable(db.link_template)

    def test_unlink_template_function(self):
        from anveshak.api.db import identifiers as db

        assert hasattr(db, "unlink_template"), "unlink_template function missing"
        assert callable(db.unlink_template)

    def test_list_topic_templates_function(self):
        from anveshak.api.db import identifiers as db

        assert hasattr(db, "list_topic_templates"), "list_topic_templates function missing"
        assert callable(db.list_topic_templates)


@pytest.mark.unit
class TestTemplateLinkingRouteExists:
    """Router must have template linking endpoints."""

    def test_link_route(self):
        from anveshak.api.routes.identifiers import router

        paths = [r.path for r in router.routes]
        # Check for a route that links templates to topics
        assert any("templates" in p and "{template_id}" in p for p in paths), (
            f"No template linking route found. Routes: {paths}"
        )

    def test_list_route(self):
        from anveshak.api.routes.identifiers import router

        paths = [r.path for r in router.routes]
        assert any("templates" in p and "{template_id}" not in p for p in paths), (
            f"No template listing route found. Routes: {paths}"
        )
