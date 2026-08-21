"""Unit tests for reporter prompt templates and RAG context assembly.

Tests:
  - render_prompt produces prompts with grounding rules, few-shot, XML markers
  - assemble_context includes credibility scores and dates in chunk headers
  - assemble_context returns source_count and date_range metadata
  - Token budget is respected
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# render_prompt
# ---------------------------------------------------------------------------


class TestRenderPrompt:
    def test_intelligence_brief_contains_grounding_rules(self):
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt(
            "intelligence_brief", "Naval Ops", ["navy", "patrol"], "some context"
        )
        assert "STRICT RULES:" in prompt
        assert "ONLY use facts" in prompt

    def test_prompt_contains_few_shot_example(self):
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt("intelligence_brief", "Test", ["kw"], "ctx")
        assert "EXAMPLE (for format reference only" in prompt
        assert "END OF EXAMPLE" in prompt

    def test_prompt_contains_xml_boundary_markers(self):
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt("research_summary", "My Topic", ["kw1"], "ctx")
        assert "<topic>My Topic</topic>" in prompt
        assert "<keywords>kw1</keywords>" in prompt
        assert "<context>" in prompt

    def test_prompt_contains_json_schema(self):
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt("intelligence_brief", "T", [], "c")
        assert '"executive_summary"' in prompt
        assert '"confidence_level"' in prompt
        assert '"labels"' in prompt

    def test_weekly_digest_has_correct_role(self):
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt("weekly_digest", "T", [], "c")
        assert "OSINT analyst" in prompt

    def test_source_count_and_date_range_injected(self):
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt(
            "intelligence_brief",
            "T",
            [],
            "c",
            source_count=5,
            date_range="2026-04-10 to 2026-04-15",
        )
        assert "5 sources" in prompt
        assert "2026-04-10 to 2026-04-15" in prompt

    def test_no_metadata_when_source_count_zero(self):
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt("intelligence_brief", "T", [], "c", source_count=0)
        assert "context_metadata" not in prompt

    def test_invalid_report_type_raises(self):
        """render_prompt must reject invalid report_type with KeyError."""
        from anveshak.reporter.prompt_templates import render_prompt

        with pytest.raises(KeyError):
            render_prompt("nonexistent_type", "T", [], "c")

    def test_invalid_report_type_rejected_by_request_model(self):
        """GenerateReportRequest must reject invalid report_type via Pydantic."""
        from anveshak.reporter.main import GenerateReportRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GenerateReportRequest(topic_id="t1", report_type="bogus_type")

    def test_valid_report_types_accepted_by_request_model(self):
        """All three valid report types must be accepted."""
        from anveshak.reporter.main import GenerateReportRequest

        for rt in ("intelligence_brief", "research_summary", "weekly_digest"):
            req = GenerateReportRequest(topic_id="t1", report_type=rt)
            assert req.report_type == rt

    def test_empty_keywords_shows_none(self):
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt("intelligence_brief", "T", [], "c")
        assert "<keywords>(none)</keywords>" in prompt


# ---------------------------------------------------------------------------
# assemble_context
# ---------------------------------------------------------------------------


class TestAssembleContext:
    def _make_chunk(
        self,
        url: str = "https://example.com",
        text: str = "Some content",
        cred: float = 65.0,
        captured_at: datetime | None = None,
    ) -> dict:
        return {
            "url": url,
            "clean_text": text,
            "credibility_score_at_capture": cred,
            "captured_at": captured_at or datetime(2026, 4, 15, tzinfo=UTC),
            "source_id": "src-1",
        }

    def test_empty_chunks_returns_empty(self):
        from anveshak.reporter.rag import assemble_context

        ctx, count, dr = assemble_context([], 4000)
        assert ctx == ""
        assert count == 0
        assert dr == ""

    def test_context_includes_credibility_score(self):
        from anveshak.reporter.rag import assemble_context

        chunks = [self._make_chunk(cred=72.5)]
        ctx, count, dr = assemble_context(chunks, 4000)
        assert "Credibility: 72.5" in ctx
        assert count == 1

    def test_context_includes_date(self):
        from anveshak.reporter.rag import assemble_context

        chunks = [self._make_chunk(captured_at=datetime(2026, 4, 10, tzinfo=UTC))]
        ctx, _, dr = assemble_context(chunks, 4000)
        assert "2026-04-10" in ctx
        assert dr == "2026-04-10"

    def test_date_range_spans_multiple_dates(self):
        from anveshak.reporter.rag import assemble_context

        chunks = [
            self._make_chunk(captured_at=datetime(2026, 4, 10, tzinfo=UTC)),
            self._make_chunk(url="https://b.com", captured_at=datetime(2026, 4, 15, tzinfo=UTC)),
        ]
        ctx, count, dr = assemble_context(chunks, 4000)
        assert count == 2
        assert dr == "2026-04-10 to 2026-04-15"

    def test_token_budget_truncates(self):
        from anveshak.reporter.rag import assemble_context

        # Each chunk header + 30 chars text ≈ 100 chars → ~25 tokens.
        # Budget of 30 tokens allows ~1 chunk.
        chunks = [
            self._make_chunk(text="A" * 30),
            self._make_chunk(url="https://b.com", text="B" * 30),
        ]
        ctx, count, _ = assemble_context(chunks, max_tokens=30)
        assert count == 1
        assert "AAAAAA" in ctx
        assert "BBBBBB" not in ctx

    def test_zero_max_tokens_returns_empty(self):
        from anveshak.reporter.rag import assemble_context

        ctx, count, dr = assemble_context([self._make_chunk()], 0)
        assert ctx == ""
        assert count == 0
