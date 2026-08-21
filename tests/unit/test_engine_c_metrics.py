"""Unit tests for Engine C Prometheus metrics.

pytest.mark.unit -- no external dependencies.
"""

from __future__ import annotations

import pytest

_JOBS = "anveshak.analyst.jobs"


@pytest.mark.unit
class TestEngineCMetricsExist:
    """Analyst metrics module must export Engine C counters."""

    def test_identifiers_extracted_total(self):
        from anveshak.analyst.metrics import analyst_identifiers_extracted_total

        # Counter with no labels — just needs to exist and be incrementable
        analyst_identifiers_extracted_total.inc(0)

    def test_template_matches_total(self):
        from anveshak.analyst.metrics import analyst_template_matches_total

        analyst_template_matches_total.labels(template_name="test").inc(0)

    def test_identifier_clusters_total(self):
        from anveshak.analyst.metrics import analyst_identifier_clusters_total

        analyst_identifier_clusters_total.inc(0)


@pytest.mark.unit
class TestEngineCMetricsIncrementedInJobs:
    """analyse_content must increment Engine C metrics when identifiers/templates found."""

    @pytest.mark.asyncio
    async def test_identifier_counter_incremented(self):
        from dataclasses import dataclass
        from unittest.mock import AsyncMock, MagicMock, patch

        @dataclass
        class FakeIdMatch:
            identifier_type: str
            raw_value: str
            normalized_value: str
            confidence: float

        row = {
            "id": "ci-1",
            "clean_text": "Call +91 9876543210",
            "topic_id": "topic-1",
            "topic_name": "Test",
            "topic_keywords": ["test"],
            "topic_relevance_threshold": None,
            "platform": "telegram",
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

        fake_ids = [
            FakeIdMatch("PHONE_IN", "+91 9876543210", "9876543210", 0.95),
        ]

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
            patch(f"{_JOBS}.extract_identifiers", return_value=fake_ids),
            patch(f"{_JOBS}.match_templates", return_value=None),
            patch(f"{_JOBS}.analyst_nlp_jobs_total"),
            patch(f"{_JOBS}.analyst_nlp_duration_seconds"),
            patch(f"{_JOBS}.analyst_relevance_score"),
            patch(f"{_JOBS}.analyst_embedding_completed_total"),
            patch(f"{_JOBS}.analyst_identifiers_extracted_total") as mock_id_counter,
        ):
            from anveshak.analyst.jobs import analyse_content

            await analyse_content({"db_pool": pool}, "ci-1")

        mock_id_counter.inc.assert_called_once_with(1)
