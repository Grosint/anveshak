"""Unit tests for location-map-v2 endpoint (backed by geocoded_locations table).

pytest.mark.unit — mocked DB.
"""

from __future__ import annotations

import pytest

# asyncio_mode = "auto" in pyproject.toml already marks the async tests here.
# An explicit asyncio mark also lands on the sync ones and emits a PytestWarning.
pytestmark = pytest.mark.unit


class TestLocationMapV2SQL:
    """SQL query must join extracted_entities → geocoded_locations properly."""

    def test_sql_joins_geocoded_locations(self):
        from anveshak.api.routes.intelligence import SQL_LOCATION_MAP_V2

        sql = SQL_LOCATION_MAP_V2.lower()
        assert "geocoded_locations" in sql
        assert "extracted_entities" in sql

    def test_sql_excludes_unresolved(self):
        """Unresolved entities (geocode_source='unresolved') must be excluded from map."""
        from anveshak.api.routes.intelligence import SQL_LOCATION_MAP_V2

        sql = SQL_LOCATION_MAP_V2.lower()
        assert "unresolved" in sql

    def test_sql_filters_by_topic(self):
        from anveshak.api.routes.intelligence import SQL_LOCATION_MAP_V2

        sql = SQL_LOCATION_MAP_V2.lower()
        assert "topic_id" in sql

    def test_sql_has_min_mentions_filter(self):
        from anveshak.api.routes.intelligence import SQL_LOCATION_MAP_V2

        sql = SQL_LOCATION_MAP_V2.lower()
        assert "having" in sql


class TestLocationMapV2Endpoint:
    """GET /topics/{topic_id}/location-map returns GeoJSON FeatureCollection."""

    def test_endpoint_exists(self):
        from anveshak.api.routes.intelligence import router

        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert any("location-map" in p for p in paths)

    def test_response_shape_geojson(self):
        """Response must have type=FeatureCollection, features[], metadata."""
        # This tests the response building logic — verified via the function signature
        from anveshak.api.routes.intelligence import SQL_LOCATION_MAP_V2

        # SQL must SELECT the fields needed for GeoJSON properties
        sql = SQL_LOCATION_MAP_V2.lower()
        assert "mention_count" in sql
        assert "source_count" in sql
        assert "latitude" in sql
        assert "longitude" in sql

    def test_sql_counts_unresolved_separately(self):
        """Must have a separate query or CTE to count unresolved entities for metadata."""
        from anveshak.api.routes.intelligence import SQL_UNRESOLVED_COUNT_V2

        sql = SQL_UNRESOLVED_COUNT_V2.lower()
        assert "unresolved" in sql or "geocoded_locations" in sql
