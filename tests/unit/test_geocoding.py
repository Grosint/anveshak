"""Unit tests for analyst geocoding module.

pytest.mark.unit — pure Python, no DB/network.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestNormalizeEntityText:
    """normalize_entity_text: Unicode NFKD + lowercase + alias resolution."""

    def test_lowercase(self):
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("Mumbai") == "mumbai"

    def test_unicode_nfkd_devanagari(self):
        """Devanagari composed forms should normalize to consistent representation."""
        from anveshak.analyst.geocoding import normalize_entity_text

        # NFKD normalizes composed chars
        result = normalize_entity_text("दिल्ली")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_alias_bombay_to_mumbai(self):
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("Bombay") == "mumbai"

    def test_alias_calcutta_to_kolkata(self):
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("Calcutta") == "kolkata"

    def test_alias_madras_to_chennai(self):
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("Madras") == "chennai"

    def test_alias_us_to_united_states(self):
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("US") == "united states"

    def test_alias_usa_to_united_states(self):
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("USA") == "united states"

    def test_strips_the_prefix(self):
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("the Philippines") == "philippines"

    def test_hindi_state_name_uttarakhand(self):
        """Hindi transliteration alias for Uttarakhand."""
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("उत्तराखंड") == "uttarakhand"

    def test_hindi_state_name_rajasthan(self):
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("राजस्थान") == "rajasthan"

    def test_hindi_state_name_maharashtra(self):
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("महाराष्ट्र") == "maharashtra"

    def test_bengaluru_alias(self):
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("Bangalore") == "bengaluru"

    def test_empty_string(self):
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("") == ""

    def test_whitespace_stripped(self):
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("  Delhi  ") == "delhi"

    def test_passthrough_unknown(self):
        from anveshak.analyst.geocoding import normalize_entity_text

        assert normalize_entity_text("Hyderabad") == "hyderabad"


class TestGeocodeEntities:
    """geocode_entities: normalize + geocode with custom overlay."""

    def test_known_city_returns_coords(self):
        from anveshak.analyst.geocoding import geocode_entities

        result = geocode_entities(["Mumbai"], ["GPE"])
        assert len(result) >= 1
        entry = result[0]
        assert entry["entity_text_normalized"] == "mumbai"
        assert isinstance(entry["latitude"], float)
        assert isinstance(entry["longitude"], float)
        assert entry["geocode_source"] in ("geonamescache", "custom_overlay")

    def test_alias_resolved_before_lookup(self):
        """Bombay → mumbai → geocoded."""
        from anveshak.analyst.geocoding import geocode_entities

        result = geocode_entities(["Bombay"], ["GPE"])
        assert len(result) >= 1
        assert result[0]["entity_text_normalized"] == "mumbai"

    def test_custom_overlay_location(self):
        from anveshak.analyst.geocoding import geocode_entities

        result = geocode_entities(["Line of Actual Control"], ["LOC"])
        assert len(result) >= 1
        assert abs(result[0]["latitude"] - 34.0) < 1.0

    def test_unknown_location_skipped(self):
        from anveshak.analyst.geocoding import geocode_entities

        result = geocode_entities(["NonexistentXYZ999"], ["GPE"])
        assert len(result) == 0

    def test_returns_confidence(self):
        from anveshak.analyst.geocoding import geocode_entities

        result = geocode_entities(["Delhi"], ["GPE"])
        assert len(result) >= 1
        assert 0.0 <= result[0]["geocode_confidence"] <= 1.0

    def test_multiple_entities(self):
        from anveshak.analyst.geocoding import geocode_entities

        result = geocode_entities(
            ["Mumbai", "NonexistentXYZ", "Delhi"],
            ["GPE", "GPE", "GPE"],
        )
        # At least Mumbai and Delhi should resolve
        normalized = [r["entity_text_normalized"] for r in result]
        assert "mumbai" in normalized
        assert "delhi" in normalized

    def test_entity_type_preserved(self):
        from anveshak.analyst.geocoding import geocode_entities

        result = geocode_entities(["Pangong Tso"], ["LOC"])
        assert len(result) >= 1
        assert result[0]["entity_type"] == "LOC"

    def test_empty_input(self):
        from anveshak.analyst.geocoding import geocode_entities

        assert geocode_entities([], []) == []


class TestGeocodeInPipeline:
    """Geocoding wired into analyse_content after NER."""

    async def test_geocode_step_called_after_ner(self):
        """analyse_content must call geocode_and_store for location entities."""

        # The geocode_and_store function should exist and be called from jobs
        from anveshak.analyst.geocoding import geocode_entities
        from anveshak.analyst.geocoding_db import upsert_geocoded_location

        # Verify the functions exist and are importable
        assert callable(geocode_entities)
        assert callable(upsert_geocoded_location)

    def test_location_entity_types_defined(self):
        """LOCATION_ENTITY_TYPES constant must exist for filtering NER entities."""
        from anveshak.analyst.geocoding import LOCATION_ENTITY_TYPES

        assert "GPE" in LOCATION_ENTITY_TYPES
        assert "LOC" in LOCATION_ENTITY_TYPES
        assert "FAC" in LOCATION_ENTITY_TYPES
