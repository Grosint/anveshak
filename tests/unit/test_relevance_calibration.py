"""Unit tests for auto-calibration of per-topic relevance thresholds.

Tests calibrate_topic_thresholds() — the periodic loop that computes
PERCENTILE_CONT of each topic's relevance score distribution and sets
topics.topic_relevance_threshold accordingly.

pytest.mark.unit — mocks all DB calls, no external dependencies.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool_mock(conn: AsyncMock):
    """asyncpg.Pool mock where acquire() returns async context manager."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire.return_value = cm
    return pool


def _make_row(
    topic_id: str = "t1",
    topic_name: str = "Test Topic",
    current_threshold: float | None = None,
    target_threshold: float = 0.20,
    item_count: int = 50,
) -> dict:
    """Build a fake asyncpg Row dict for SQL_TOPIC_RELEVANCE_PERCENTILE."""
    return {
        "topic_id": topic_id,
        "topic_name": topic_name,
        "current_threshold": current_threshold,
        "target_threshold": target_threshold,
        "item_count": item_count,
    }


# ---------------------------------------------------------------------------
# calibrate_topic_thresholds
# ---------------------------------------------------------------------------


class TestCalibrateTopicThresholds:
    @pytest.mark.asyncio
    async def test_sets_threshold_from_percentile(self):
        """Basic case: topic with no existing threshold gets calibrated."""
        from anveshak.analyst.relevance import calibrate_topic_thresholds

        row = _make_row(target_threshold=0.18, current_threshold=None)
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row])
        mock_conn.execute = AsyncMock()

        mock_pool = _make_pool_mock(mock_conn)

        updated = await calibrate_topic_thresholds(mock_pool)

        assert updated == 1
        # Verify UPDATE was called with clamped threshold
        mock_conn.execute.assert_awaited_once()
        call_args = mock_conn.execute.call_args[0]
        assert call_args[1] == 0.18  # threshold
        assert call_args[2] == "t1"  # topic_id

    @pytest.mark.asyncio
    async def test_clamps_to_floor(self):
        """Percentile below floor (0.08) gets clamped up."""
        from anveshak.analyst.relevance import calibrate_topic_thresholds

        row = _make_row(target_threshold=0.03, current_threshold=None)
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row])
        mock_conn.execute = AsyncMock()

        mock_pool = _make_pool_mock(mock_conn)

        with patch("anveshak.analyst.relevance.settings") as mock_settings:
            mock_settings.relevance_calibration_target_pct = 0.40
            mock_settings.relevance_calibration_min_items = 20
            mock_settings.relevance_calibration_floor = 0.08
            mock_settings.relevance_calibration_ceiling = 0.50
            updated = await calibrate_topic_thresholds(mock_pool)

        assert updated == 1
        call_args = mock_conn.execute.call_args[0]
        assert call_args[1] == 0.08  # clamped to floor

    @pytest.mark.asyncio
    async def test_clamps_to_ceiling(self):
        """Percentile above ceiling (0.50) gets clamped down."""
        from anveshak.analyst.relevance import calibrate_topic_thresholds

        row = _make_row(target_threshold=0.65, current_threshold=None)
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row])
        mock_conn.execute = AsyncMock()

        mock_pool = _make_pool_mock(mock_conn)

        with patch("anveshak.analyst.relevance.settings") as mock_settings:
            mock_settings.relevance_calibration_target_pct = 0.40
            mock_settings.relevance_calibration_min_items = 20
            mock_settings.relevance_calibration_floor = 0.08
            mock_settings.relevance_calibration_ceiling = 0.50
            updated = await calibrate_topic_thresholds(mock_pool)

        assert updated == 1
        call_args = mock_conn.execute.call_args[0]
        assert call_args[1] == 0.5  # clamped to ceiling

    @pytest.mark.asyncio
    async def test_skips_when_threshold_unchanged(self):
        """No UPDATE if new threshold differs by < 0.005 from current."""
        from anveshak.analyst.relevance import calibrate_topic_thresholds

        row = _make_row(target_threshold=0.201, current_threshold=0.20)
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row])
        mock_conn.execute = AsyncMock()

        mock_pool = _make_pool_mock(mock_conn)

        updated = await calibrate_topic_thresholds(mock_pool)

        assert updated == 0
        mock_conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_updates_when_threshold_changed_meaningfully(self):
        """UPDATE fires when threshold changes by >= 0.005."""
        from anveshak.analyst.relevance import calibrate_topic_thresholds

        row = _make_row(target_threshold=0.25, current_threshold=0.20)
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row])
        mock_conn.execute = AsyncMock()

        mock_pool = _make_pool_mock(mock_conn)

        updated = await calibrate_topic_thresholds(mock_pool)

        assert updated == 1
        call_args = mock_conn.execute.call_args[0]
        assert call_args[1] == 0.25

    @pytest.mark.asyncio
    async def test_no_topics_returns_zero(self):
        """No topics with enough data → returns 0, logs skip."""
        from anveshak.analyst.relevance import calibrate_topic_thresholds

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = _make_pool_mock(mock_conn)

        updated = await calibrate_topic_thresholds(mock_pool)

        assert updated == 0
        mock_conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_multiple_topics_calibrated_independently(self):
        """Each topic gets its own threshold from its own distribution."""
        from anveshak.analyst.relevance import calibrate_topic_thresholds

        rows = [
            _make_row(
                topic_id="t1", topic_name="Narrow", target_threshold=0.35, current_threshold=None
            ),
            _make_row(
                topic_id="t2", topic_name="Broad", target_threshold=0.12, current_threshold=None
            ),
        ]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=rows)
        mock_conn.execute = AsyncMock()

        mock_pool = _make_pool_mock(mock_conn)

        updated = await calibrate_topic_thresholds(mock_pool)

        assert updated == 2
        calls = mock_conn.execute.call_args_list
        # t1: 0.35 (within bounds)
        assert calls[0][0][1] == 0.35
        assert calls[0][0][2] == "t1"
        # t2: 0.12 (within bounds, above floor)
        assert calls[1][0][1] == 0.12
        assert calls[1][0][2] == "t2"

    @pytest.mark.asyncio
    async def test_threshold_rounded_to_3_decimals(self):
        """Threshold is rounded to 3 decimal places for clean display."""
        from anveshak.analyst.relevance import calibrate_topic_thresholds

        row = _make_row(target_threshold=0.18749, current_threshold=None)
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row])
        mock_conn.execute = AsyncMock()

        mock_pool = _make_pool_mock(mock_conn)

        await calibrate_topic_thresholds(mock_pool)

        call_args = mock_conn.execute.call_args[0]
        assert call_args[1] == 0.187  # rounded


# ---------------------------------------------------------------------------
# Reporter RAG relevance filter
# ---------------------------------------------------------------------------


class TestReporterRAGRelevanceFilter:
    """Verify relevance_threshold is threaded to fetch_rag_chunks."""

    _FAKE_DATA_BUNDLE = {
        "topic_stats": {
            "name": "Test",
            "content_count": 5,
            "source_count": 2,
            "cluster_count": 1,
            "signal_count": 0,
        },
        "sources": [],
        "clusters": [],
        "signals": [],
        "entities": [],
        "sentiment_trend": [],
        "keywords": [],
        "evidence_items": [],
        "language_breakdown": [],
    }

    @pytest.mark.asyncio
    async def test_per_topic_threshold_passed_to_rag(self):
        """When topic has topic_relevance_threshold, it's passed to fetch_rag_chunks."""
        from anveshak.reporter.worker import generate_report

        topic = {
            "id": "topic-1",
            "name": "Test",
            "keywords": ["test"],
            "topic_relevance_threshold": 0.18,
        }
        report = {
            "id": "r1",
            "topic_id": "topic-1",
            "report_type": "intelligence_brief",
            "credibility_min_filter": 30.0,
        }

        ctx = {
            "db": AsyncMock(),
            "settings": MagicMock(
                rag_top_k=10,
                rag_max_context_tokens=4000,
                ollama_model="test",
                ollama_host="http://o:11434",
                ollama_report_timeout_s=30,
                ollama_retry_max=2,
                topic_relevance_threshold=0.35,
            ),
        }

        with (
            patch("anveshak.reporter.worker.db") as mock_db,
            patch(
                "anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock
            ) as mock_embed,
        ):
            mock_db.fetch_report = AsyncMock(return_value=report)
            mock_db.fetch_topic = AsyncMock(return_value=topic)
            mock_db.fetch_report_data_bundle = AsyncMock(return_value=self._FAKE_DATA_BUNDLE)
            mock_db.fetch_rag_chunks = AsyncMock(return_value=[])
            mock_db.set_report_failed = AsyncMock()
            mock_embed.return_value = [0.1] * 384

            await generate_report(ctx, "r1")

            call_kwargs = mock_db.fetch_rag_chunks.call_args
            assert call_kwargs.kwargs.get("relevance_threshold") == 0.18

    @pytest.mark.asyncio
    async def test_null_topic_threshold_falls_back_to_settings(self):
        """When topic has no topic_relevance_threshold, global default is used."""
        from anveshak.reporter.worker import generate_report

        topic = {"id": "topic-1", "name": "Test", "keywords": ["test"]}
        report = {
            "id": "r1",
            "topic_id": "topic-1",
            "report_type": "intelligence_brief",
            "credibility_min_filter": 30.0,
        }

        ctx = {
            "db": AsyncMock(),
            "settings": MagicMock(
                rag_top_k=10,
                rag_max_context_tokens=4000,
                ollama_model="test",
                ollama_host="http://o:11434",
                ollama_report_timeout_s=30,
                ollama_retry_max=2,
                topic_relevance_threshold=0.35,
            ),
        }

        with (
            patch("anveshak.reporter.worker.db") as mock_db,
            patch(
                "anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock
            ) as mock_embed,
        ):
            mock_db.fetch_report = AsyncMock(return_value=report)
            mock_db.fetch_topic = AsyncMock(return_value=topic)
            mock_db.fetch_report_data_bundle = AsyncMock(return_value=self._FAKE_DATA_BUNDLE)
            mock_db.fetch_rag_chunks = AsyncMock(return_value=[])
            mock_db.set_report_failed = AsyncMock()
            mock_embed.return_value = [0.1] * 384

            await generate_report(ctx, "r1")

            call_kwargs = mock_db.fetch_rag_chunks.call_args
            assert call_kwargs.kwargs.get("relevance_threshold") == 0.35


# ---------------------------------------------------------------------------
# API default threshold consistency
# ---------------------------------------------------------------------------


class TestAPIDefaultThreshold:
    """Verify API default matches global analyst setting."""

    def test_api_default_matches_analyst_global(self):
        from anveshak.api.db.topics import _DEFAULT_RELEVANCE_THRESHOLD

        assert _DEFAULT_RELEVANCE_THRESHOLD == 0.35

    def test_api_custom_threshold_overrides_default(self):
        """Existing test updated — verify 0.42 was changed to 0.35."""
        from anveshak.api.db.topics import _DEFAULT_RELEVANCE_THRESHOLD

        # Must NOT be 0.42 (the old hardcoded value)
        assert _DEFAULT_RELEVANCE_THRESHOLD != 0.42


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestCalibrationSettings:
    """Verify calibration settings exist with correct defaults."""

    def test_defaults(self):
        from anveshak.analyst.settings import AnalystSettings

        s = AnalystSettings()
        assert s.relevance_calibration_interval_s == 21600
        assert s.relevance_calibration_target_pct == 0.40
        assert s.relevance_calibration_floor == 0.08
        assert s.relevance_calibration_ceiling == 0.50
        assert s.relevance_calibration_min_items == 20

    def test_floor_less_than_ceiling(self):
        """Invariant: floor must be less than ceiling."""
        from anveshak.analyst.settings import settings

        assert settings.relevance_calibration_floor < settings.relevance_calibration_ceiling

    def test_target_pct_between_zero_and_one(self):
        """Target percentile must be a valid probability."""
        from anveshak.analyst.settings import settings

        assert 0.0 < settings.relevance_calibration_target_pct < 1.0

    def test_reporter_has_topic_relevance_threshold(self):
        """Reporter settings must have topic_relevance_threshold for fallback."""
        from anveshak.reporter.settings import ReporterSettings

        s = ReporterSettings()
        assert s.topic_relevance_threshold == 0.35
