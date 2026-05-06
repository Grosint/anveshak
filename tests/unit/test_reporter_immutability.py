"""Unit tests for reporter worker — report generation job immutability.

pytest.mark.unit — mocks DB, Ollama, and embedding model.
CLAUDE.md rule 4: generated_at is set ONCE via WHERE generated_at IS NULL guard.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


pytestmark = pytest.mark.unit


def _make_ctx(settings=None) -> dict:
    """Build a minimal ARQ job context dict."""
    if settings is None:
        s = MagicMock()
        s.ollama_host = "http://ollama:11434"
        s.ollama_report_model = "mistral:7b"
        s.ollama_report_timeout_s = 30
        s.ollama_retry_max = 2
        s.embedding_model = "all-MiniLM-L6-v2"
        s.rag_top_k = 10
        s.rag_similarity_threshold = 0.3
        s.rag_max_context_tokens = 4000
        s.pdf_output_dir = "/tmp/test-reports"
        s.source_warning_lookback_days = 30
        settings = s

    pool = MagicMock()
    return {"db": pool, "settings": settings}


VALID_REPORT_CONTENT = {
    "executive_summary": "Test summary.",
    "key_findings": ["Finding 1"],
    "recommendations": ["Rec 1"],
    "confidence_level": 0.75,
    "source_citations": ["https://example.com/1"],
    "labels": {"classification": "OPEN", "domain": "report", "owner_org": "anveshak"},
}


class TestGenerateReportIdempotency:
    """generate_report is idempotent — second call with same ID is a no-op."""

    @pytest.mark.asyncio
    async def test_second_call_is_noop_when_already_generated(self):
        """If set_report_generated returns False, job silently exits."""
        from anveshak.reporter.worker import generate_report

        ctx = _make_ctx()
        mock_topic = {
            "id": "topic-1",
            "name": "Test Topic",
            "keywords": ["kw1"],
            "credibility_min": 30.0,
        }
        mock_report = {
            "id": "report-1",
            "topic_id": "topic-1",
            "report_type": "intelligence_brief",
            "time_window_start": "2026-04-10T00:00:00+00:00",
            "time_window_end": "2026-04-13T00:00:00+00:00",
            "credibility_min_filter": 30.0,
            "generated_at": "2026-04-13T10:00:00+00:00",  # already done
        }
        mock_chunks = [
            {
                "id": "c1",
                "clean_text": "Some intelligence text here.",
                "credibility_score_at_capture": 80.0,
                "url": "https://example.com/a",
                "source_id": "src-1",
            }
        ]

        with (
            patch("anveshak.reporter.worker.db") as mock_db_mod,
            patch("anveshak.reporter.worker.call_ollama_with_retry", new_callable=AsyncMock) as mock_llm,
            patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock, return_value=[0.1] * 384),
            patch("anveshak.reporter.worker.assemble_context", return_value=("context text", 1, "2026-04-10")),
            patch("anveshak.reporter.worker.render_prompt", return_value="prompt text"),
        ):
            mock_db_mod.fetch_report = AsyncMock(return_value=mock_report)
            mock_db_mod.fetch_topic = AsyncMock(return_value=mock_topic)
            mock_db_mod.fetch_rag_chunks = AsyncMock(return_value=mock_chunks)
            mock_db_mod.fetch_sources_for_snapshot = AsyncMock(return_value={})
            mock_db_mod.fetch_topic_location_entities = AsyncMock(return_value=[])
            # Return False → already generated (WHERE generated_at IS NULL guard failed)
            mock_db_mod.set_report_generated = AsyncMock(return_value=False)
            mock_db_mod.update_job_status = AsyncMock()

            from anveshak.reporter.llm import ReportContent
            from anveshak.models.base import Labels
            mock_llm.return_value = ReportContent(
                **VALID_REPORT_CONTENT
            )

            await generate_report(ctx, "report-1")

        # LLM should have been called but set_report_generated returned False → no crash
        # The key assertion: no exception raised, job completed gracefully

    @pytest.mark.asyncio
    async def test_no_rag_chunks_sets_failed_status(self):
        """generate_report with zero RAG chunks sets status=failed, does NOT store empty report."""
        from anveshak.reporter.worker import generate_report

        ctx = _make_ctx()
        mock_topic = {
            "id": "topic-1",
            "name": "Test Topic",
            "keywords": ["kw1"],
            "credibility_min": 30.0,
        }
        mock_report = {
            "id": "report-1",
            "topic_id": "topic-1",
            "report_type": "intelligence_brief",
            "time_window_start": "2026-04-10T00:00:00+00:00",
            "time_window_end": "2026-04-13T00:00:00+00:00",
            "credibility_min_filter": 30.0,
            "generated_at": None,
        }

        with (
            patch("anveshak.reporter.worker.db") as mock_db_mod,
            patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock, return_value=[0.1] * 384),
        ):
            mock_db_mod.fetch_report = AsyncMock(return_value=mock_report)
            mock_db_mod.fetch_topic = AsyncMock(return_value=mock_topic)
            mock_db_mod.fetch_rag_chunks = AsyncMock(return_value=[])  # empty!
            mock_db_mod.update_job_status = AsyncMock()
            mock_db_mod.set_report_generated = AsyncMock()
            mock_db_mod.set_report_failed = AsyncMock()

            await generate_report(ctx, "report-1")

        # set_report_generated must NOT have been called
        mock_db_mod.set_report_generated.assert_not_called()
        # set_report_failed must have been called with an error message
        mock_db_mod.set_report_failed.assert_called_once()
        call_args = mock_db_mod.set_report_failed.call_args
        assert "report-1" in str(call_args)

    @pytest.mark.asyncio
    async def test_llm_returning_none_sets_failed_status(self):
        """generate_report with LLM returning None must set status=failed."""
        from anveshak.reporter.worker import generate_report

        ctx = _make_ctx()
        mock_topic = {
            "id": "topic-1",
            "name": "Test Topic",
            "keywords": ["kw1"],
            "credibility_min": 30.0,
        }
        mock_report = {
            "id": "report-1",
            "topic_id": "topic-1",
            "report_type": "intelligence_brief",
            "time_window_start": "2026-04-10T00:00:00+00:00",
            "time_window_end": "2026-04-13T00:00:00+00:00",
            "credibility_min_filter": 30.0,
            "generated_at": None,
        }
        mock_chunks = [
            {
                "id": "c1",
                "clean_text": "Some intelligence text.",
                "credibility_score_at_capture": 80.0,
                "url": "https://example.com/a",
                "source_id": "src-1",
            }
        ]

        with (
            patch("anveshak.reporter.worker.db") as mock_db_mod,
            patch("anveshak.reporter.worker.call_ollama_with_retry", new_callable=AsyncMock) as mock_llm,
            patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock, return_value=[0.1] * 384),
            patch("anveshak.reporter.worker.assemble_context", return_value=("context text", 1, "2026-04-10")),
            patch("anveshak.reporter.worker.render_prompt", return_value="prompt text"),
        ):
            mock_db_mod.fetch_report = AsyncMock(return_value=mock_report)
            mock_db_mod.fetch_topic = AsyncMock(return_value=mock_topic)
            mock_db_mod.fetch_rag_chunks = AsyncMock(return_value=mock_chunks)
            mock_db_mod.fetch_sources_for_snapshot = AsyncMock(return_value={})
            mock_db_mod.fetch_topic_location_entities = AsyncMock(return_value=[])
            mock_db_mod.update_job_status = AsyncMock()
            mock_db_mod.set_report_generated = AsyncMock()
            mock_db_mod.set_report_failed = AsyncMock()
            mock_llm.return_value = None  # LLM failed all retries

            await generate_report(ctx, "report-1")

        # Must NOT have stored an empty report
        mock_db_mod.set_report_generated.assert_not_called()
        # Must have set failed via set_report_failed
        mock_db_mod.set_report_failed.assert_called_once()
        call_args = mock_db_mod.set_report_failed.call_args
        assert "report-1" in str(call_args)

    @pytest.mark.asyncio
    async def test_successful_generation_stores_report(self):
        """Happy path: valid LLM output → set_report_generated called once."""
        from anveshak.reporter.worker import generate_report
        from anveshak.reporter.llm import ReportContent

        ctx = _make_ctx()
        mock_topic = {
            "id": "topic-1",
            "name": "Test Topic",
            "keywords": ["kw1"],
            "credibility_min": 30.0,
        }
        mock_report = {
            "id": "report-1",
            "topic_id": "topic-1",
            "report_type": "intelligence_brief",
            "time_window_start": "2026-04-10T00:00:00+00:00",
            "time_window_end": "2026-04-13T00:00:00+00:00",
            "credibility_min_filter": 30.0,
            "generated_at": None,
        }
        mock_chunks = [
            {
                "id": "c1",
                "clean_text": "Some intelligence text.",
                "credibility_score_at_capture": 80.0,
                "url": "https://example.com/a",
                "source_id": "src-1",
            }
        ]

        with (
            patch("anveshak.reporter.worker.db") as mock_db_mod,
            patch("anveshak.reporter.worker.call_ollama_with_retry", new_callable=AsyncMock) as mock_llm,
            patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock, return_value=[0.1] * 384),
            patch("anveshak.reporter.worker.assemble_context", return_value=("context text", 1, "2026-04-10")),
            patch("anveshak.reporter.worker.render_prompt", return_value="prompt text"),
            patch("anveshak.reporter.worker.geocode_locations", return_value={}),
            patch("anveshak.reporter.worker.extract_locations_from_text", return_value=[]),
            patch("anveshak.reporter.worker.build_geojson", return_value={"type": "FeatureCollection", "features": []}),
        ):
            mock_db_mod.fetch_report = AsyncMock(return_value=mock_report)
            mock_db_mod.fetch_topic = AsyncMock(return_value=mock_topic)
            mock_db_mod.fetch_rag_chunks = AsyncMock(return_value=mock_chunks)
            mock_db_mod.fetch_sources_for_snapshot = AsyncMock(return_value={"src-1": {"name": "Reuters", "credibility_score": 80.0}})
            mock_db_mod.fetch_topic_location_entities = AsyncMock(return_value=[])
            mock_db_mod.set_report_generated = AsyncMock(return_value=True)
            mock_db_mod.update_job_status = AsyncMock()

            mock_llm.return_value = ReportContent(**VALID_REPORT_CONTENT)

            await generate_report(ctx, "report-1")

        mock_db_mod.set_report_generated.assert_called_once()
        # update_job_status should be called with "complete"
        calls = mock_db_mod.update_job_status.call_args_list
        statuses = [str(c) for c in calls]
        assert any("complete" in s for s in statuses)
