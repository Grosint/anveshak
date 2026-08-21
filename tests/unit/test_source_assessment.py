"""Unit tests for Source Assessment feature — Phase 0 (deterministic stats).

TDD RED phase: these tests define the contract before implementation.
pytest.mark.unit — mocks DB, no external dependencies.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Model tests — Pydantic strict mode + mandatory labels
# ---------------------------------------------------------------------------


class TestSourceAssessmentModels:
    """SourceAssessment and SourceStats must enforce strict=True + labels."""

    def test_source_stats_requires_labels(self):
        """SourceStats without labels must raise ValidationError."""
        from anveshak.models.assessment import SourceStats

        with pytest.raises(Exception):
            SourceStats(
                total_posts=10,
                avg_posts_per_day=1.5,
                engagement={"likes": 0, "comments": 0, "shares": 0, "views": 0},
                language_breakdown=[],
                volume_timeline=[],
                top_entities=[],
                identifier_overlap=[],
                cluster_participation=[],
                sentiment_distribution={"negative": 0, "neutral": 0, "positive": 0},
                credibility_trajectory=[],
                # labels intentionally omitted
            )

    def test_source_stats_valid(self):
        """SourceStats with all required fields passes validation."""
        from anveshak.models.assessment import SourceStats
        from anveshak.models.base import Labels

        stats = SourceStats(
            total_posts=42,
            first_post=datetime.now(timezone.utc),
            last_post=datetime.now(timezone.utc),
            avg_posts_per_day=3.5,
            engagement={"likes": 100, "comments": 20, "shares": 5, "views": 500},
            language_breakdown=[{"language": "en", "count": 40, "pct": 95.2}],
            volume_timeline=[{"date": "2026-06-01", "count": 5}],
            top_entities=[{"entity_text": "Nagaland", "entity_type": "GPE", "count": 15}],
            identifier_overlap=[],
            cluster_participation=[{"cluster_id": "c1", "label": "test", "item_count": 3}],
            sentiment_distribution={"negative": 5, "neutral": 30, "positive": 7},
            credibility_trajectory=[],
            labels=Labels(),
        )
        assert stats.total_posts == 42
        assert stats.labels.classification == "OPEN"

    def test_source_assessment_requires_labels(self):
        """SourceAssessment inherits AuditedModel — labels is mandatory."""
        from anveshak.models.assessment import SourceAssessment

        with pytest.raises(Exception):
            SourceAssessment(
                topic_id="t1",
                source_id="s1",
                org_id="org1",
                time_window_start=datetime.now(timezone.utc),
                time_window_end=datetime.now(timezone.utc),
                # labels intentionally omitted
            )

    def test_source_assessment_valid(self):
        """SourceAssessment with all required fields passes validation."""
        from anveshak.models.assessment import SourceAssessment
        from anveshak.models.base import Labels

        now = datetime.now(timezone.utc)
        assessment = SourceAssessment(
            topic_id="t1",
            source_id="s1",
            org_id="org1",
            time_window_start=now - timedelta(days=30),
            time_window_end=now,
            labels=Labels(domain="assessment"),
        )
        assert assessment.topic_id == "t1"
        assert assessment.generated_at is None  # not yet generated
        assert assessment.brief_md is None  # Phase 2

    def test_source_assessment_immutability_fields(self):
        """generated_at starts as None, can be set once."""
        from anveshak.models.assessment import SourceAssessment
        from anveshak.models.base import Labels

        now = datetime.now(timezone.utc)
        assessment = SourceAssessment(
            topic_id="t1",
            source_id="s1",
            org_id="org1",
            time_window_start=now - timedelta(days=30),
            time_window_end=now,
            labels=Labels(domain="assessment"),
        )
        assert assessment.generated_at is None
        assert assessment.content_item_count == 0
        assert assessment.source_snapshot == {}


# ---------------------------------------------------------------------------
# DB layer tests — SQL query functions
# ---------------------------------------------------------------------------


class TestAssessmentDB:
    """Test assessment DB layer functions."""

    @pytest.mark.asyncio
    async def test_insert_assessment(self):
        """insert_assessment stores a new assessment row."""
        from anveshak.api.db.assessments import insert_assessment

        conn = AsyncMock()
        conn.execute = AsyncMock()

        assessment_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        await insert_assessment(
            conn,
            assessment_id=assessment_id,
            topic_id="topic-1",
            source_id="source-1",
            org_id="org-1",
            time_window_start=now - timedelta(days=30),
            time_window_end=now,
            stats_json="{}",
            content_item_count=42,
            source_snapshot_json="{}",
            now=now,
            labels_json='{"classification":"OPEN","domain":"assessment","owner_org":"anveshak"}',
        )
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_assessment(self):
        """fetch_assessment returns dict or None."""
        from anveshak.api.db.assessments import fetch_assessment

        # asyncpg Record acts like a dict — use a real dict wrapped in a
        # MagicMock that supports dict() conversion via items().
        mock_row = MagicMock()
        mock_row.items.return_value = [
            ("id", "a1"),
            ("topic_id", "t1"),
            ("source_id", "s1"),
            ("org_id", "org1"),
            ("stats", "{}"),
            ("generated_at", None),
        ]
        mock_row.keys.return_value = [
            "id",
            "topic_id",
            "source_id",
            "org_id",
            "stats",
            "generated_at",
        ]
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await fetch_assessment(conn, "a1")
        conn.fetchrow.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_assessments(self):
        """list_assessments returns a list of dicts."""
        from anveshak.api.db.assessments import list_assessments

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])

        result = await list_assessments(conn, "topic-1", "source-1")
        assert result == []
        conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_compute_source_stats(self):
        """compute_source_stats runs all SQL queries via gather."""
        from anveshak.api.db.assessments import compute_source_stats

        conn = AsyncMock()
        # Mock all fetchrow/fetch calls
        conn.fetchrow = AsyncMock(return_value=None)
        conn.fetch = AsyncMock(return_value=[])

        now = datetime.now(timezone.utc)
        stats = await compute_source_stats(
            conn,
            topic_id="t1",
            source_id="s1",
            org_id="org1",
            time_start=now - timedelta(days=30),
            time_end=now,
        )

        # Must return a dict with all expected keys
        assert "total_posts" in stats
        assert "engagement" in stats
        assert "language_breakdown" in stats
        assert "volume_timeline" in stats
        assert "top_entities" in stats
        assert "identifier_overlap" in stats
        assert "cluster_participation" in stats
        assert "sentiment_distribution" in stats
        assert "credibility_trajectory" in stats


# ---------------------------------------------------------------------------
# Route tests — endpoint behavior
# ---------------------------------------------------------------------------


class TestAssessmentRoutes:
    """Test assessment API route logic."""

    @pytest.mark.asyncio
    async def test_create_assessment_verifies_topic_access(self):
        """POST /assessment must call verify_topic_access."""
        from anveshak.api.routes.assessments import create_assessment

        mock_db = AsyncMock()
        mock_user = {"sub": "user-1", "org_id": "org-1", "role": "analyst"}
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        with (
            patch("anveshak.api.routes.assessments.topics_db") as mock_topics,
            patch("anveshak.api.routes.assessments.sources_db") as mock_sources,
            patch("anveshak.api.routes.assessments.assessments_db") as mock_assess_db,
            patch("anveshak.api.routes.assessments.audit_db") as mock_audit,
        ):
            mock_topics.verify_topic_access = AsyncMock()
            mock_sources.verify_source_access = AsyncMock()
            mock_sources.topic_source_exists = AsyncMock(return_value=True)
            mock_assess_db.count_source_content = AsyncMock(return_value=10)
            mock_assess_db.compute_source_stats = AsyncMock(
                return_value={
                    "total_posts": 10,
                    "engagement": {"likes": 0, "comments": 0, "shares": 0, "views": 0},
                    "language_breakdown": [],
                    "volume_timeline": [],
                    "top_entities": [],
                    "identifier_overlap": [],
                    "cluster_participation": [],
                    "sentiment_distribution": {"negative": 0, "neutral": 0, "positive": 0},
                    "credibility_trajectory": [],
                }
            )
            mock_assess_db.insert_assessment = AsyncMock()
            mock_assess_db.get_source_snapshot = AsyncMock(return_value={})
            mock_audit.log_action = AsyncMock()

            from anveshak.api.routes.assessments import CreateAssessmentRequest

            req = CreateAssessmentRequest()

            await create_assessment(
                topic_id="t1",
                source_id="s1",
                req=req,
                request=mock_request,
                db=mock_db,
                user=mock_user,
            )

            mock_topics.verify_topic_access.assert_called_once()
            mock_sources.verify_source_access.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_assessment_rejects_insufficient_data(self):
        """POST /assessment with < 5 content items returns 400."""
        from anveshak.api.routes.assessments import CreateAssessmentRequest, create_assessment
        from fastapi import HTTPException

        mock_db = AsyncMock()
        mock_user = {"sub": "user-1", "org_id": "org-1", "role": "analyst"}
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        with (
            patch("anveshak.api.routes.assessments.topics_db") as mock_topics,
            patch("anveshak.api.routes.assessments.sources_db") as mock_sources,
            patch("anveshak.api.routes.assessments.assessments_db") as mock_assess_db,
        ):
            mock_topics.verify_topic_access = AsyncMock()
            mock_sources.verify_source_access = AsyncMock()
            mock_sources.topic_source_exists = AsyncMock(return_value=True)
            mock_assess_db.count_source_content = AsyncMock(return_value=3)  # < 5

            req = CreateAssessmentRequest()

            with pytest.raises(HTTPException) as exc_info:
                await create_assessment(
                    topic_id="t1",
                    source_id="s1",
                    req=req,
                    request=mock_request,
                    db=mock_db,
                    user=mock_user,
                )
            assert exc_info.value.status_code == 400
            assert "Insufficient" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_assessment_rejects_unlinked_source(self):
        """POST /assessment for source not linked to topic returns 400."""
        from anveshak.api.routes.assessments import CreateAssessmentRequest, create_assessment
        from fastapi import HTTPException

        mock_db = AsyncMock()
        mock_user = {"sub": "user-1", "org_id": "org-1", "role": "analyst"}
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        with (
            patch("anveshak.api.routes.assessments.topics_db") as mock_topics,
            patch("anveshak.api.routes.assessments.sources_db") as mock_sources,
        ):
            mock_topics.verify_topic_access = AsyncMock()
            mock_sources.verify_source_access = AsyncMock()
            mock_sources.topic_source_exists = AsyncMock(return_value=False)

            req = CreateAssessmentRequest()

            with pytest.raises(HTTPException) as exc_info:
                await create_assessment(
                    topic_id="t1",
                    source_id="s1",
                    req=req,
                    request=mock_request,
                    db=mock_db,
                    user=mock_user,
                )
            assert exc_info.value.status_code == 400
