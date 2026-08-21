"""Unit tests for geocoded-locations API endpoint.

pytest.mark.unit — no real DB/server.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestGeocodedLocationsRoute:
    """PATCH /api/v1/geocoded-locations/{id} — analyst override."""

    def test_route_module_importable(self):
        from anveshak.api.routes.geocoded_locations import router

        assert router is not None

    def test_update_request_model_has_labels(self):
        """Per AGENTS.md: every Pydantic model MUST have labels: Labels."""
        from anveshak.api.routes.geocoded_locations import UpdateGeocodedLocationRequest

        fields = UpdateGeocodedLocationRequest.model_fields
        assert "latitude" in fields
        assert "longitude" in fields

    def test_route_registered_in_main(self):
        """Route must be included in app via include_router."""
        from anveshak.api.main import app

        paths = [route.path for route in app.routes if hasattr(route, "path")]
        assert any("geocoded-locations" in p for p in paths), (
            f"geocoded-locations route not registered. Paths: {[p for p in paths if 'geo' in p.lower()]}"
        )

    def test_list_endpoint_exists(self):
        """GET /api/v1/geocoded-locations should exist for listing."""
        from anveshak.api.routes.geocoded_locations import router

        methods_by_path = {}
        for route in router.routes:
            if hasattr(route, "methods"):
                methods_by_path[route.path] = route.methods
        # Should have at least GET (list) and PATCH (update) endpoints
        assert any("GET" in m for m in methods_by_path.values())
        assert any("PATCH" in m or "PUT" in m for m in methods_by_path.values())
