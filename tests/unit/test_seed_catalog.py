"""Unit tests for catalog seed script — manifest loading and idempotency."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_load_manifests_finds_json_files(tmp_path):
    """load_manifests reads all JSON files from catalog directory."""
    from scripts.seed_catalog import load_manifests

    # Use real catalog dir
    entries = load_manifests()
    assert len(entries) > 0, "Should find at least one entry in scripts/catalog/"


def test_load_manifests_has_required_fields():
    """Every manifest entry must have name, url_or_handle, platform."""
    from scripts.seed_catalog import load_manifests

    entries = load_manifests()
    for entry in entries:
        assert "name" in entry, f"Entry missing 'name': {entry}"
        assert "url_or_handle" in entry, f"Entry missing 'url_or_handle': {entry}"
        assert "platform" in entry, f"Entry missing 'platform': {entry}"


def test_load_manifests_valid_platforms():
    """Every manifest entry must have a valid platform."""
    from scripts.seed_catalog import load_manifests

    valid_platforms = {"web", "telegram", "twitter", "reddit", "bluesky", "rss", "darkweb"}
    entries = load_manifests()
    for entry in entries:
        assert entry["platform"] in valid_platforms, (
            f"Invalid platform '{entry['platform']}' in entry '{entry['name']}'"
        )


def test_load_manifests_valid_reliability_tiers():
    """Every manifest entry must have a valid reliability_tier."""
    from scripts.seed_catalog import load_manifests

    valid_tiers = {"S", "A", "B", "C"}
    entries = load_manifests()
    for entry in entries:
        tier = entry.get("reliability_tier", "C")
        assert tier in valid_tiers, f"Invalid tier '{tier}' in entry '{entry['name']}'"


def test_load_manifests_no_duplicate_handles():
    """No two entries should have the same (platform, url_or_handle) pair."""
    from scripts.seed_catalog import load_manifests

    entries = load_manifests()
    seen = set()
    for entry in entries:
        key = (entry["platform"], entry["url_or_handle"])
        assert key not in seen, (
            f"Duplicate (platform, url_or_handle): {key} in entry '{entry['name']}'"
        )
        seen.add(key)


def test_load_manifests_domain_tags_are_lists():
    """domain_tags must always be a list (even if empty)."""
    from scripts.seed_catalog import load_manifests

    entries = load_manifests()
    for entry in entries:
        tags = entry.get("domain_tags", [])
        assert isinstance(tags, list), (
            f"domain_tags must be a list in entry '{entry['name']}', got {type(tags)}"
        )
