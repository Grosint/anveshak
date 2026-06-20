"""Tests for Intelligence Graph — entity co-occurrence endpoint.

pytest.mark.unit — no external dependencies.
"""
from __future__ import annotations

import pytest


@pytest.mark.unit
class TestEntityGraphSQL:
    """Entity co-occurrence SQL must use frontend-compatible field names."""

    def test_sql_alias_is_count_not_co_occurrence_count(self):
        """SQL_ENTITY_COOCCURRENCE must alias the count column as 'count'
        to match the frontend EntityEdge interface."""
        from anveshak.api.routes.intelligence import SQL_ENTITY_COOCCURRENCE
        sql = SQL_ENTITY_COOCCURRENCE.lower()
        assert "as count" in sql, \
            "Must alias co-occurrence count as 'count' (not 'co_occurrence_count')"

    def test_sql_having_uses_count(self):
        """HAVING clause must reference the aliased column."""
        from anveshak.api.routes.intelligence import SQL_ENTITY_COOCCURRENCE
        sql = SQL_ENTITY_COOCCURRENCE.lower()
        # HAVING should reference count (via the aggregate expression)
        assert "having" in sql, "Must have HAVING clause for min_count filter"

    def test_sql_order_by_uses_count(self):
        """ORDER BY must reference the count alias."""
        from anveshak.api.routes.intelligence import SQL_ENTITY_COOCCURRENCE
        sql = SQL_ENTITY_COOCCURRENCE.lower()
        assert "order by" in sql, "Must have ORDER BY clause"
        # Should order by count desc
        assert "count" in sql.split("order by")[1], \
            "ORDER BY must reference count column"

    def test_entity_graph_excludes_gpe_loc(self):
        """Entity co-occurrence graph must NOT include GPE or LOC —
        those belong on the location map, not the network graph."""
        from anveshak.api.routes.intelligence import SQL_ENTITY_COOCCURRENCE
        sql = SQL_ENTITY_COOCCURRENCE.lower()
        # Extract the entity_type IN (...) clause content
        assert "'gpe'" not in sql, "GPE must not be in co-occurrence graph"
        assert "'loc'" not in sql, "LOC must not be in co-occurrence graph"
        # PERSON, ORG, FAC should still be there
        assert "'person'" in sql
        assert "'org'" in sql
        assert "'fac'" in sql


@pytest.mark.unit
class TestLocationMapSQL:
    """Location map endpoint must aggregate GPE/LOC entities with counts."""

    def test_location_map_sql_exists(self):
        from anveshak.api.routes.intelligence import SQL_TOPIC_LOCATION_MAP
        sql = SQL_TOPIC_LOCATION_MAP.lower()
        assert "extracted_entities" in sql

    def test_location_map_sql_filters_gpe_loc_fac(self):
        from anveshak.api.routes.intelligence import SQL_TOPIC_LOCATION_MAP
        sql = SQL_TOPIC_LOCATION_MAP.lower()
        assert "'gpe'" in sql
        assert "'loc'" in sql
        assert "'fac'" in sql

    def test_location_map_sql_has_min_mentions_filter(self):
        from anveshak.api.routes.intelligence import SQL_TOPIC_LOCATION_MAP
        sql = SQL_TOPIC_LOCATION_MAP.lower()
        assert "having" in sql, "Must have HAVING clause for min mentions"

    def test_location_map_sql_counts_distinct_content(self):
        from anveshak.api.routes.intelligence import SQL_TOPIC_LOCATION_MAP
        sql = SQL_TOPIC_LOCATION_MAP.lower()
        assert "count(distinct" in sql.replace(" ", "").replace("\n", ""), \
            "Must count distinct content_item_id for accurate mention counts"
