"""Unit tests for reporter worker — generate_report pipeline and helpers.

pytest.mark.unit — mocks all DB and LLM calls, no external dependencies.
Tests real business logic: idempotency, failure paths, markdown building.
"""
from __future__ import annotations

import json
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(settings=None):
    """Build a fake ARQ context dict with mocked DB pool and settings."""
    s = settings or _make_settings()
    return {"db": AsyncMock(), "settings": s}


def _make_settings():
    s = MagicMock()
    s.rag_top_k = 10
    s.rag_max_context_tokens = 4000
    s.ollama_model = "mistral:7b"
    s.ollama_host = "http://ollama:11434"
    s.ollama_report_timeout_s = 30
    s.ollama_retry_max = 2
    s.source_warning_lookback_days = 30
    s.topic_relevance_threshold = 0.35
    return s


def _make_report_row(topic_id="topic-1", report_type="intelligence_brief"):
    return {
        "id": "report-1",
        "topic_id": topic_id,
        "report_type": report_type,
        "credibility_min_filter": 30.0,
    }


def _make_topic_row(name="UAV Activity", keywords=None):
    return {
        "id": "topic-1",
        "name": name,
        "keywords": keywords or ["UAV", "drone"],
    }


def _make_report_content():
    """Return a mock ReportContent object with all required fields."""
    rc = MagicMock()
    rc.executive_summary = "Summary of UAV activity near northern border."
    rc.key_findings = ["Finding 1", "Finding 2"]
    rc.recommendations = ["Recommendation 1"]
    rc.source_citations = ["https://example.com/source1"]
    rc.confidence_level = 0.85
    return rc


def _make_chunk(source_id="src-1"):
    return {
        "id": "chunk-1",
        "source_id": source_id,
        "clean_text": "UAV detected near border.",
        "url": "https://example.com",
    }


# ---------------------------------------------------------------------------
# generate_report tests
# ---------------------------------------------------------------------------

class TestGenerateReport:

    @pytest.mark.asyncio
    async def test_generate_report_not_found(self):
        """Report not in DB -> returns early, no crash."""
        ctx = _make_ctx()

        with patch("anveshak.reporter.worker.db") as mock_db:
            mock_db.fetch_report = AsyncMock(return_value=None)

            from anveshak.reporter.worker import generate_report
            await generate_report(ctx, "nonexistent-id")

            mock_db.fetch_report.assert_awaited_once_with(ctx["db"], "nonexistent-id")
            mock_db.set_report_failed.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_report_topic_not_found(self):
        """Topic deleted after report created -> set_report_failed called."""
        ctx = _make_ctx()

        with patch("anveshak.reporter.worker.db") as mock_db:
            mock_db.fetch_report = AsyncMock(return_value=_make_report_row())
            mock_db.fetch_topic = AsyncMock(return_value=None)
            mock_db.set_report_failed = AsyncMock()

            from anveshak.reporter.worker import generate_report
            await generate_report(ctx, "report-1")

            mock_db.set_report_failed.assert_awaited_once()
            args = mock_db.set_report_failed.call_args
            assert "not found" in args[1].get("error_message", args[0][-1]).lower() or \
                   "deleted" in args[1].get("error_message", args[0][-1]).lower()

    @pytest.mark.asyncio
    async def test_generate_report_no_rag_chunks(self):
        """No content available -> set_report_failed with helpful message."""
        ctx = _make_ctx()

        with patch("anveshak.reporter.worker.db") as mock_db, \
             patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock) as mock_embed:
            mock_db.fetch_report = AsyncMock(return_value=_make_report_row())
            mock_db.fetch_topic = AsyncMock(return_value=_make_topic_row())
            mock_db.fetch_rag_chunks = AsyncMock(return_value=[])
            mock_db.set_report_failed = AsyncMock()
            mock_embed.return_value = [0.1] * 384

            from anveshak.reporter.worker import generate_report
            await generate_report(ctx, "report-1")

            mock_db.set_report_failed.assert_awaited_once()
            error_msg = mock_db.set_report_failed.call_args[0][-1]
            assert "no scraped content" in error_msg.lower() or "sources" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_generate_report_llm_failure(self):
        """call_ollama_with_retry returns None -> set_report_failed."""
        ctx = _make_ctx()
        chunks = [_make_chunk()]

        with patch("anveshak.reporter.worker.db") as mock_db, \
             patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock) as mock_embed, \
             patch("anveshak.reporter.worker.assemble_context") as mock_ctx, \
             patch("anveshak.reporter.worker.render_prompt") as mock_prompt, \
             patch("anveshak.reporter.worker.call_ollama_with_retry", new_callable=AsyncMock) as mock_llm:
            mock_db.fetch_report = AsyncMock(return_value=_make_report_row())
            mock_db.fetch_topic = AsyncMock(return_value=_make_topic_row())
            mock_db.fetch_rag_chunks = AsyncMock(return_value=chunks)
            mock_db.fetch_topic_identifiers = AsyncMock(return_value=[])
            mock_db.fetch_topic_template_matches = AsyncMock(return_value=[])
            mock_db.set_report_failed = AsyncMock()
            mock_embed.return_value = [0.1] * 384
            mock_ctx.return_value = ("context text", 3, "2026-01-01 to 2026-01-07")
            mock_prompt.return_value = "prompt"
            mock_llm.return_value = None

            from anveshak.reporter.worker import generate_report
            await generate_report(ctx, "report-1")

            mock_db.set_report_failed.assert_awaited_once()
            error_msg = mock_db.set_report_failed.call_args[0][-1]
            assert "llm" in error_msg.lower() or "ollama" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_generate_report_idempotent(self):
        """set_report_generated returns False -> logs 'already_generated', no crash."""
        ctx = _make_ctx()
        chunks = [_make_chunk()]
        rc = _make_report_content()

        with patch("anveshak.reporter.worker.db") as mock_db, \
             patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock) as mock_embed, \
             patch("anveshak.reporter.worker.assemble_context") as mock_ctx, \
             patch("anveshak.reporter.worker.render_prompt") as mock_prompt, \
             patch("anveshak.reporter.worker.call_ollama_with_retry", new_callable=AsyncMock) as mock_llm, \
             patch("anveshak.reporter.worker.geocode_locations") as mock_geo, \
             patch("anveshak.reporter.worker.build_geojson") as mock_geojson, \
             patch("anveshak.reporter.worker.extract_locations_from_text") as mock_extract:
            mock_db.fetch_report = AsyncMock(return_value=_make_report_row())
            mock_db.fetch_topic = AsyncMock(return_value=_make_topic_row())
            mock_db.fetch_rag_chunks = AsyncMock(return_value=chunks)
            mock_db.fetch_sources_for_snapshot = AsyncMock(return_value={})
            mock_db.fetch_topic_location_entities = AsyncMock(return_value=[])
            mock_db.fetch_topic_identifiers = AsyncMock(return_value=[])
            mock_db.fetch_topic_template_matches = AsyncMock(return_value=[])
            mock_db.set_report_generated = AsyncMock(return_value=False)  # already generated
            mock_db.update_job_status = AsyncMock()
            mock_embed.return_value = [0.1] * 384
            mock_ctx.return_value = ("context", 3, "2026-01-01 to 2026-01-07")
            mock_prompt.return_value = "prompt"
            mock_llm.return_value = rc
            mock_geo.return_value = []
            mock_geojson.return_value = {"type": "FeatureCollection", "features": []}
            mock_extract.return_value = []

            from anveshak.reporter.worker import generate_report
            # Should not crash
            await generate_report(ctx, "report-1")

            # set_report_generated was called but returned False
            mock_db.set_report_generated.assert_awaited_once()
            # update_job_status should NOT be called when already generated
            mock_db.update_job_status.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_generate_report_happy_path(self):
        """Full pipeline success: set_report_generated called with correct params."""
        ctx = _make_ctx()
        chunks = [_make_chunk("src-1"), _make_chunk("src-2")]
        rc = _make_report_content()

        with patch("anveshak.reporter.worker.db") as mock_db, \
             patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock) as mock_embed, \
             patch("anveshak.reporter.worker.assemble_context") as mock_ctx, \
             patch("anveshak.reporter.worker.render_prompt") as mock_prompt, \
             patch("anveshak.reporter.worker.call_ollama_with_retry", new_callable=AsyncMock) as mock_llm, \
             patch("anveshak.reporter.worker.geocode_locations") as mock_geo, \
             patch("anveshak.reporter.worker.build_geojson") as mock_geojson, \
             patch("anveshak.reporter.worker.extract_locations_from_text") as mock_extract:
            mock_db.fetch_report = AsyncMock(return_value=_make_report_row())
            mock_db.fetch_topic = AsyncMock(return_value=_make_topic_row())
            mock_db.fetch_rag_chunks = AsyncMock(return_value=chunks)
            mock_db.fetch_sources_for_snapshot = AsyncMock(return_value={"src-1": {"credibility_score": 80}})
            mock_db.fetch_topic_location_entities = AsyncMock(return_value=["Delhi"])
            mock_db.fetch_topic_identifiers = AsyncMock(return_value=[])
            mock_db.fetch_topic_template_matches = AsyncMock(return_value=[])
            mock_db.set_report_generated = AsyncMock(return_value=True)
            mock_db.update_job_status = AsyncMock()
            mock_embed.return_value = [0.1] * 384
            mock_ctx.return_value = ("context", 3, "2026-01-01 to 2026-01-07")
            mock_prompt.return_value = "prompt"
            mock_llm.return_value = rc
            mock_geo.return_value = [{"name": "Delhi", "lat": 28.6, "lon": 77.2}]
            mock_geojson.return_value = {"type": "FeatureCollection", "features": []}
            mock_extract.return_value = []

            from anveshak.reporter.worker import generate_report
            await generate_report(ctx, "report-1")

            mock_db.set_report_generated.assert_awaited_once()
            call_kwargs = mock_db.set_report_generated.call_args[1]
            assert call_kwargs["report_id"] == "report-1"
            assert call_kwargs["confidence_score"] == 0.85
            assert call_kwargs["content_item_count"] == 2
            assert "## Executive Summary" in call_kwargs["content_md"]
            mock_db.update_job_status.assert_awaited_once_with(
                ctx["db"], "report-1", "complete"
            )


# ---------------------------------------------------------------------------
# check_source_warnings tests
# ---------------------------------------------------------------------------

class TestCheckSourceWarnings:

    @pytest.mark.asyncio
    async def test_snapshot_as_string(self):
        """source_snapshot stored as JSON string -> parsed correctly."""
        ctx = _make_ctx()
        snapshot_dict = {"src-1": {"credibility_score": 90.0}}
        report = {
            "id": "report-1",
            "source_snapshot": json.dumps(snapshot_dict),
        }

        with patch("anveshak.reporter.worker.db") as mock_db:
            mock_db.fetch_reports_for_warning_check = AsyncMock(return_value=[report])
            mock_db.fetch_sources_for_snapshot = AsyncMock(
                return_value={"src-1": {"credibility_score": 90.0, "name": "Source One"}}
            )
            mock_db.insert_source_warning = AsyncMock()

            from anveshak.reporter.worker import check_source_warnings
            await check_source_warnings(ctx)

            # No downgrade — same score, so no warning
            mock_db.insert_source_warning.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_snapshot_as_dict(self):
        """source_snapshot already a dict -> works directly."""
        ctx = _make_ctx()
        report = {
            "id": "report-1",
            "source_snapshot": {"src-1": {"credibility_score": 90.0}},
        }

        with patch("anveshak.reporter.worker.db") as mock_db:
            mock_db.fetch_reports_for_warning_check = AsyncMock(return_value=[report])
            mock_db.fetch_sources_for_snapshot = AsyncMock(
                return_value={"src-1": {"credibility_score": 90.0, "name": "Source One"}}
            )
            mock_db.insert_source_warning = AsyncMock()

            from anveshak.reporter.worker import check_source_warnings
            await check_source_warnings(ctx)

            # No downgrade
            mock_db.insert_source_warning.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_detects_downgrade(self):
        """old_score > new_score -> insert_source_warning called."""
        ctx = _make_ctx()
        report = {
            "id": "report-1",
            "source_snapshot": {"src-1": {"credibility_score": 90.0}},
        }

        with patch("anveshak.reporter.worker.db") as mock_db:
            mock_db.fetch_reports_for_warning_check = AsyncMock(return_value=[report])
            mock_db.fetch_sources_for_snapshot = AsyncMock(
                return_value={"src-1": {"credibility_score": 60.0, "name": "Source One"}}
            )
            mock_db.insert_source_warning = AsyncMock()

            from anveshak.reporter.worker import check_source_warnings
            await check_source_warnings(ctx)

            mock_db.insert_source_warning.assert_awaited_once()
            call_kwargs = mock_db.insert_source_warning.call_args[1]
            assert call_kwargs["report_id"] == "report-1"
            assert call_kwargs["source_id"] == "src-1"
            assert call_kwargs["old_score"] == 90.0
            assert call_kwargs["new_score"] == 60.0


# ---------------------------------------------------------------------------
# check_scheduled_reports tests
# ---------------------------------------------------------------------------

def _make_pool_with_topics(topics: list[dict]):
    """Build a mock asyncpg pool that returns topics from acquire→fetch."""
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=topics)
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_conn),
        __aexit__=AsyncMock(return_value=False),
    ))
    return mock_pool


class TestCheckScheduledReports:

    def _make_topic_record(
        self, *,
        topic_id="topic-1",
        cron_expr="0 0 * * 0",
        scheduled_type=None,
        last_report_at=None,
        credibility_min=30.0,
    ):
        return {
            "id": topic_id,
            "name": "Test Topic",
            "keywords": ["test"],
            "scheduled_report_cron": cron_expr,
            "scheduled_report_type": scheduled_type,
            "credibility_min": credibility_min,
            "last_report_at": last_report_at,
        }

    def _make_sched_ctx(self, topics):
        pool = _make_pool_with_topics(topics)
        arq_pool = AsyncMock()
        return {"db": pool, "settings": _make_settings(), "arq_pool": arq_pool}, arq_pool

    @pytest.mark.asyncio
    async def test_valid_cron_fires_and_enqueues(self):
        """Cron that has fired creates report row + enqueues ARQ job."""
        topic = self._make_topic_record(
            cron_expr="* * * * *",
            last_report_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        ctx, arq_pool = self._make_sched_ctx([topic])

        with patch("anveshak.reporter.db.create_report_row", new_callable=AsyncMock) as mock_create:
            from anveshak.reporter.worker import check_scheduled_reports
            await check_scheduled_reports(ctx)

            mock_create.assert_awaited_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["topic_id"] == "topic-1"
            assert call_kwargs["report_type"] == "intelligence_brief"
            arq_pool.enqueue_job.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_cron_skipped(self):
        """Invalid cron expression is logged and skipped."""
        topic = self._make_topic_record(cron_expr="INVALID CRON")
        ctx, _ = self._make_sched_ctx([topic])

        with patch("anveshak.reporter.db.create_report_row", new_callable=AsyncMock) as mock_create:
            from anveshak.reporter.worker import check_scheduled_reports
            await check_scheduled_reports(ctx)
            mock_create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_null_last_report_fires_immediately(self):
        """First-ever report (NULL last_report_at) fires immediately."""
        topic = self._make_topic_record(cron_expr="* * * * *", last_report_at=None)
        ctx, _ = self._make_sched_ctx([topic])

        with patch("anveshak.reporter.db.create_report_row", new_callable=AsyncMock) as mock_create:
            from anveshak.reporter.worker import check_scheduled_reports
            await check_scheduled_reports(ctx)
            mock_create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_scheduled_type_used_when_set(self):
        """scheduled_report_type overrides default intelligence_brief."""
        topic = self._make_topic_record(
            cron_expr="* * * * *",
            scheduled_type="weekly_digest",
            last_report_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        ctx, _ = self._make_sched_ctx([topic])

        with patch("anveshak.reporter.db.create_report_row", new_callable=AsyncMock) as mock_create:
            from anveshak.reporter.worker import check_scheduled_reports
            await check_scheduled_reports(ctx)
            assert mock_create.call_args[1]["report_type"] == "weekly_digest"

    @pytest.mark.asyncio
    async def test_time_window_is_7_days(self):
        """Scheduled reports use 168-hour (7-day) time window."""
        topic = self._make_topic_record(
            cron_expr="* * * * *",
            last_report_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        ctx, _ = self._make_sched_ctx([topic])

        with patch("anveshak.reporter.db.create_report_row", new_callable=AsyncMock) as mock_create:
            from anveshak.reporter.worker import check_scheduled_reports
            await check_scheduled_reports(ctx)
            kw = mock_create.call_args[1]
            delta = kw["time_window_end"] - kw["time_window_start"]
            assert delta.total_seconds() == 168 * 3600

    @pytest.mark.asyncio
    async def test_no_topics_no_crash(self):
        """Empty topic list → nothing enqueued, no crash."""
        ctx, _ = self._make_sched_ctx([])

        with patch("anveshak.reporter.db.create_report_row", new_callable=AsyncMock) as mock_create:
            from anveshak.reporter.worker import check_scheduled_reports
            await check_scheduled_reports(ctx)
            mock_create.assert_not_awaited()


# ---------------------------------------------------------------------------
# _build_content_md tests
# ---------------------------------------------------------------------------

class TestBuildContentMd:

    def test_format(self):
        """Markdown output has correct sections and content."""
        from anveshak.reporter.worker import _build_content_md

        rc = _make_report_content()
        md = _build_content_md(rc)

        assert "## Executive Summary" in md
        assert rc.executive_summary in md
        assert "## Key Findings" in md
        assert "- Finding 1" in md
        assert "- Finding 2" in md
        assert "## Recommendations" in md
        assert "- Recommendation 1" in md
        assert "## Source Citations" in md
        assert "- https://example.com/source1" in md
