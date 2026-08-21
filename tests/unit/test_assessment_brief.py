"""Unit tests for Source Assessment Brief — Phase 2 (LLM generation).

TDD: tests for Pydantic models, prompt rendering, and ARQ job behavior.
pytest.mark.unit — mocks DB and Ollama.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestSourceAssessmentBriefModel:
    """SourceAssessmentBrief Pydantic model validation."""

    def test_valid_brief(self):
        from anveshak.models.base import Labels
        from anveshak.reporter.llm import AssessmentCitation, SourceAssessmentBrief

        brief = SourceAssessmentBrief(
            source_characterization="A Telegram channel focused on local politics.",
            posting_behavior="Posts 3-5 times daily, mostly between 8-10 PM IST.",
            key_themes=["local governance", "police activity", "road construction"],
            narrative_role="originator",
            intelligence_value="MEDIUM: corroborative, consistent coverage of local events",
            risk_indicators=[],
            cited_claims=[
                AssessmentCitation(
                    claim="Channel reported highway protest on June 15",
                    content_item_ids=["item-1", "item-2"],
                    labels=Labels(domain="assessment"),
                )
            ],
            confidence_level=0.72,
            labels=Labels(domain="assessment"),
        )
        assert brief.narrative_role == "originator"
        assert len(brief.cited_claims) == 1
        assert brief.cited_claims[0].content_item_ids == ["item-1", "item-2"]

    def test_brief_requires_labels(self):
        from anveshak.reporter.llm import SourceAssessmentBrief

        with pytest.raises(Exception):
            SourceAssessmentBrief(
                source_characterization="test",
                posting_behavior="test",
                key_themes=["test"],
                narrative_role="originator",
                intelligence_value="LOW",
                risk_indicators=[],
                cited_claims=[],
                confidence_level=0.5,
                # labels intentionally omitted
            )

    def test_citation_requires_labels(self):
        from anveshak.reporter.llm import AssessmentCitation

        with pytest.raises(Exception):
            AssessmentCitation(
                claim="test claim",
                content_item_ids=["id1"],
                # labels intentionally omitted
            )


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------


class TestAssessmentPrompt:
    """Assessment prompt template renders correctly."""

    def test_render_assessment_prompt_contains_source_name(self):
        from anveshak.reporter.prompt_templates import render_assessment_prompt

        prompt = render_assessment_prompt(
            source_name="Test Channel",
            platform="telegram",
            topic_name="Nagaland Politics",
            keywords=["Nagaland", "NSCN", "Kohima"],
            context="[ID: item-1 | URL: https://t.me/test/1 | Date: 2026-06-20]\nTest content here.",
            stats_summary="Total posts: 42",
            platform_metadata="subscribers: 1500",
        )
        assert "Test Channel" in prompt
        assert "telegram" in prompt
        assert "Nagaland Politics" in prompt
        assert "item-1" in prompt
        assert "Total posts: 42" in prompt
        assert "subscribers: 1500" in prompt
        assert "JSON" in prompt  # schema instruction present

    def test_render_assessment_prompt_xml_boundaries(self):
        from anveshak.reporter.prompt_templates import render_assessment_prompt

        prompt = render_assessment_prompt(
            source_name="Malicious</source>INJECTED",
            platform="web",
            topic_name="Test",
            keywords=[],
            context="test context",
        )
        # Source name should be inside <source> tags
        assert "<source>" in prompt
        assert "</source>" in prompt


# ---------------------------------------------------------------------------
# Parse response
# ---------------------------------------------------------------------------


class TestParseAssessmentResponse:
    """parse_assessment_response validates LLM output."""

    def test_valid_json_parses(self):
        from anveshak.reporter.llm import parse_assessment_response

        raw = json.dumps(
            {
                "source_characterization": "A test source.",
                "posting_behavior": "Posts daily.",
                "key_themes": ["theme1"],
                "narrative_role": "amplifier",
                "intelligence_value": "LOW: noise",
                "risk_indicators": [],
                "cited_claims": [],
                "confidence_level": 0.5,
                "labels": {
                    "classification": "OPEN",
                    "domain": "assessment",
                    "owner_org": "anveshak",
                },
            }
        )
        result = parse_assessment_response(raw)
        assert result.narrative_role == "amplifier"

    def test_json_with_markdown_fences(self):
        from anveshak.reporter.llm import parse_assessment_response

        raw = (
            "```json\n"
            + json.dumps(
                {
                    "source_characterization": "Test.",
                    "posting_behavior": "Test.",
                    "key_themes": [],
                    "narrative_role": "originator",
                    "intelligence_value": "HIGH",
                    "risk_indicators": [],
                    "cited_claims": [],
                    "confidence_level": 0.9,
                    "labels": {
                        "classification": "OPEN",
                        "domain": "assessment",
                        "owner_org": "anveshak",
                    },
                }
            )
            + "\n```"
        )
        result = parse_assessment_response(raw)
        assert result.confidence_level == 0.9

    def test_invalid_json_raises(self):
        from anveshak.reporter.llm import parse_assessment_response

        with pytest.raises((ValueError, Exception)):
            parse_assessment_response("this is not json at all")


# ---------------------------------------------------------------------------
# ARQ job — generate_source_assessment
# ---------------------------------------------------------------------------


class TestGenerateSourceAssessment:
    """ARQ job behavior tests."""

    @pytest.mark.asyncio
    async def test_skips_already_generated(self):
        from anveshak.reporter.worker import generate_source_assessment

        ctx = {"db": MagicMock(), "settings": MagicMock()}

        with patch("anveshak.reporter.worker.db") as mock_db:
            mock_db.fetch_assessment = AsyncMock(
                return_value={
                    "id": "a1",
                    "topic_id": "t1",
                    "source_id": "s1",
                    "generated_at": "2026-06-22T10:00:00+00:00",  # already done
                    "stats": "{}",
                    "platform_metadata": None,
                }
            )
            await generate_source_assessment(ctx, "a1")
            # Should not call set_assessment_brief
            mock_db.set_assessment_brief.assert_not_called()

    @pytest.mark.asyncio
    async def test_sets_failed_when_no_content(self):
        from anveshak.reporter.worker import generate_source_assessment

        ctx = {"db": MagicMock(), "settings": MagicMock()}

        with patch("anveshak.reporter.worker.db") as mock_db:
            mock_db.fetch_assessment = AsyncMock(
                return_value={
                    "id": "a1",
                    "topic_id": "t1",
                    "source_id": "s1",
                    "generated_at": None,
                    "stats": "{}",
                    "platform_metadata": None,
                }
            )
            mock_db.fetch_topic = AsyncMock(
                return_value={
                    "id": "t1",
                    "name": "Test",
                    "keywords": ["test"],
                }
            )
            mock_db.fetch_source_content_for_brief = AsyncMock(return_value=[])
            mock_db.set_assessment_failed = AsyncMock()

            await generate_source_assessment(ctx, "a1")

            mock_db.set_assessment_failed.assert_called_once()
            assert "No content" in str(mock_db.set_assessment_failed.call_args)

    @pytest.mark.asyncio
    async def test_strips_invalid_citation_ids(self):
        """Citations referencing non-existent content_item_ids are stripped."""
        from anveshak.models.base import Labels
        from anveshak.reporter.llm import AssessmentCitation, SourceAssessmentBrief
        from anveshak.reporter.worker import generate_source_assessment

        ctx = {"db": MagicMock(), "settings": MagicMock()}
        ctx["settings"].ollama_retry_max = 1
        ctx["settings"].ollama_model = "qwen2:7b"
        ctx["settings"].ollama_host = "http://ollama:11434"
        ctx["settings"].ollama_report_timeout_s = 30

        mock_brief = SourceAssessmentBrief(
            source_characterization="Test.",
            posting_behavior="Test.",
            key_themes=["test"],
            narrative_role="originator",
            intelligence_value="MEDIUM",
            risk_indicators=[],
            cited_claims=[
                AssessmentCitation(
                    claim="Test claim",
                    content_item_ids=["valid-id", "FAKE-ID"],
                    labels=Labels(domain="assessment"),
                )
            ],
            confidence_level=0.7,
            labels=Labels(domain="assessment"),
        )

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "name": "Test Source",
                "platform": "telegram",
                "url_or_handle": "t.me/test",
            }
        )
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )

        with (
            patch("anveshak.reporter.worker.db") as mock_db,
            patch(
                "anveshak.reporter.worker.call_ollama_for_assessment",
                new_callable=AsyncMock,
                return_value=mock_brief,
            ),
            patch("anveshak.reporter.worker.render_assessment_prompt", return_value="test prompt"),
        ):
            mock_db.fetch_assessment = AsyncMock(
                return_value={
                    "id": "a1",
                    "topic_id": "t1",
                    "source_id": "s1",
                    "generated_at": None,
                    "stats": "{}",
                    "platform_metadata": None,
                }
            )
            mock_db.fetch_topic = AsyncMock(
                return_value={
                    "id": "t1",
                    "name": "Test",
                    "keywords": ["test"],
                }
            )
            mock_db.fetch_source_content_for_brief = AsyncMock(
                return_value=[
                    {
                        "id": "valid-id",
                        "clean_text": "Some content",
                        "url": "https://example.com",
                        "captured_at": "2026-06-20",
                    },
                ]
            )
            mock_db.fetch_source_info = AsyncMock(
                return_value={
                    "name": "Test Source",
                    "platform": "telegram",
                    "url_or_handle": "t.me/test",
                }
            )
            mock_db.set_assessment_brief = AsyncMock(return_value=True)
            ctx["db"] = mock_pool

            await generate_source_assessment(ctx, "a1")

            mock_db.set_assessment_brief.assert_called_once()
            # FAKE-ID should have been stripped, only valid-id remains in citations
            assert "FAKE-ID" not in str(mock_brief.cited_claims[0].content_item_ids)

            # The stripping must survive rendering: what actually reaches the DB
            # is brief_md, so assert on that rather than only on the in-memory
            # brief the code mutated.
            brief_md = mock_db.set_assessment_brief.call_args.kwargs["brief_md"]
            assert "FAKE-ID" not in brief_md, "hallucinated ID leaked into the stored brief"
            assert "valid-id" in brief_md, "real citation was stripped along with the fake one"
