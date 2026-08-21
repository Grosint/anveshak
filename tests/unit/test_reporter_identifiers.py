"""Unit tests for Engine C Step 9 — Report identifier intelligence enhancements.

Tests cover:
  - DB functions: fetch_topic_identifiers, fetch_topic_template_matches
  - Identifier context assembly for LLM prompt
  - Recommended actions generation from template matches
  - content_md identifier sections (present when data exists, absent when empty)
  - Prompt includes identifier context
  - PDF HTML includes identifier sections
  - Worker integrates identifier data into generate_report pipeline

pytest.mark.unit — mocks all DB calls, no external dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Test data factories
# ---------------------------------------------------------------------------


def _make_identifiers():
    """Sample identifier_clusters rows."""
    return [
        {
            "identifier_type": "PHONE_IN",
            "identifier_value": "9876543210",
            "source_count": 5,
            "content_item_count": 12,
            "first_seen_at": datetime(2026, 6, 1, tzinfo=UTC),
            "last_seen_at": datetime(2026, 6, 10, tzinfo=UTC),
        },
        {
            "identifier_type": "UPI",
            "identifier_value": "scammer@paytm",
            "source_count": 3,
            "content_item_count": 7,
            "first_seen_at": datetime(2026, 6, 2, tzinfo=UTC),
            "last_seen_at": datetime(2026, 6, 9, tzinfo=UTC),
        },
        {
            "identifier_type": "CRYPTO_BTC",
            "identifier_value": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "source_count": 2,
            "content_item_count": 3,
            "first_seen_at": datetime(2026, 6, 5, tzinfo=UTC),
            "last_seen_at": datetime(2026, 6, 8, tzinfo=UTC),
        },
    ]


def _make_template_matches():
    """Sample template match aggregation rows."""
    return [
        {
            "template_name": "mule_recruitment",
            "template_display": "Mule Account Recruitment",
            "confidence": 0.85,
            "severity": "CRITICAL",
            "legal_sections": ["PMLA Section 3", "PMLA Section 4"],
            "match_count": 5,
        },
        {
            "template_name": "investment_fraud",
            "template_display": "Investment Fraud",
            "confidence": 0.72,
            "severity": "CRITICAL",
            "legal_sections": ["BNS 318", "IT Act 66D"],
            "match_count": 3,
        },
    ]


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
    s.include_legal_mapping = True
    s.include_three_lens = False
    return s


def _make_ctx(settings=None):
    s = settings or _make_settings()
    return {"db": AsyncMock(), "settings": s}


def _make_report_content():
    rc = MagicMock()
    rc.executive_summary = "Summary of mule recruitment activity."
    rc.key_findings = ["Finding 1: Mule recruitment via Telegram"]
    rc.recommendations = ["Block identified UPI IDs"]
    rc.source_citations = ["https://example.com/src1"]
    rc.confidence_level = 0.80
    rc.legal_sections = []
    rc.three_lens = None
    return rc


def _data_bundle():
    return {
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


# ---------------------------------------------------------------------------
# DB function tests
# ---------------------------------------------------------------------------


class TestFetchTopicIdentifiers:
    """fetch_topic_identifiers returns top identifiers from identifier_clusters."""

    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self):
        from anveshak.reporter.db import fetch_topic_identifiers

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[dict(r) if isinstance(r, dict) else r for r in _make_identifiers()]
        )
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        result = await fetch_topic_identifiers(mock_pool, "topic-1")
        assert len(result) == 3
        assert result[0]["identifier_type"] == "PHONE_IN"
        assert result[0]["source_count"] == 5

    @pytest.mark.asyncio
    async def test_empty_topic_returns_empty_list(self):
        from anveshak.reporter.db import fetch_topic_identifiers

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        result = await fetch_topic_identifiers(mock_pool, "topic-empty")
        assert result == []

    @pytest.mark.asyncio
    async def test_respects_limit_param(self):
        from anveshak.reporter.db import fetch_topic_identifiers

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        await fetch_topic_identifiers(mock_pool, "topic-1", limit=50)
        # Check that the limit was passed to SQL query
        call_args = mock_conn.fetch.call_args[0]
        assert 50 in call_args  # limit param in positional args


class TestFetchTopicTemplateMatches:
    """fetch_topic_template_matches returns aggregated template match data."""

    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self):
        from anveshak.reporter.db import fetch_topic_template_matches

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[dict(r) if isinstance(r, dict) else r for r in _make_template_matches()]
        )
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        result = await fetch_topic_template_matches(mock_pool, "topic-1")
        assert len(result) == 2
        assert result[0]["template_name"] == "mule_recruitment"
        assert result[0]["severity"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_empty_when_no_matches(self):
        from anveshak.reporter.db import fetch_topic_template_matches

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        result = await fetch_topic_template_matches(mock_pool, "topic-1")
        assert result == []


# ---------------------------------------------------------------------------
# Identifier context assembly tests
# ---------------------------------------------------------------------------


class TestAssembleIdentifierContext:
    """assemble_identifier_context formats identifier data for LLM prompt."""

    def test_formats_identifiers_by_type(self):
        from anveshak.reporter.rag import assemble_identifier_context

        ids = _make_identifiers()
        ctx = assemble_identifier_context(ids)
        assert "PHONE_IN" in ctx or "Phone" in ctx
        assert "9876543210" in ctx
        assert "5 sources" in ctx or "5" in ctx

    def test_formats_upi_identifiers(self):
        from anveshak.reporter.rag import assemble_identifier_context

        ids = _make_identifiers()
        ctx = assemble_identifier_context(ids)
        assert "scammer@paytm" in ctx

    def test_formats_crypto_identifiers(self):
        from anveshak.reporter.rag import assemble_identifier_context

        ids = _make_identifiers()
        ctx = assemble_identifier_context(ids)
        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in ctx

    def test_empty_list_returns_empty_string(self):
        from anveshak.reporter.rag import assemble_identifier_context

        ctx = assemble_identifier_context([])
        assert ctx == ""

    def test_output_is_string(self):
        from anveshak.reporter.rag import assemble_identifier_context

        ctx = assemble_identifier_context(_make_identifiers())
        assert isinstance(ctx, str)
        assert len(ctx) > 0


# ---------------------------------------------------------------------------
# Recommended actions tests
# ---------------------------------------------------------------------------


class TestBuildRecommendedActions:
    """build_recommended_actions generates actions based on template matches."""

    def test_mule_recruitment_actions(self):
        from anveshak.reporter.rag import build_recommended_actions

        matches = [_make_template_matches()[0]]  # mule_recruitment
        actions = build_recommended_actions(matches)
        assert isinstance(actions, list)
        assert len(actions) > 0
        # Should mention freezing/blocking accounts or CDR
        action_text = " ".join(actions).lower()
        assert any(w in action_text for w in ["freeze", "block", "pmla", "account", "bank"])

    def test_investment_fraud_actions(self):
        from anveshak.reporter.rag import build_recommended_actions

        matches = [_make_template_matches()[1]]  # investment_fraud
        actions = build_recommended_actions(matches)
        assert isinstance(actions, list)
        assert len(actions) > 0

    def test_empty_matches_returns_empty(self):
        from anveshak.reporter.rag import build_recommended_actions

        actions = build_recommended_actions([])
        assert actions == []

    def test_multiple_templates_combine_actions(self):
        from anveshak.reporter.rag import build_recommended_actions

        matches = _make_template_matches()
        actions = build_recommended_actions(matches)
        # Both templates should contribute actions
        assert len(actions) >= 2


# ---------------------------------------------------------------------------
# _build_content_md with identifiers
# ---------------------------------------------------------------------------


class TestBuildContentMdIdentifiers:
    """_build_content_md includes identifier sections when data provided."""

    def test_includes_identified_indicators_section(self):
        from anveshak.reporter.worker import _build_content_md

        rc = _make_report_content()
        md = _build_content_md(
            rc,
            identifiers=_make_identifiers(),
        )
        assert "## Identified Indicators" in md
        assert "9876543210" in md
        assert "scammer@paytm" in md

    def test_includes_source_count_in_indicators(self):
        from anveshak.reporter.worker import _build_content_md

        rc = _make_report_content()
        md = _build_content_md(
            rc,
            identifiers=_make_identifiers(),
        )
        # Phone has 5 sources
        assert "5" in md

    def test_includes_template_matches_section(self):
        from anveshak.reporter.worker import _build_content_md

        rc = _make_report_content()
        md = _build_content_md(
            rc,
            template_matches=_make_template_matches(),
        )
        assert "## Scam Template Matches" in md
        assert "Mule Account Recruitment" in md
        assert "CRITICAL" in md

    def test_includes_recommended_actions_section(self):
        from anveshak.reporter.worker import _build_content_md

        rc = _make_report_content()
        md = _build_content_md(
            rc,
            template_matches=_make_template_matches(),
        )
        assert "## Recommended Actions" in md

    def test_omits_identifier_sections_when_no_data(self):
        from anveshak.reporter.worker import _build_content_md

        rc = _make_report_content()
        md = _build_content_md(rc)
        assert "## Identified Indicators" not in md
        assert "## Scam Template Matches" not in md
        assert "## Recommended Actions" not in md

    def test_omits_indicators_when_empty_list(self):
        from anveshak.reporter.worker import _build_content_md

        rc = _make_report_content()
        md = _build_content_md(rc, identifiers=[], template_matches=[])
        assert "## Identified Indicators" not in md
        assert "## Scam Template Matches" not in md

    def test_includes_legal_sections_from_templates(self):
        from anveshak.reporter.worker import _build_content_md

        rc = _make_report_content()
        md = _build_content_md(
            rc,
            template_matches=_make_template_matches(),
        )
        # Template legal_sections should appear in recommended actions or template section
        assert "PMLA" in md

    def test_preserves_existing_sections(self):
        """Identifier sections don't break existing executive_summary/findings/etc."""
        from anveshak.reporter.worker import _build_content_md

        rc = _make_report_content()
        md = _build_content_md(
            rc,
            identifiers=_make_identifiers(),
            template_matches=_make_template_matches(),
        )
        assert "## Executive Summary" in md
        assert "## Key Findings" in md
        assert "## Recommendations" in md
        assert "## Source Citations" in md

    def test_identifier_section_before_source_citations(self):
        """Per plan: new section between Key Findings and Source Citations."""
        from anveshak.reporter.worker import _build_content_md

        rc = _make_report_content()
        md = _build_content_md(
            rc,
            identifiers=_make_identifiers(),
        )
        findings_pos = md.index("## Key Findings")
        indicators_pos = md.index("## Identified Indicators")
        citations_pos = md.index("## Source Citations")
        assert findings_pos < indicators_pos < citations_pos


# ---------------------------------------------------------------------------
# Prompt with identifier context
# ---------------------------------------------------------------------------


class TestRenderPromptWithIdentifiers:
    """render_prompt includes identifier context when provided."""

    def test_prompt_includes_identifier_context(self):
        from anveshak.reporter.prompt_templates import render_prompt

        identifier_context = (
            "IDENTIFIED INDICATORS IN THIS TOPIC:\n"
            "Phones: 9876543210 (5 sources)\n"
            "UPI IDs: scammer@paytm (3 sources)\n"
        )
        prompt = render_prompt(
            "intelligence_brief",
            "Cyber Fraud",
            ["mule", "fraud"],
            "content context",
            identifier_context=identifier_context,
        )
        assert "IDENTIFIED INDICATORS" in prompt
        assert "9876543210" in prompt
        assert "scammer@paytm" in prompt

    def test_prompt_without_identifier_context(self):
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt(
            "intelligence_brief",
            "T",
            [],
            "c",
        )
        assert "IDENTIFIED INDICATORS" not in prompt

    def test_empty_identifier_context_omitted(self):
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt(
            "intelligence_brief",
            "T",
            [],
            "c",
            identifier_context="",
        )
        assert "IDENTIFIED INDICATORS" not in prompt


# ---------------------------------------------------------------------------
# PDF with identifier sections
# ---------------------------------------------------------------------------


class TestPdfIdentifierSections:
    """PDF HTML template includes identifier sections when data provided."""

    def test_pdf_includes_indicators_table(self):
        from anveshak.reporter.pdf import render_pdf_html

        report_data = {
            "topic_name": "Cyber Fraud",
            "report_type": "intelligence_brief",
            "generated_at": "2026-06-11",
            "confidence_score": 0.8,
            "content_item_count": 10,
            "executive_summary": "Test summary",
            "key_findings": ["Finding 1"],
            "recommendations": ["Rec 1"],
            "source_citations": ["https://example.com"],
            "labels": {"classification": "OPEN"},
            "identifiers": _make_identifiers(),
        }
        html = render_pdf_html(report_data)
        assert "Identified Indicators" in html
        assert "9876543210" in html
        assert "scammer@paytm" in html

    def test_pdf_includes_template_matches(self):
        from anveshak.reporter.pdf import render_pdf_html

        report_data = {
            "topic_name": "Cyber Fraud",
            "report_type": "intelligence_brief",
            "generated_at": "2026-06-11",
            "confidence_score": 0.8,
            "content_item_count": 10,
            "executive_summary": "Test summary",
            "key_findings": ["Finding 1"],
            "recommendations": ["Rec 1"],
            "source_citations": ["https://example.com"],
            "labels": {"classification": "OPEN"},
            "template_matches": _make_template_matches(),
        }
        html = render_pdf_html(report_data)
        assert "Scam Template Matches" in html
        assert "Mule Account Recruitment" in html
        assert "CRITICAL" in html

    def test_pdf_omits_sections_when_no_data(self):
        from anveshak.reporter.pdf import render_pdf_html

        report_data = {
            "topic_name": "Clean Topic",
            "report_type": "intelligence_brief",
            "generated_at": "2026-06-11",
            "confidence_score": 0.8,
            "content_item_count": 5,
            "executive_summary": "Nothing suspicious",
            "key_findings": ["No issues"],
            "recommendations": ["Continue monitoring"],
            "source_citations": ["https://example.com"],
            "labels": {"classification": "OPEN"},
        }
        html = render_pdf_html(report_data)
        assert "Identified Indicators" not in html
        assert "Scam Template Matches" not in html

    def test_pdf_includes_recommended_actions(self):
        from anveshak.reporter.pdf import render_pdf_html

        report_data = {
            "topic_name": "Fraud Topic",
            "report_type": "intelligence_brief",
            "generated_at": "2026-06-11",
            "confidence_score": 0.8,
            "content_item_count": 10,
            "executive_summary": "Summary",
            "key_findings": ["F1"],
            "recommendations": ["R1"],
            "source_citations": [],
            "labels": {"classification": "OPEN"},
            "recommended_actions": ["Freeze UPI ID scammer@paytm", "Request CDR for 9876543210"],
        }
        html = render_pdf_html(report_data)
        assert "Recommended Actions" in html
        assert "Freeze UPI" in html


# ---------------------------------------------------------------------------
# Worker integration — generate_report fetches identifiers
# ---------------------------------------------------------------------------


class TestGenerateReportWithIdentifiers:
    """generate_report fetches and includes identifier data."""

    @pytest.mark.asyncio
    async def test_happy_path_with_identifiers(self):
        """Full pipeline: identifiers + template matches included in content_md."""
        from anveshak.reporter.llm import BlufContent

        ctx = _make_ctx()
        chunks = [
            {"id": "c1", "source_id": "src-1", "clean_text": "fraud text", "url": "https://ex.com"}
        ]

        with (
            patch("anveshak.reporter.worker.db") as mock_db,
            patch(
                "anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock
            ) as mock_embed,
            patch(
                "anveshak.reporter.worker.call_ollama_for_bluf", new_callable=AsyncMock
            ) as mock_llm,
            patch("anveshak.reporter.worker.render_bluf_prompt", return_value="bluf prompt"),
            patch("anveshak.reporter.worker.geocode_locations") as mock_geo,
            patch("anveshak.reporter.worker.build_geojson") as mock_geojson,
            patch("anveshak.reporter.worker.extract_locations_from_text") as mock_extract,
        ):
            mock_db.fetch_report = AsyncMock(
                return_value={
                    "id": "report-1",
                    "topic_id": "topic-1",
                    "report_type": "intelligence_brief",
                    "credibility_min_filter": 30.0,
                }
            )
            mock_db.fetch_topic = AsyncMock(
                return_value={
                    "id": "topic-1",
                    "name": "Cyber Fraud",
                    "keywords": ["fraud"],
                }
            )
            mock_db.fetch_report_data_bundle = AsyncMock(return_value=_data_bundle())
            mock_db.fetch_rag_chunks = AsyncMock(return_value=chunks)
            mock_db.fetch_sources_for_snapshot = AsyncMock(return_value={})
            mock_db.fetch_topic_location_entities = AsyncMock(return_value=[])
            mock_db.fetch_topic_identifiers = AsyncMock(return_value=_make_identifiers())
            mock_db.fetch_topic_template_matches = AsyncMock(return_value=_make_template_matches())
            mock_db.set_report_generated = AsyncMock(return_value=True)
            mock_db.set_report_failed = AsyncMock()
            mock_db.update_job_status = AsyncMock()
            mock_embed.return_value = [0.1] * 384
            mock_llm.return_value = BlufContent(
                bluf="Test.",
                confidence_level=0.8,
                labels={"classification": "OPEN", "domain": "report", "owner_org": "anveshak"},
            )
            mock_geo.return_value = []
            mock_geojson.return_value = {"type": "FeatureCollection", "features": []}
            mock_extract.return_value = []

            from anveshak.reporter.worker import generate_report

            await generate_report(ctx, "report-1")

            # DB functions called
            mock_db.fetch_topic_identifiers.assert_awaited_once()
            mock_db.fetch_topic_template_matches.assert_awaited_once()

            # Content MD includes identifier sections
            call_kwargs = mock_db.set_report_generated.call_args[1]
            content_md = call_kwargs["content_md"]
            assert "## Identified Indicators" in content_md
            assert "## Scam Template Matches" in content_md

    @pytest.mark.asyncio
    async def test_no_identifiers_graceful(self):
        """No identifiers found → sections omitted, no crash."""
        from anveshak.reporter.llm import BlufContent

        ctx = _make_ctx()
        chunks = [{"id": "c1", "source_id": "src-1", "clean_text": "text", "url": "https://ex.com"}]

        with (
            patch("anveshak.reporter.worker.db") as mock_db,
            patch(
                "anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock
            ) as mock_embed,
            patch(
                "anveshak.reporter.worker.call_ollama_for_bluf", new_callable=AsyncMock
            ) as mock_llm,
            patch("anveshak.reporter.worker.render_bluf_prompt", return_value="bluf prompt"),
            patch("anveshak.reporter.worker.geocode_locations") as mock_geo,
            patch("anveshak.reporter.worker.build_geojson") as mock_geojson,
            patch("anveshak.reporter.worker.extract_locations_from_text") as mock_extract,
        ):
            mock_db.fetch_report = AsyncMock(
                return_value={
                    "id": "report-1",
                    "topic_id": "topic-1",
                    "report_type": "intelligence_brief",
                    "credibility_min_filter": 30.0,
                }
            )
            mock_db.fetch_topic = AsyncMock(
                return_value={
                    "id": "topic-1",
                    "name": "Clean Topic",
                    "keywords": ["safe"],
                }
            )
            mock_db.fetch_report_data_bundle = AsyncMock(return_value=_data_bundle())
            mock_db.fetch_rag_chunks = AsyncMock(return_value=chunks)
            mock_db.fetch_sources_for_snapshot = AsyncMock(return_value={})
            mock_db.fetch_topic_location_entities = AsyncMock(return_value=[])
            mock_db.fetch_topic_identifiers = AsyncMock(return_value=[])
            mock_db.fetch_topic_template_matches = AsyncMock(return_value=[])
            mock_db.set_report_generated = AsyncMock(return_value=True)
            mock_db.set_report_failed = AsyncMock()
            mock_db.update_job_status = AsyncMock()
            mock_embed.return_value = [0.1] * 384
            mock_llm.return_value = BlufContent(
                bluf="Test.",
                confidence_level=0.8,
                labels={"classification": "OPEN", "domain": "report", "owner_org": "anveshak"},
            )
            mock_geo.return_value = []
            mock_geojson.return_value = {"type": "FeatureCollection", "features": []}
            mock_extract.return_value = []

            from anveshak.reporter.worker import generate_report

            await generate_report(ctx, "report-1")

            # Should succeed without identifier sections
            mock_db.set_report_generated.assert_awaited_once()
            content_md = mock_db.set_report_generated.call_args[1]["content_md"]
            assert "## Identified Indicators" not in content_md
            assert "## Scam Template Matches" not in content_md
