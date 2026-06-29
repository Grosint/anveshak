"""Tests for location entity normalization — case folding + alias merging.

pytest.mark.unit — no external dependencies.
"""
from __future__ import annotations

import pytest


@pytest.mark.unit
class TestLocationMapSQL:
    """SQL_TOPIC_LOCATION_MAP must case-fold entity_text for grouping."""

    def test_groups_by_lowercase_entity_text(self):
        """GROUP BY must use LOWER(entity_text) to merge case variants."""
        from anveshak.api.routes.intelligence import SQL_TOPIC_LOCATION_MAP
        sql = SQL_TOPIC_LOCATION_MAP.lower()
        assert "lower(ee.entity_text)" in sql, \
            "GROUP BY must use LOWER(ee.entity_text) to merge 'India'/'india'"

    def test_selects_entity_key_as_lowercase(self):
        """SELECT must return LOWER(entity_text) as entity_key."""
        from anveshak.api.routes.intelligence import SQL_TOPIC_LOCATION_MAP
        sql = SQL_TOPIC_LOCATION_MAP.lower()
        assert "entity_key" in sql, \
            "Must SELECT LOWER(entity_text) AS entity_key"


@pytest.mark.unit
class TestNormalizeLocation:
    """_normalize_location handles case variants and common aliases."""

    def test_lowercase(self):
        from anveshak.api.routes.intelligence import _normalize_location
        assert _normalize_location("India") == "india"

    def test_alias_us(self):
        from anveshak.api.routes.intelligence import _normalize_location
        assert _normalize_location("US") == "united states"

    def test_alias_the_united_states(self):
        from anveshak.api.routes.intelligence import _normalize_location
        assert _normalize_location("the United States") == "united states"

    def test_alias_bombay(self):
        from anveshak.api.routes.intelligence import _normalize_location
        assert _normalize_location("Bombay") == "mumbai"

    def test_strips_the_prefix(self):
        from anveshak.api.routes.intelligence import _normalize_location
        # "the Caribbean" → "caribbean" (stripped "the ")
        assert _normalize_location("the Caribbean") == "caribbean"

    def test_passthrough(self):
        from anveshak.api.routes.intelligence import _normalize_location
        assert _normalize_location("Hyderabad") == "hyderabad"


@pytest.mark.unit
class TestMergeLocationRows:
    """_merge_location_rows collapses rows by normalized name."""

    def test_merges_case_variants(self):
        from anveshak.api.routes.intelligence import _merge_location_rows
        rows = [
            {"entity_key": "india", "entity_type": "GPE",
             "mention_count": 72, "source_count": 3, "latest_mention": None},
            {"entity_key": "india", "entity_type": "GPE",
             "mention_count": 50, "source_count": 4, "latest_mention": None},
        ]
        merged = _merge_location_rows(rows)
        # SQL already lowered, so both are "india" — but if alias varies, still merges
        assert len(merged) == 1
        assert merged["india"]["mention_count"] == 122

    def test_merges_alias_variants(self):
        from anveshak.api.routes.intelligence import _merge_location_rows
        rows = [
            {"entity_key": "us", "entity_type": "GPE",
             "mention_count": 35, "source_count": 3, "latest_mention": None},
            {"entity_key": "the united states", "entity_type": "GPE",
             "mention_count": 23, "source_count": 2, "latest_mention": None},
            {"entity_key": "united states", "entity_type": "GPE",
             "mention_count": 10, "source_count": 1, "latest_mention": None},
        ]
        merged = _merge_location_rows(rows)
        assert len(merged) == 1
        assert merged["united states"]["mention_count"] == 68

    def test_merges_source_count_max(self):
        """source_count should take max (not sum — sources overlap across variants)."""
        from anveshak.api.routes.intelligence import _merge_location_rows
        rows = [
            {"entity_key": "india", "entity_type": "GPE",
             "mention_count": 72, "source_count": 3, "latest_mention": None},
            {"entity_key": "india", "entity_type": "GPE",
             "mention_count": 50, "source_count": 4, "latest_mention": None},
        ]
        merged = _merge_location_rows(rows)
        # Sources overlap — max is more accurate than sum
        assert merged["india"]["source_count"] == 4

    def test_keeps_latest_mention(self):
        from datetime import datetime, timezone
        from anveshak.api.routes.intelligence import _merge_location_rows
        t1 = datetime(2026, 6, 28, tzinfo=timezone.utc)
        t2 = datetime(2026, 6, 29, tzinfo=timezone.utc)
        rows = [
            {"entity_key": "india", "entity_type": "GPE",
             "mention_count": 72, "source_count": 3, "latest_mention": t1},
            {"entity_key": "india", "entity_type": "GPE",
             "mention_count": 50, "source_count": 4, "latest_mention": t2},
        ]
        merged = _merge_location_rows(rows)
        assert merged["india"]["latest_mention"] == t2

    def test_different_entity_types_stay_separate(self):
        """Same name but different entity_type should NOT merge."""
        from anveshak.api.routes.intelligence import _merge_location_rows
        rows = [
            {"entity_key": "delhi", "entity_type": "GPE",
             "mention_count": 40, "source_count": 3, "latest_mention": None},
            {"entity_key": "delhi", "entity_type": "FAC",
             "mention_count": 5, "source_count": 1, "latest_mention": None},
        ]
        merged = _merge_location_rows(rows)
        # GPE "delhi" and FAC "delhi" are different concepts — keep separate
        assert len(merged) == 2
        assert "delhi:GPE" in merged
        assert "delhi:FAC" in merged

    def test_preserves_non_alias_entries(self):
        from anveshak.api.routes.intelligence import _merge_location_rows
        rows = [
            {"entity_key": "hyderabad", "entity_type": "GPE",
             "mention_count": 141, "source_count": 3, "latest_mention": None},
            {"entity_key": "cambodia", "entity_type": "GPE",
             "mention_count": 35, "source_count": 1, "latest_mention": None},
        ]
        merged = _merge_location_rows(rows)
        assert len(merged) == 2
        assert merged["hyderabad"]["mention_count"] == 141


@pytest.mark.unit
class TestDisplayName:
    """_location_display_name produces clean title-case names."""

    def test_simple_titlecase(self):
        from anveshak.api.routes.intelligence import _location_display_name
        assert _location_display_name("hyderabad") == "Hyderabad"

    def test_known_display_name(self):
        from anveshak.api.routes.intelligence import _location_display_name
        assert _location_display_name("united states") == "United States"

    def test_multi_word(self):
        from anveshak.api.routes.intelligence import _location_display_name
        assert _location_display_name("new delhi") == "New Delhi"
