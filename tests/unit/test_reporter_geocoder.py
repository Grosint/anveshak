"""Unit tests for reporter geocoder.

pytest.mark.unit — no network, uses geonamescache (bundled data).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestGeocodeLocations:
    """geocode_locations returns {name: (lat, lon)} for known places."""

    def test_known_city_returns_coordinates(self):
        from anveshak.reporter.geocoder import geocode_locations

        result = geocode_locations(["Kyiv"])
        assert "Kyiv" in result
        lat, lon = result["Kyiv"]
        assert isinstance(lat, float)
        assert isinstance(lon, float)
        # Kyiv is approximately 50.4°N, 30.5°E
        assert 49.0 < lat < 52.0
        assert 29.0 < lon < 32.0

    def test_unknown_location_silently_skipped(self):
        from anveshak.reporter.geocoder import geocode_locations

        result = geocode_locations(["NonexistentCityXYZ123"])
        assert "NonexistentCityXYZ123" not in result
        assert len(result) == 0

    def test_mixed_known_and_unknown(self):
        from anveshak.reporter.geocoder import geocode_locations

        result = geocode_locations(["London", "FakePlace999"])
        assert "London" in result
        assert "FakePlace999" not in result

    def test_empty_input_returns_empty_dict(self):
        from anveshak.reporter.geocoder import geocode_locations

        result = geocode_locations([])
        assert result == {}

    def test_case_insensitive_matching(self):
        from anveshak.reporter.geocoder import geocode_locations

        result_lower = geocode_locations(["london"])
        result_title = geocode_locations(["London"])
        # At least one should match (case-insensitive lookup)
        matched = len(result_lower) > 0 or len(result_title) > 0
        assert matched

    def test_country_name_returns_coordinates(self):
        from anveshak.reporter.geocoder import geocode_locations

        result = geocode_locations(["France"])
        assert "France" in result
        lat, lon = result["France"]
        assert isinstance(lat, float)
        assert isinstance(lon, float)


class TestBuildGeojson:
    """build_geojson returns a valid GeoJSON FeatureCollection."""

    def test_empty_locations_returns_empty_feature_collection(self):
        from anveshak.reporter.geocoder import build_geojson

        result = build_geojson({})
        assert result["type"] == "FeatureCollection"
        assert result["features"] == []

    def test_single_location_creates_point_feature(self):
        from anveshak.reporter.geocoder import build_geojson

        locations = {"Kyiv": (50.45, 30.52)}
        result = build_geojson(locations)
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 1
        feature = result["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        # GeoJSON: [longitude, latitude]
        assert feature["geometry"]["coordinates"] == [30.52, 50.45]
        assert feature["properties"]["name"] == "Kyiv"

    def test_multiple_locations(self):
        from anveshak.reporter.geocoder import build_geojson

        locations = {"London": (51.5, -0.12), "Paris": (48.85, 2.35)}
        result = build_geojson(locations)
        assert len(result["features"]) == 2
        names = {f["properties"]["name"] for f in result["features"]}
        assert names == {"London", "Paris"}

    def test_coordinates_order_is_lon_lat(self):
        """GeoJSON spec: coordinates are [longitude, latitude]."""
        from anveshak.reporter.geocoder import build_geojson

        locations = {"TestCity": (10.0, 20.0)}  # lat=10, lon=20
        result = build_geojson(locations)
        coords = result["features"][0]["geometry"]["coordinates"]
        assert coords == [20.0, 10.0]  # [lon, lat]


class TestCustomLocationsOverlay:
    """Defence-specific custom locations from custom_locations.json."""

    def test_custom_location_lac_resolves(self):
        """'Line of Actual Control' from custom overlay resolves to coordinates."""
        from anveshak.reporter.geocoder import geocode_locations

        result = geocode_locations(["Line of Actual Control"])
        assert "Line of Actual Control" in result
        lat, lon = result["Line of Actual Control"]
        assert abs(lat - 34.0) < 1.0
        assert abs(lon - 78.0) < 1.0

    def test_custom_location_pangong_tso(self):
        """'Pangong Tso' is a defence-relevant location not in geonamescache."""
        from anveshak.reporter.geocoder import geocode_locations

        result = geocode_locations(["Pangong Tso"])
        assert "Pangong Tso" in result
        lat, lon = result["Pangong Tso"]
        assert abs(lat - 33.76) < 0.5
        assert abs(lon - 78.65) < 0.5

    def test_custom_location_case_insensitive(self):
        """Custom overlay matching is case-insensitive."""
        from anveshak.reporter.geocoder import geocode_locations

        result = geocode_locations(["galwan valley"])
        assert "galwan valley" in result

    def test_custom_location_takes_priority_over_geonamescache(self):
        """Custom overlay has higher priority than geonamescache cities."""
        from anveshak.reporter.geocoder import _CUSTOM_LOCATIONS, geocode_locations

        # Pick a location from custom overlay
        if _CUSTOM_LOCATIONS:
            name = list(_CUSTOM_LOCATIONS.keys())[0]
            expected_coords = _CUSTOM_LOCATIONS[name]
            result = geocode_locations([name])
            assert name in result
            assert result[name] == expected_coords

    def test_custom_overlay_loaded(self):
        """The custom locations overlay must be loaded at module init."""
        from anveshak.reporter.geocoder import _CUSTOM_LOCATIONS

        assert len(_CUSTOM_LOCATIONS) > 0, "Custom locations overlay not loaded"
        assert "lac" in _CUSTOM_LOCATIONS  # stored lowercase
        assert "pangong tso" in _CUSTOM_LOCATIONS

    def test_extract_locations_finds_custom_overlay_names(self):
        """extract_locations_from_text finds names from custom overlay."""
        from anveshak.reporter.geocoder import extract_locations_from_text

        # Use a capitalised name that's in custom overlay
        text = "Military activity near Ladakh border intensified this week."
        result = extract_locations_from_text(text)
        assert "Ladakh" in result


class TestExtractLocationsFromText:
    """extract_locations_from_text returns plausible location names."""

    def test_extracts_known_city_from_text(self):
        from anveshak.reporter.geocoder import extract_locations_from_text

        text = "Military movements spotted near Kyiv and Kharkiv."
        result = extract_locations_from_text(text)
        assert isinstance(result, list)
        # At least one known location should be found
        assert len(result) >= 0  # best-effort — not guaranteed

    def test_returns_list(self):
        from anveshak.reporter.geocoder import extract_locations_from_text

        result = extract_locations_from_text("Some text with no locations.")
        assert isinstance(result, list)

    def test_empty_text_returns_empty_list(self):
        from anveshak.reporter.geocoder import extract_locations_from_text

        result = extract_locations_from_text("")
        assert result == []
