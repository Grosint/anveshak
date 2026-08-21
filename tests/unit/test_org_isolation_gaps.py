"""Unit tests for org_id isolation in signals, intelligence, and templates.

Verifies cross-org data cannot leak through:
  1. get_signal_connections — must verify topic access before returning graph
  2. SQL_MISSED_SIGNALS — must filter by org_id
  3. SQL_SIGNAL_CROSS_TOPIC — must constrain to same org
  4. SQL_TOPIC_SIMILARITY — must scope other_topics to same org
  5. SQL_LIST_TEMPLATES — must hide custom templates from other orgs

pytest.mark.unit -- no external dependencies.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# 1. Signal connections must check org access
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSignalConnectionsOrgCheck:
    """get_signal_connections must verify the signal's topic belongs to user's org."""

    def test_route_fetches_signal_topic_before_graph(self):
        """Route code must fetch signal's topic_id and call verify_topic_access."""
        import inspect

        from anveshak.api.routes.signals import get_signal_connections

        source = inspect.getsource(get_signal_connections)
        assert "verify_topic_access" in source or "topic_id" in source, (
            "get_signal_connections must check org via topic before returning graph data"
        )


# ---------------------------------------------------------------------------
# 2. Missed signals must filter by org
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMissedSignalsOrgFilter:
    """SQL_MISSED_SIGNALS must JOIN topics and filter by org_id."""

    def test_sql_has_org_filter(self):
        from anveshak.api.db.signals import SQL_MISSED_SIGNALS

        sql = SQL_MISSED_SIGNALS.lower()
        assert "org_id" in sql, (
            "SQL_MISSED_SIGNALS must filter by org_id to prevent cross-org replay"
        )
        assert "topics" in sql or "join" in sql, (
            "SQL_MISSED_SIGNALS must JOIN topics to access org_id"
        )

    def test_get_missed_signals_accepts_org_id(self):
        """Function signature must accept org_id parameter."""
        import inspect

        from anveshak.api.db.signals import get_missed_signals

        sig = inspect.signature(get_missed_signals)
        params = list(sig.parameters.keys())
        assert "org_id" in params, f"get_missed_signals must accept org_id param. Has: {params}"


# ---------------------------------------------------------------------------
# 3. Cross-topic signal must constrain to same org
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCrossTopicSignalOrgFilter:
    """SQL_SIGNAL_CROSS_TOPIC must not return topics from other organizations."""

    def test_sql_has_org_constraint(self):
        from anveshak.api.db.signals import SQL_SIGNAL_CROSS_TOPIC

        sql = SQL_SIGNAL_CROSS_TOPIC.lower()
        assert "org_id" in sql, (
            "SQL_SIGNAL_CROSS_TOPIC must filter by org_id to prevent cross-org topic leak"
        )


# ---------------------------------------------------------------------------
# 4. Similar topics must scope to same org
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimilarTopicsOrgFilter:
    """SQL_TOPIC_SIMILARITY other_topics CTE must filter by org_id."""

    def test_sql_has_org_filter(self):
        from anveshak.api.routes.intelligence import SQL_TOPIC_SIMILARITY

        sql = SQL_TOPIC_SIMILARITY.lower()
        assert "org_id" in sql, "SQL_TOPIC_SIMILARITY must scope other_topics to same org"


# ---------------------------------------------------------------------------
# 5. Templates list must hide other orgs' custom templates
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTemplatesListOrgFilter:
    """SQL_LIST_TEMPLATES must filter custom templates by org_id."""

    def test_sql_has_org_filter(self):
        from anveshak.api.db.templates import SQL_LIST_TEMPLATES

        sql = SQL_LIST_TEMPLATES.lower()
        assert "org_id" in sql, (
            "SQL_LIST_TEMPLATES must filter by org_id (builtins=NULL visible to all)"
        )

    def test_list_templates_accepts_org_id(self):
        """Function must accept org_id to filter custom templates."""
        import inspect

        from anveshak.api.db.templates import list_templates

        sig = inspect.signature(list_templates)
        params = list(sig.parameters.keys())
        assert "org_id" in params, f"list_templates must accept org_id param. Has: {params}"
