"""Unit tests for Engine C configuration settings.

Verifies that:
  1. identifier_extraction_enabled setting exists (default True)
  2. template_matching_enabled setting exists (default True)
  3. identifier_cluster_interval_s setting exists (default 300)
  4. Settings are used as guards in jobs.py and scheduler.py
  5. Compose environment block includes Engine C vars

pytest.mark.unit -- no external dependencies.
"""

from __future__ import annotations

import pytest

_MOD = "anveshak.analyst.settings"


_JOBS = "anveshak.analyst.jobs"


@pytest.mark.unit
class TestEngineCSettingsExist:
    """AnalystSettings must have Engine C configuration fields."""

    def test_identifier_extraction_enabled(self):
        from anveshak.analyst.settings import settings

        assert hasattr(settings, "identifier_extraction_enabled"), (
            "Missing identifier_extraction_enabled setting"
        )
        assert settings.identifier_extraction_enabled is True, "Default should be True"

    def test_template_matching_enabled(self):
        from anveshak.analyst.settings import settings

        assert hasattr(settings, "template_matching_enabled"), (
            "Missing template_matching_enabled setting"
        )
        assert settings.template_matching_enabled is True, "Default should be True"

    def test_identifier_cluster_interval_s(self):
        from anveshak.analyst.settings import settings

        assert hasattr(settings, "identifier_cluster_interval_s"), (
            "Missing identifier_cluster_interval_s setting"
        )
        assert settings.identifier_cluster_interval_s == 300, "Default should be 300 (5 minutes)"


@pytest.mark.unit
class TestEngineCSettingsGuardExtraction:
    """analyse_content must skip extraction when identifier_extraction_enabled=False."""

    @pytest.mark.asyncio
    async def test_extraction_skipped_when_disabled(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        row = {
            "id": "ci-1",
            "clean_text": "Call +91 9876543210 for guaranteed returns",
            "topic_id": "topic-1",
            "topic_name": "Test",
            "topic_keywords": ["test"],
            "topic_relevance_threshold": None,
            "platform": "web",
        }

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=row)
        conn.execute = AsyncMock()
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)
        acq = AsyncMock()
        acq.__aenter__ = AsyncMock(return_value=conn)
        acq.__aexit__ = AsyncMock(return_value=False)
        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=acq)

        with (
            patch(f"{_JOBS}.is_quality_content", return_value=(True, "passed")),
            patch(f"{_JOBS}.detect_language", return_value="en"),
            patch(f"{_JOBS}.needs_translation", return_value=False),
            patch(f"{_JOBS}.is_model_loaded", return_value=True),
            patch(f"{_JOBS}.parse_entities", return_value=[]),
            patch(f"{_JOBS}.encode_text", return_value=[0.1] * 384),
            patch(f"{_JOBS}.build_topic_query_embedding", return_value=[0.2] * 384),
            patch(f"{_JOBS}.compute_topic_relevance", return_value=0.5),
            patch(
                f"{_JOBS}.analyse_sentiment",
                return_value=type(
                    "S", (), {"compound": 0.0, "positive": 0.0, "negative": 0.0, "neutral": 1.0}
                )(),
            ),
            patch(f"{_JOBS}.extract_keywords", return_value=[]),
            patch(f"{_JOBS}.compute_entity_minhash", return_value=None),
            patch(f"{_JOBS}.extract_identifiers") as mock_extract,
            patch(f"{_JOBS}.match_templates") as mock_match,
            patch(f"{_JOBS}.settings") as mock_settings,
            patch(f"{_JOBS}.analyst_nlp_jobs_total"),
            patch(f"{_JOBS}.analyst_nlp_duration_seconds"),
            patch(f"{_JOBS}.analyst_relevance_score"),
            patch(f"{_JOBS}.analyst_embedding_completed_total"),
        ):
            mock_settings.identifier_extraction_enabled = False
            mock_settings.template_matching_enabled = False
            mock_settings.translation_enabled = False
            mock_settings.minhash_num_perm = 128

            from anveshak.analyst.jobs import analyse_content

            await analyse_content({"db_pool": pool}, "ci-1")

        mock_extract.assert_not_called()
        mock_match.assert_not_called()


@pytest.mark.unit
class TestEngineCComposeVars:
    """Compose environment must include Engine C vars."""

    def test_compose_has_engine_c_vars(self):
        from pathlib import Path

        compose_path = Path(__file__).parents[2] / "infra" / "compose.yml"
        if not compose_path.exists():
            pytest.skip("compose.yml not found")
        text = compose_path.read_text().lower()
        assert "identifier_extraction_enabled" in text, (
            "compose.yml missing IDENTIFIER_EXTRACTION_ENABLED"
        )
        assert "template_matching_enabled" in text, "compose.yml missing TEMPLATE_MATCHING_ENABLED"
        assert "identifier_cluster_interval_s" in text, (
            "compose.yml missing IDENTIFIER_CLUSTER_INTERVAL_S"
        )
