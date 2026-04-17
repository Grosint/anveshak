"""Unit tests for cluster merge endpoint SQL and logic.

Tests:
  - Merge SQL reassigns content items
  - Merge SQL updates cluster counts
  - Merge SQL deletes absorbed cluster
  - Cluster lookup query is correct
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestClusterMergeSQL:

    def test_reassign_query_updates_cluster_id(self):
        from anveshak.api.routes.intelligence import SQL_REASSIGN_CONTENT_ITEMS

        assert "narrative_cluster_id = $1" in SQL_REASSIGN_CONTENT_ITEMS
        assert "narrative_cluster_id = $2" in SQL_REASSIGN_CONTENT_ITEMS

    def test_update_counts_recalculates_item_count(self):
        from anveshak.api.routes.intelligence import SQL_UPDATE_CLUSTER_COUNTS

        assert "COUNT(*)" in SQL_UPDATE_CLUSTER_COUNTS
        assert "narrative_cluster_id = $1" in SQL_UPDATE_CLUSTER_COUNTS

    def test_update_counts_recalculates_independent_sources(self):
        from anveshak.api.routes.intelligence import SQL_UPDATE_CLUSTER_COUNTS

        assert "COUNT(DISTINCT s.platform)" in SQL_UPDATE_CLUSTER_COUNTS

    def test_delete_cluster_query(self):
        from anveshak.api.routes.intelligence import SQL_DELETE_CLUSTER

        assert "DELETE FROM narrative_clusters" in SQL_DELETE_CLUSTER
        assert "id = $1" in SQL_DELETE_CLUSTER

    def test_get_cluster_query(self):
        from anveshak.api.routes.intelligence import SQL_GET_CLUSTER

        assert "SELECT" in SQL_GET_CLUSTER
        assert "narrative_clusters" in SQL_GET_CLUSTER
        assert "id = $1" in SQL_GET_CLUSTER
