"""Unit tests for provenance API — DB functions and SQL correctness.

Tests:
  - get_topic_intelligence returns all sections, empty arrays on no data
  - get_identifier_provenance returns full chain + cross-topic
  - get_content_provenance returns nested source/cluster/identifiers/vision
  - get_topic_urgency returns urgency metrics with health label
  - SQL queries have correct org/topic scoping
  - Topic list queries include urgency fields
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. Topic Intelligence
# ---------------------------------------------------------------------------

class TestGetTopicIntelligence:

    @pytest.mark.asyncio
    async def test_returns_all_sections_empty(self, mock_conn: AsyncMock) -> None:
        """Empty topic returns empty arrays and zero stats.

        get_topic_intelligence uses asyncio.gather, so fetch/fetchrow
        are called concurrently. We use side_effect to return different
        results for each concurrent call.
        """
        empty_stats = {"total_content": 0, "total_clusters": 0, "total_signals": 0}
        # 5 fetch calls + 1 fetchrow call via asyncio.gather
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchrow = AsyncMock(return_value=empty_stats)

        from services.api.anveshak.api.db.provenance import get_topic_intelligence
        result = await get_topic_intelligence(mock_conn, "topic-001")

        assert result["signals"] == []
        assert result["clusters"] == []
        assert result["identifiers"] == []
        assert result["locations"] == []
        assert result["source_health"] == []
        assert result["stats"]["total_content"] == 0

    @pytest.mark.asyncio
    async def test_passes_limits(self, mock_conn: AsyncMock) -> None:
        """Limit params forwarded to SQL queries via asyncio.gather."""
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchrow = AsyncMock(return_value={
            "total_content": 5, "total_clusters": 2, "total_signals": 1,
        })

        from services.api.anveshak.api.db.provenance import get_topic_intelligence
        await get_topic_intelligence(
            mock_conn, "topic-001",
            cluster_limit=5, identifier_limit=10, location_limit=15,
        )

        # All fetch calls made — verify cluster query got limit=5
        fetch_calls = mock_conn.fetch.call_args_list
        # Find the call that has 3 args (SQL, topic_id, cluster_limit)
        cluster_calls = [c for c in fetch_calls if len(c[0]) == 3]
        assert any(c[0][2] == 5 for c in cluster_calls)

    @pytest.mark.asyncio
    async def test_stats_fallback_when_none(self, mock_conn: AsyncMock) -> None:
        """If stats query returns None, fallback to zeros."""
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchrow = AsyncMock(return_value=None)

        from services.api.anveshak.api.db.provenance import get_topic_intelligence
        result = await get_topic_intelligence(mock_conn, "topic-001")

        assert result["stats"] == {
            "total_content": 0, "total_clusters": 0, "total_signals": 0,
        }


# ---------------------------------------------------------------------------
# 2. Identifier Provenance
# ---------------------------------------------------------------------------

class TestGetIdentifierProvenance:

    @pytest.mark.asyncio
    async def test_returns_full_chain(self, mock_conn: AsyncMock) -> None:
        """All 5 sections returned with correct structure (asyncio.gather)."""
        fake_content = [{"id": "ci-1", "title": "T", "snippet": "S",
                         "captured_at": "2026-01-01", "platform": "web"}]
        fake_source = [{"id": "s-1", "name": "Src", "platform": "web",
                        "credibility_score": 75.0}]
        fake_cluster = [{"id": "nc-1", "label": "L", "isc": 3, "item_count": 10}]
        fake_signal = [{"id": "sig-1", "status": "new", "fired_at": "2026-01-01"}]
        fake_cross = [{"topic_name": "Other Topic", "mention_count": 2}]

        # asyncio.gather calls all 5 concurrently; side_effect sequences results
        mock_conn.fetch = AsyncMock(
            side_effect=[fake_content, fake_source, fake_cluster,
                         fake_signal, fake_cross],
        )

        from services.api.anveshak.api.db.provenance import get_identifier_provenance
        result = await get_identifier_provenance(
            mock_conn, "9876543210", "topic-001", "org-001",
        )

        assert result["identifier_value"] == "9876543210"
        assert result["topic_id"] == "topic-001"
        assert len(result["content_items"]) == 1
        assert len(result["sources"]) == 1
        assert len(result["clusters"]) == 1
        assert len(result["signals"]) == 1
        assert len(result["cross_topic_appearances"]) == 1

    @pytest.mark.asyncio
    async def test_empty_chain(self, mock_conn: AsyncMock) -> None:
        """Identifier not found returns empty arrays, not errors."""
        mock_conn.fetch = AsyncMock(return_value=[])

        from services.api.anveshak.api.db.provenance import get_identifier_provenance
        result = await get_identifier_provenance(
            mock_conn, "nonexistent", "topic-001", "org-001",
        )

        assert result["content_items"] == []
        assert result["sources"] == []
        assert result["clusters"] == []
        assert result["signals"] == []
        assert result["cross_topic_appearances"] == []


# ---------------------------------------------------------------------------
# 3. Content Provenance
# ---------------------------------------------------------------------------

class TestGetContentProvenance:

    @pytest.mark.asyncio
    async def test_returns_nested_structure(self, mock_conn: AsyncMock) -> None:
        """Content provenance nests source, cluster, identifiers, vision."""
        fake_row = {
            "id": "ci-1", "url": "https://example.com", "clean_text": "text",
            "translated_text": None, "language": "en",
            "captured_at": "2026-01-01", "content_hash": "abc123",
            "credibility_score_at_capture": 80.0,
            "topic_id": "topic-001", "narrative_cluster_id": "nc-1",
            "source_id": "s-1", "source_name": "Src",
            "source_platform": "web", "source_credibility": 75.0,
            "cluster_label": "Cluster X", "cluster_isc": 3,
        }
        fake_identifiers = [
            {"entity_type": "PHONE_IN", "entity_text": "9876543210",
             "confidence": 0.95},
        ]
        fake_vision = [
            {"deepfake_score": 0.12, "deepfake_model": "dire",
             "yolo_detections": json.dumps([{"label": "person"}]),
             "clip_labels": None, "synthetic_probability": 0.05,
             "processed_at": "2026-01-01", "storage_path": "/media/img.jpg",
             "asset_type": "image", "exif_data": None, "phash": 12345},
        ]

        mock_conn.fetchrow = AsyncMock(return_value=fake_row)
        mock_conn.fetch = AsyncMock(
            side_effect=[fake_identifiers, fake_vision],
        )

        from services.api.anveshak.api.db.provenance import get_content_provenance
        result = await get_content_provenance(mock_conn, "ci-1")

        assert result["source"]["name"] == "Src"
        assert result["source"]["credibility_score"] == 75.0
        assert result["cluster"]["label"] == "Cluster X"
        assert result["cluster"]["isc"] == 3
        assert len(result["identifiers"]) == 1
        assert result["identifiers"][0]["entity_type"] == "PHONE_IN"
        assert len(result["vision_results"]) == 1
        assert result["vision_results"][0]["deepfake_score"] == 0.12
        # JSONB double-encoding: yolo_detections parsed from string
        assert result["vision_results"][0]["yolo_detections"] == [{"label": "person"}]

    @pytest.mark.asyncio
    async def test_not_found(self, mock_conn: AsyncMock) -> None:
        """Missing content returns None."""
        mock_conn.fetchrow = AsyncMock(return_value=None)

        from services.api.anveshak.api.db.provenance import get_content_provenance
        result = await get_content_provenance(mock_conn, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_cluster(self, mock_conn: AsyncMock) -> None:
        """Content without cluster sets cluster=None."""
        fake_row = {
            "id": "ci-1", "url": "https://example.com", "clean_text": "text",
            "translated_text": None, "language": "en",
            "captured_at": "2026-01-01", "content_hash": "abc123",
            "credibility_score_at_capture": 80.0,
            "topic_id": "topic-001", "narrative_cluster_id": None,
            "source_id": "s-1", "source_name": "Src",
            "source_platform": "web", "source_credibility": 75.0,
            "cluster_label": None, "cluster_isc": None,
        }
        mock_conn.fetchrow = AsyncMock(return_value=fake_row)
        mock_conn.fetch = AsyncMock(return_value=[])

        from services.api.anveshak.api.db.provenance import get_content_provenance
        result = await get_content_provenance(mock_conn, "ci-1")

        assert result["cluster"] is None
        assert result["identifiers"] == []
        assert result["vision_results"] == []


# ---------------------------------------------------------------------------
# 4. Topic Urgency
# ---------------------------------------------------------------------------

class TestGetTopicUrgency:

    @pytest.mark.asyncio
    async def test_returns_urgency_metrics(self, mock_conn: AsyncMock) -> None:
        """Health rank mapped to label correctly."""
        mock_conn.fetchrow = AsyncMock(return_value={
            "unacked_signal_count": 3,
            "new_content_24h": 42,
            "worst_health_rank": 2,
        })

        from services.api.anveshak.api.db.provenance import get_topic_urgency
        result = await get_topic_urgency(mock_conn, "topic-001")

        assert result["unacked_signal_count"] == 3
        assert result["new_content_24h"] == 42
        assert result["worst_source_health"] == "degraded"

    @pytest.mark.asyncio
    async def test_healthy_default(self, mock_conn: AsyncMock) -> None:
        """Rank 3 = healthy."""
        mock_conn.fetchrow = AsyncMock(return_value={
            "unacked_signal_count": 0,
            "new_content_24h": 0,
            "worst_health_rank": 3,
        })

        from services.api.anveshak.api.db.provenance import get_topic_urgency
        result = await get_topic_urgency(mock_conn, "topic-001")
        assert result["worst_source_health"] == "healthy"

    @pytest.mark.asyncio
    async def test_none_fallback(self, mock_conn: AsyncMock) -> None:
        """No data returns zeros + healthy."""
        mock_conn.fetchrow = AsyncMock(return_value=None)

        from services.api.anveshak.api.db.provenance import get_topic_urgency
        result = await get_topic_urgency(mock_conn, "topic-001")

        assert result["unacked_signal_count"] == 0
        assert result["new_content_24h"] == 0
        assert result["worst_source_health"] == "healthy"


# ---------------------------------------------------------------------------
# 5. SQL Query Correctness
# ---------------------------------------------------------------------------

class TestSQLCorrectness:

    def test_intelligence_signals_scoped_by_topic(self) -> None:
        from services.api.anveshak.api.db.provenance import SQL_INTELLIGENCE_SIGNALS
        assert "topic_id = $1" in SQL_INTELLIGENCE_SIGNALS
        assert "status = 'new'" in SQL_INTELLIGENCE_SIGNALS
        assert "AS fired_at" in SQL_INTELLIGENCE_SIGNALS

    def test_intelligence_clusters_scoped_by_topic(self) -> None:
        from services.api.anveshak.api.db.provenance import SQL_INTELLIGENCE_CLUSTERS
        assert "topic_id = $1" in SQL_INTELLIGENCE_CLUSTERS
        assert "archived_at IS NULL" in SQL_INTELLIGENCE_CLUSTERS

    def test_identifier_cross_topic_scoped_by_org(self) -> None:
        from services.api.anveshak.api.db.provenance import SQL_IDENTIFIER_CROSS_TOPIC
        assert "org_id = $3" in SQL_IDENTIFIER_CROSS_TOPIC
        assert "topic_id != $2" in SQL_IDENTIFIER_CROSS_TOPIC

    def test_content_provenance_joins_source_and_cluster(self) -> None:
        from services.api.anveshak.api.db.provenance import SQL_CONTENT_PROVENANCE
        assert "JOIN sources s" in SQL_CONTENT_PROVENANCE
        assert "JOIN narrative_clusters nc" in SQL_CONTENT_PROVENANCE

    def test_topic_urgency_24h_window(self) -> None:
        from services.api.anveshak.api.db.provenance import SQL_TOPIC_URGENCY
        assert "24 hours" in SQL_TOPIC_URGENCY

    def test_topic_list_has_urgency_fields(self) -> None:
        from services.api.anveshak.api.db.topics import SQL_LIST_TOPICS_BY_ORG
        assert "new_content_24h" in SQL_LIST_TOPICS_BY_ORG
        assert "worst_source_health" in SQL_LIST_TOPICS_BY_ORG

    def test_identifier_locations_use_lower_for_case_insensitive(self) -> None:
        from services.api.anveshak.api.db.provenance import SQL_IDENTIFIER_CONTENT_ITEMS
        assert "LOWER(ee.entity_text) = LOWER($2)" in SQL_IDENTIFIER_CONTENT_ITEMS
