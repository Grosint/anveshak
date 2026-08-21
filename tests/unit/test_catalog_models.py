"""Unit tests for catalog/discovery Pydantic models.

Validates Labels is mandatory (non-Optional), strict mode, and field types.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_catalog_entry_has_mandatory_labels():
    """CatalogEntry.labels must be non-Optional (AGENTS.md rule 2)."""
    from anveshak.models.catalog import CatalogEntry

    field = CatalogEntry.model_fields["labels"]
    # labels must NOT have a default of None and must NOT be Optional
    assert field.is_required() or field.default is not None, (
        "CatalogEntry.labels must not be Optional — AGENTS.md rule 2"
    )
    # Verify it cannot be None
    with pytest.raises(Exception):
        CatalogEntry(
            name="test",
            url_or_handle="https://test.com",
            platform="web",
            labels=None,
        )


def test_catalog_entry_strict_mode():
    """CatalogEntry must use strict=True."""
    from anveshak.models.catalog import CatalogEntry

    assert CatalogEntry.model_config.get("strict") is True


def test_catalog_entry_defaults():
    """CatalogEntry fields have sensible defaults."""
    from anveshak.models.base import Labels
    from anveshak.models.catalog import CatalogEntry

    entry = CatalogEntry(
        name="Test Source",
        url_or_handle="@test_channel",
        platform="telegram",
        labels=Labels(),
    )
    assert entry.reliability_tier == "C"
    assert entry.recommendation_rank == "curated"
    assert entry.signal_contribution_count == 0
    assert entry.topics_approved_count == 0
    assert entry.domain_tags == []
    assert entry.id  # auto-generated UUID


def test_catalog_entry_domain_tags():
    """CatalogEntry.domain_tags accepts list of strings."""
    from anveshak.models.base import Labels
    from anveshak.models.catalog import CatalogEntry

    entry = CatalogEntry(
        name="Test",
        url_or_handle="https://test.com",
        platform="web",
        domain_tags=["china", "military", "cyber"],
        labels=Labels(),
    )
    assert entry.domain_tags == ["china", "military", "cyber"]


def test_discovered_source_has_mandatory_labels():
    """DiscoveredSource.labels must be non-Optional."""
    from anveshak.models.catalog import DiscoveredSource

    field = DiscoveredSource.model_fields["labels"]
    assert field.is_required() or field.default is not None
    with pytest.raises(Exception):
        DiscoveredSource(
            topic_id="t1",
            domain_or_handle="example.com",
            discovery_method="snowball",
            labels=None,
        )


def test_discovered_source_strict_mode():
    """DiscoveredSource must use strict=True."""
    from anveshak.models.catalog import DiscoveredSource

    assert DiscoveredSource.model_config.get("strict") is True


def test_discovered_source_defaults():
    """DiscoveredSource has correct defaults."""
    from anveshak.models.base import Labels
    from anveshak.models.catalog import DiscoveredSource

    ds = DiscoveredSource(
        topic_id="topic-1",
        domain_or_handle="example.com",
        discovery_method="snowball",
        labels=Labels(),
    )
    assert ds.platform == "web"
    assert ds.citation_count == 1
    assert ds.status == "pending"
    assert ds.source_id is None


def test_source_suggestion_has_mandatory_labels():
    """SourceSuggestion.labels must be non-Optional."""
    from anveshak.models.catalog import SourceSuggestion

    field = SourceSuggestion.model_fields["labels"]
    assert field.is_required() or field.default is not None


def test_source_suggestion_strict_mode():
    """SourceSuggestion must use strict=True."""
    from anveshak.models.catalog import SourceSuggestion

    assert SourceSuggestion.model_config.get("strict") is True


def test_source_suggestion_fields():
    """SourceSuggestion must have platform, description, search_terms, reasoning."""
    from anveshak.models.base import Labels
    from anveshak.models.catalog import SourceSuggestion

    ss = SourceSuggestion(
        platform="telegram",
        description="Myanmar-language military channels",
        search_terms=["myanmar", "tatmadaw"],
        reasoning="Topic covers India-Myanmar border",
        labels=Labels(),
    )
    assert ss.platform == "telegram"
    assert len(ss.search_terms) == 2


def test_catalog_approval_fields():
    """CatalogApproval must have required fields."""
    from anveshak.models.base import Labels
    from anveshak.models.catalog import CatalogApproval

    ca = CatalogApproval(
        catalog_entry_id="ce-1",
        topic_id="t-1",
        source_id="s-1",
        approved_by="analyst@example.com",
        labels=Labels(),
    )
    assert ca.catalog_entry_id == "ce-1"
    assert ca.approved_at is not None
