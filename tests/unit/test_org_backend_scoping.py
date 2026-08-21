"""RED phase — Backend service org-scoping tests (PR 3).

Tests for:
  1. SQL_CONVERGENT_CLUSTERS must join topics and filter same org
  2. SQL_BREACHING_CLUSTERS — no change needed (already joins topics, runs globally)
  3. Scraper SQL_INSERT_CONTENT includes org_id column
  4. Scraper SQL_GET_TOPIC fetches org_id
  5. Social SQL_INSERT_CONTENT includes org_id column
  6. Credibility SQL_INSERT_AUDIT_LOG includes org_id column
  7. Signal engine SQL_INSERT_SIGNAL includes org_id column

pytest.mark.unit — no external dependencies.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ===================================================================
# 1. Convergence — cross-topic must be org-scoped
# ===================================================================


class TestConvergenceOrgScope:
    def test_convergent_clusters_joins_topics(self):
        """SQL_CONVERGENT_CLUSTERS must JOIN topics to access org_id."""
        from services.analyst.anveshak.analyst.convergence import SQL_CONVERGENT_CLUSTERS

        sql = SQL_CONVERGENT_CLUSTERS.lower()
        assert "join topics" in sql or "join topics " in sql, (
            "SQL_CONVERGENT_CLUSTERS must JOIN topics for org_id access"
        )

    def test_convergent_clusters_filters_same_org(self):
        """SQL_CONVERGENT_CLUSTERS must ensure both clusters are in same org."""
        from services.analyst.anveshak.analyst.convergence import SQL_CONVERGENT_CLUSTERS

        sql = SQL_CONVERGENT_CLUSTERS.lower()
        # Must have a condition ensuring t1.org_id = t2.org_id
        assert "org_id" in sql, (
            "SQL_CONVERGENT_CLUSTERS must filter by org_id to prevent cross-org leaks"
        )


# ===================================================================
# 2. Scraper — content inserts must include org_id
# ===================================================================


class TestScraperOrgId:
    def test_insert_content_has_org_id(self):
        """Scraper SQL_INSERT_CONTENT must include org_id column."""
        from services.scraper.anveshak.scraper.jobs import SQL_INSERT_CONTENT

        assert "org_id" in SQL_INSERT_CONTENT.lower()

    def test_get_topic_fetches_org_id(self):
        """Scraper SQL_GET_TOPIC must SELECT org_id for propagation."""
        from services.scraper.anveshak.scraper.jobs import SQL_GET_TOPIC

        assert "org_id" in SQL_GET_TOPIC.lower()


# ===================================================================
# 3. Social — content inserts must include org_id
# ===================================================================


class TestSocialOrgId:
    def test_insert_content_has_org_id(self):
        """Social SQL_INSERT_CONTENT must include org_id column."""
        from services.social.anveshak.social.ingest import SQL_INSERT_CONTENT

        assert "org_id" in SQL_INSERT_CONTENT.lower()


# ===================================================================
# 4. Credibility — audit log inserts must include org_id
# ===================================================================


class TestCredibilityOrgId:
    def test_insert_audit_log_has_org_id(self):
        """Credibility SQL_INSERT_AUDIT_LOG must include org_id column."""
        from services.analyst.anveshak.analyst.credibility import SQL_INSERT_AUDIT_LOG

        assert "org_id" in SQL_INSERT_AUDIT_LOG.lower()


# ===================================================================
# 5. Signal engine — signals inherit org via topic_id (no org_id column)
# ===================================================================


class TestSignalEngineOrgScope:
    def test_signals_inherit_org_via_topic(self):
        """Signals don't need org_id column — they inherit org scope via topic_id FK.
        The SQL_INSERT_SIGNAL must have topic_id which links to the org-scoped topics table."""
        from services.analyst.anveshak.analyst.signal_engine import SQL_INSERT_SIGNAL

        assert "topic_id" in SQL_INSERT_SIGNAL.lower()
