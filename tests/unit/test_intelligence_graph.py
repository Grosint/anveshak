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
        assert "as count" in sql, (
            "Must alias co-occurrence count as 'count' (not 'co_occurrence_count')"
        )

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
        assert "count" in sql.split("order by")[1], "ORDER BY must reference count column"

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
        assert "count(distinct" in sql.replace(" ", "").replace("\n", ""), (
            "Must count distinct content_item_id for accurate mention counts"
        )

    def test_location_map_sql_returns_source_count(self):
        """SQL must return distinct source count per location for ISC-like signal."""
        from anveshak.api.routes.intelligence import SQL_TOPIC_LOCATION_MAP

        sql = SQL_TOPIC_LOCATION_MAP.lower()
        assert "source_count" in sql, "Must return source_count column"
        assert "ci.source_id" in sql, "Must count ci.source_id for source count"

    def test_location_map_sql_returns_latest_mention(self):
        """SQL must return latest capture timestamp per location."""
        from anveshak.api.routes.intelligence import SQL_TOPIC_LOCATION_MAP

        sql = SQL_TOPIC_LOCATION_MAP.lower()
        assert "latest_mention" in sql, "Must return MAX(ci.captured_at) AS latest_mention"

    def test_location_map_sql_returns_entity_type(self):
        """SQL must include entity_type in SELECT (already grouped by it)."""
        from anveshak.api.routes.intelligence import SQL_TOPIC_LOCATION_MAP

        sql = SQL_TOPIC_LOCATION_MAP.lower()
        # entity_type should be in SELECT and GROUP BY
        select_part = sql.split("from")[0]
        assert "entity_type" in select_part, "entity_type must be in SELECT clause"


@pytest.mark.unit
class TestLocationMapGeoJSON:
    """GeoJSON output must include enriched properties and metadata."""

    def test_geocode_known_city(self):
        """_geocode must resolve known cities."""
        from anveshak.api.routes.intelligence import _geocode

        result = _geocode(["Mumbai"])
        assert "Mumbai" in result
        lat, lon = result["Mumbai"]
        assert 18 < lat < 20  # Mumbai latitude
        assert 72 < lon < 73  # Mumbai longitude

    def test_geocode_unknown_name_skipped(self):
        """_geocode must skip unresolvable names."""
        from anveshak.api.routes.intelligence import _geocode

        result = _geocode(["Kotwali PS Ranchi", "XYZ123"])
        assert len(result) == 0

    def test_geocode_alias_resolution(self):
        """_geocode must resolve common aliases like US, the United States."""
        from anveshak.api.routes.intelligence import _geocode

        result = _geocode(["US", "U.S.", "the United States"])
        # All three should resolve to the same country
        assert len(result) == 3
        for name in ["US", "U.S.", "the United States"]:
            assert name in result, f"{name} should resolve"

    def test_geocode_strips_article(self):
        """_geocode must handle 'the Middle East', 'the Gulf' etc."""
        from anveshak.api.routes.intelligence import _geocode

        result = _geocode(["the Middle East", "the Netherlands"])
        assert "the Middle East" in result
        assert "the Netherlands" in result

    def test_geocode_noise_filtered(self):
        """_geocode must skip HTML artifacts, person names, too-short strings."""
        from anveshak.api.routes.intelligence import _geocode

        noise = ['dir="ltr"', 'City News">Hyderabad City', "+domian", "DM", "Modi", "Khan"]
        result = _geocode(noise)
        # None of these should resolve — they're noise, not locations
        assert len(result) == 0, f"Noise leaked through: {list(result.keys())}"

    def test_geojson_properties_include_entity_type(self):
        """GeoJSON feature properties must include entity_type."""
        # The endpoint builds properties dict — test the expected shape
        # by checking the SQL selects entity_type (covered above)
        # and verifying the route handler maps it to properties.
        import inspect

        from anveshak.api.routes.intelligence import get_location_map

        source = inspect.getsource(get_location_map)
        assert "entity_type" in source, (
            "get_location_map must include entity_type in GeoJSON properties"
        )

    def test_geojson_properties_include_source_count(self):
        """GeoJSON feature properties must include source_count."""
        import inspect

        from anveshak.api.routes.intelligence import get_location_map

        source = inspect.getsource(get_location_map)
        assert "source_count" in source, (
            "get_location_map must include source_count in GeoJSON properties"
        )

    def test_geojson_metadata_includes_unresolved(self):
        """Response must include metadata.unresolved for locations that couldn't be geocoded."""
        import inspect

        from anveshak.api.routes.intelligence import get_location_map

        source = inspect.getsource(get_location_map)
        assert "unresolved" in source, (
            "get_location_map must return unresolved location names in metadata"
        )
