"""Integration test: reporter generate_report full pipeline against real DB.

Tests the complete pipeline: topic → content → report row → generate_report() worker
→ verify generated_at, content_md, source_snapshot are set.

Only Ollama (LLM) is mocked — everything else hits real PostgreSQL.

pytest.mark.integration — requires running Docker Compose (postgres).

Run with:
  uv run --package anveshak-tests pytest tests/integration/test_reporter_e2e.py -v -m integration
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


def _random_embedding(seed: int, dim: int = 384) -> list[float]:
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float64)
    vec /= np.linalg.norm(vec)
    return vec.tolist()


def _make_report_content():
    """Return a mock LLM ReportContent object."""
    rc = MagicMock()
    rc.executive_summary = "UAV activity detected near northern border sector."
    rc.key_findings = ["Finding: drone spotted at 0300h", "Finding: similar to prior incident"]
    rc.recommendations = ["Increase patrol frequency in sector"]
    rc.source_citations = ["https://example.com/source1"]
    rc.confidence_level = 0.75
    rc.labels = {"classification": "OPEN", "domain": "report", "owner_org": "anveshak"}
    return rc


class TestReporterE2E:
    """Full generate_report pipeline against real DB, mocked LLM only."""

    async def test_generate_report_full_pipeline(self, db_pool, make_topic, make_source):
        """Create topic → insert content → create report row → run generate_report → verify."""
        from anveshak.reporter.db import create_report_row, fetch_report
        from anveshak.reporter.worker import generate_report
        from tests.conftest import insert_content_item

        # --- Setup: topic + source + content items ---
        topic_id = await make_topic(name="UAV Border Activity", keywords=["uav", "drone"])
        source_id = await make_source(name="Reuters", platform="rss", credibility_score=80.0)

        emb = _random_embedding(seed=100)
        await insert_content_item(
            db_pool, topic_id, source_id,
            "UAV spotted near Line of Actual Control at 0300 hours on patrol route.",
            embedding=emb,
        )
        await insert_content_item(
            db_pool, topic_id, source_id,
            "Indian Army reports increased drone activity along northern border sectors.",
            embedding=_random_embedding(seed=101),
        )

        # --- Create report row ---
        report_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        await create_report_row(
            db_pool,
            report_id=report_id,
            topic_id=topic_id,
            report_type="intelligence_brief",
            time_window_start=now - timedelta(hours=72),
            time_window_end=now,
            credibility_min=30.0,
        )

        # Verify report exists but not yet generated
        report_before = await fetch_report(db_pool, report_id)
        assert report_before is not None
        assert report_before.get("generated_at") is None

        # --- Build worker context (real DB, mocked LLM) ---
        rc = _make_report_content()
        settings = MagicMock()
        settings.rag_top_k = 10
        settings.rag_max_context_tokens = 4000
        settings.ollama_model = "qwen2:7b"
        settings.ollama_host = "http://ollama:11434"
        settings.ollama_report_timeout_s = 300
        settings.ollama_retry_max = 2

        ctx = {"db": db_pool, "settings": settings}

        with patch("anveshak.reporter.worker.call_ollama_with_retry", new_callable=AsyncMock) as mock_llm, \
             patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock) as mock_embed, \
             patch("anveshak.reporter.worker.call_ollama_for_bluf", new_callable=AsyncMock) as mock_bluf:
            mock_llm.return_value = rc
            mock_embed.return_value = emb  # use same embedding as query vector
            mock_bluf.return_value = None  # trigger fallback BLUF

            await generate_report(ctx, report_id)

        # --- Verify report is fully generated ---
        report_after = await fetch_report(db_pool, report_id)
        assert report_after is not None
        assert report_after.get("generated_at") is not None, "generated_at must be set"
        assert report_after.get("content_md") is not None, "content_md must be set"
        assert "Bottom Line Up Front" in report_after["content_md"]
        assert report_after.get("confidence_score") == 0.0  # fallback BLUF (no LLM)
        assert report_after.get("content_item_count") == 2
        assert report_after.get("source_snapshot") is not None

    async def test_generate_report_idempotent_on_replay(self, db_pool, make_topic, make_source):
        """Running generate_report twice on same report_id is a no-op (idempotent)."""
        from anveshak.reporter.db import create_report_row, fetch_report
        from anveshak.reporter.worker import generate_report
        from tests.conftest import insert_content_item

        topic_id = await make_topic(name="Idempotency Test")
        source_id = await make_source(name="NDTV", platform="web", credibility_score=70.0)

        emb = _random_embedding(seed=200)
        await insert_content_item(
            db_pool, topic_id, source_id,
            "Test article for idempotency verification in reporter pipeline.",
            embedding=emb,
        )

        report_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        await create_report_row(
            db_pool,
            report_id=report_id,
            topic_id=topic_id,
            report_type="research_summary",
            time_window_start=now - timedelta(hours=24),
            time_window_end=now,
            credibility_min=30.0,
        )

        rc = _make_report_content()
        settings = MagicMock()
        settings.rag_top_k = 10
        settings.rag_max_context_tokens = 4000
        settings.ollama_model = "qwen2:7b"
        settings.ollama_host = "http://ollama:11434"
        settings.ollama_report_timeout_s = 300
        settings.ollama_retry_max = 2

        ctx = {"db": db_pool, "settings": settings}

        with patch("anveshak.reporter.worker.call_ollama_with_retry", new_callable=AsyncMock) as mock_llm, \
             patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock) as mock_embed, \
             patch("anveshak.reporter.worker.call_ollama_for_bluf", new_callable=AsyncMock) as mock_bluf:
            mock_llm.return_value = rc
            mock_embed.return_value = emb
            mock_bluf.return_value = None  # trigger fallback BLUF

            # First run — should generate
            await generate_report(ctx, report_id)
            report_v1 = await fetch_report(db_pool, report_id)
            generated_at_v1 = report_v1["generated_at"]

            # Second run — should be no-op (idempotent via generated_at IS NULL guard)
            await generate_report(ctx, report_id)
            report_v2 = await fetch_report(db_pool, report_id)

            # generated_at must not change (CLAUDE.md rule 4: reports are immutable)
            assert report_v2["generated_at"] == generated_at_v1
