"""Unit tests for catalog API routes — mock DB, verify endpoint logic."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_catalog_row(**overrides):
    """Build a dict mimicking a source_catalog DB row."""
    base = {
        "id": "cat-1",
        "name": "China Military Review",
        "url_or_handle": "@ChinaMilitaryReview",
        "platform": "telegram",
        "domain_tags": ["china", "military"],
        "reliability_tier": "A",
        "bias_indicator": "state-aligned",
        "risk_level": "medium",
        "language": "en",
        "category": "military",
        "description": "PLA force movements and exercises",
        "subscriber_count": 45000,
        "activity_frequency": "daily",
        "signal_contribution_count": 5,
        "relevance_hit_rate": 0.78,
        "cluster_participation_rate": 0.45,
        "topics_approved_count": 3,
        "recommendation_rank": "most_recommended",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return base


def _fake_discovered_row(**overrides):
    """Build a dict mimicking a discovered_sources DB row."""
    base = {
        "id": "disc-1",
        "topic_id": "topic-1",
        "domain_or_handle": "example.com",
        "platform": "web",
        "discovery_method": "snowball",
        "citation_count": 5,
        "confidence_score": 0.8,
        "evidence": '{"citing_sources": ["src1", "src2"]}',
        "status": "pending",
        "source_id": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# GET /api/v1/topics/{topic_id}/catalog-suggestions
# ---------------------------------------------------------------------------


async def test_catalog_suggestions_returns_list():
    """GET catalog-suggestions returns matching catalog entries."""
    from anveshak.api.routes.catalog import get_catalog_suggestions

    mock_conn = AsyncMock()
    mock_user = {"user_id": "test-user", "role": "analyst", "org_id": "org-test"}

    with (
        patch("anveshak.api.routes.catalog.topics_db.verify_topic_access", new=AsyncMock()),
        patch("anveshak.api.routes.catalog.catalog_db") as mock_db,
    ):
        # Mock: topic exists with keywords
        mock_conn.fetchrow = AsyncMock(return_value={"keywords": ["china", "military"]})
        mock_db.list_catalog_suggestions = AsyncMock(return_value=[_fake_catalog_row()])

        result = await get_catalog_suggestions("topic-1", db=mock_conn, user=mock_user)

    assert len(result["suggestions"]) == 1
    assert result["suggestions"][0]["name"] == "China Military Review"
    assert result["topic_id"] == "topic-1"


async def test_catalog_suggestions_404_on_missing_topic():
    """GET catalog-suggestions returns 404 if topic doesn't exist."""
    from anveshak.api.routes.catalog import get_catalog_suggestions
    from fastapi import HTTPException

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_user = {"user_id": "test-user", "role": "analyst"}

    with pytest.raises(HTTPException) as exc_info:
        await get_catalog_suggestions("nonexistent", db=mock_conn, user=mock_user)
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/topics/{topic_id}/catalog-approve
# ---------------------------------------------------------------------------


async def test_catalog_approve_creates_source_and_links():
    """POST catalog-approve creates a source, links to topic, records approval."""
    from anveshak.api.routes.catalog import approve_catalog_entry

    mock_conn = AsyncMock()
    mock_user = {"user_id": "test-user", "role": "analyst", "org_id": "org-test"}

    with (
        patch("anveshak.api.routes.catalog.topics_db.verify_topic_access", new=AsyncMock()),
        patch("anveshak.api.routes.catalog.catalog_db") as mock_catalog_db,
        patch("anveshak.api.routes.catalog.sources_db") as mock_sources_db,
    ):
        mock_catalog_db.get_catalog_entry = AsyncMock(return_value=_fake_catalog_row())
        mock_sources_db.insert_source = AsyncMock()
        mock_sources_db.add_topic_source = AsyncMock()
        mock_sources_db.source_exists = AsyncMock(return_value=False)
        mock_catalog_db.insert_catalog_approval = AsyncMock()
        mock_conn.execute = AsyncMock()

        result = await approve_catalog_entry(
            topic_id="topic-1",
            catalog_entry_id="cat-1",
            db=mock_conn,
            user=mock_user,
        )

    assert result["catalog_entry_id"] == "cat-1"
    assert "source_id" in result
    # Verify source was inserted and linked
    mock_sources_db.insert_source.assert_called_once()
    mock_sources_db.add_topic_source.assert_called_once()
    # Verify catalog approval was recorded
    mock_catalog_db.insert_catalog_approval.assert_called_once()


async def test_catalog_approve_404_on_missing_entry():
    """POST catalog-approve returns 404 if catalog entry doesn't exist."""
    from anveshak.api.routes.catalog import approve_catalog_entry
    from fastapi import HTTPException

    mock_conn = AsyncMock()
    mock_user = {"user_id": "test-user", "role": "analyst"}

    with patch("anveshak.api.routes.catalog.catalog_db") as mock_catalog_db:
        mock_catalog_db.get_catalog_entry = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await approve_catalog_entry("topic-1", "nonexistent", db=mock_conn, user=mock_user)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/catalog
# ---------------------------------------------------------------------------


async def test_list_all_catalog_returns_entries():
    """GET /api/v1/catalog returns all catalog entries."""
    from anveshak.api.routes.catalog import list_catalog

    mock_conn = AsyncMock()
    mock_user = {"user_id": "test-user", "role": "admin"}

    with patch("anveshak.api.routes.catalog.catalog_db") as mock_db:
        mock_db.list_all_catalog = AsyncMock(
            return_value=[
                _fake_catalog_row(),
                _fake_catalog_row(id="cat-2", name="Another Source"),
            ]
        )

        result = await list_catalog(db=mock_conn, user=mock_user)

    assert len(result["entries"]) == 2


# ---------------------------------------------------------------------------
# GET /api/v1/topics/{topic_id}/discovered
# ---------------------------------------------------------------------------


async def test_list_discovered_returns_sources():
    """GET discovered sources returns list for topic."""
    from anveshak.api.routes.catalog import list_discovered_sources

    mock_conn = AsyncMock()
    mock_user = {"user_id": "test-user", "role": "analyst", "org_id": "org-test"}

    with (
        patch("anveshak.api.routes.catalog.topics_db.verify_topic_access", new=AsyncMock()),
        patch("anveshak.api.routes.catalog.catalog_db") as mock_db,
    ):
        mock_db.list_discovered = AsyncMock(return_value=[_fake_discovered_row()])

        result = await list_discovered_sources(
            topic_id="topic-1", status=None, db=mock_conn, user=mock_user
        )

    assert len(result["discovered"]) == 1
    assert result["discovered"][0]["domain_or_handle"] == "example.com"


# ---------------------------------------------------------------------------
# POST /api/v1/topics/{topic_id}/discovered/{id}/approve
# ---------------------------------------------------------------------------


async def test_approve_discovered_creates_source():
    """POST approve discovered creates source and updates status."""
    from anveshak.api.routes.catalog import approve_discovered_source

    mock_conn = AsyncMock()
    mock_user = {"user_id": "test-user", "role": "analyst", "org_id": "org-test"}

    with (
        patch("anveshak.api.routes.catalog.topics_db.verify_topic_access", new=AsyncMock()),
        patch("anveshak.api.routes.catalog.catalog_db") as mock_catalog_db,
        patch("anveshak.api.routes.catalog.sources_db") as mock_sources_db,
    ):
        mock_conn.fetchrow = AsyncMock(return_value=_fake_discovered_row())
        mock_sources_db.insert_source = AsyncMock()
        mock_sources_db.add_topic_source = AsyncMock()
        mock_catalog_db.approve_discovered = AsyncMock()
        mock_conn.execute = AsyncMock()

        result = await approve_discovered_source(
            topic_id="topic-1",
            discovered_id="disc-1",
            db=mock_conn,
            user=mock_user,
        )

    assert "source_id" in result
    mock_sources_db.insert_source.assert_called_once()
    mock_sources_db.add_topic_source.assert_called_once()
    mock_catalog_db.approve_discovered.assert_called_once()


# ---------------------------------------------------------------------------
# POST /api/v1/topics/{topic_id}/discovered/{id}/dismiss
# ---------------------------------------------------------------------------


async def test_dismiss_discovered_updates_status():
    """POST dismiss discovered sets status to dismissed."""
    from anveshak.api.routes.catalog import dismiss_discovered_source

    mock_conn = AsyncMock()
    mock_user = {"user_id": "test-user", "role": "analyst", "org_id": "org-test"}

    with (
        patch("anveshak.api.routes.catalog.topics_db.verify_topic_access", new=AsyncMock()),
        patch("anveshak.api.routes.catalog.catalog_db") as mock_catalog_db,
    ):
        mock_conn.fetchrow = AsyncMock(return_value=_fake_discovered_row())
        mock_catalog_db.dismiss_discovered = AsyncMock()

        result = await dismiss_discovered_source(
            topic_id="topic-1",
            discovered_id="disc-1",
            db=mock_conn,
            user=mock_user,
        )

    assert result["status"] == "dismissed"
    mock_catalog_db.dismiss_discovered.assert_called_once()
