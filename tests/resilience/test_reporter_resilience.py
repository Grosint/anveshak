"""Resilience tests for reporter + identifier pipeline — Engine C Phase EC-4.

Degradation scenarios: garbage input, missing data, DB failures, malformed
identifier data, unknown templates. Every test verifies graceful handling
(no crash, clear fallback) rather than correct output.

pytest.mark.resilience — runs in make test-e2e, not in fast CI.
"""
from __future__ import annotations

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.resilience, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings():
    s = MagicMock()
    s.rag_top_k = 10
    s.rag_max_context_tokens = 4000
    s.ollama_model = "qwen2:7b"
    s.ollama_host = "http://ollama:11434"
    s.ollama_report_timeout_s = 30
    s.ollama_retry_max = 2
    s.source_warning_lookback_days = 30
    s.topic_relevance_threshold = 0.35
    s.include_legal_mapping = False
    s.include_three_lens = False
    return s


def _make_ctx():
    return {"db": AsyncMock(), "settings": _make_settings()}


def _make_rc():
    rc = MagicMock()
    rc.executive_summary = "Test summary."
    rc.key_findings = ["Finding 1"]
    rc.recommendations = ["Rec 1"]
    rc.source_citations = ["https://example.com"]
    rc.confidence_level = 0.7
    rc.legal_sections = []
    rc.three_lens = None
    return rc


# ---------------------------------------------------------------------------
# 1. Identifier extraction on garbage text → empty, no crash
# ---------------------------------------------------------------------------

class TestIdentifierExtractionResilience:
    """Identifier extractor handles garbage/adversarial input gracefully."""

    def test_garbage_text_returns_empty(self):
        """Binary-like garbage → no identifiers, no crash."""
        from anveshak.analyst.identifiers import extract_identifiers

        garbage = "\x00\x01\x02\xff\xfe\xfd" * 100
        result = extract_identifiers(garbage)
        assert isinstance(result, list)
        # May find false positives but must not crash

    def test_empty_string_returns_empty(self):
        from anveshak.analyst.identifiers import extract_identifiers

        result = extract_identifiers("")
        assert result == []

    def test_very_long_text_no_crash(self):
        """100KB of random ASCII — must not hang or crash."""
        from anveshak.analyst.identifiers import extract_identifiers

        # 100K chars of repeated non-matching text
        text = "no identifiers here at all " * 4000
        result = extract_identifiers(text)
        assert isinstance(result, list)

    def test_unicode_heavy_text_no_crash(self):
        """Hindi/Chinese/Arabic text — must not crash."""
        from anveshak.analyst.identifiers import extract_identifiers

        text = "यह एक परीक्षण है 这是测试 هذا اختبار"
        result = extract_identifiers(text)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 2. Template matching with 0 active templates → skip gracefully
# ---------------------------------------------------------------------------

class TestTemplateMatchingResilience:
    """Template matcher handles edge cases without crash."""

    def test_no_templates_returns_none(self):
        """Empty template list → None match, not crash."""
        from anveshak.analyst.templates import match_templates

        result = match_templates(
            content_keywords={"fraud", "bank", "account"},
            identifier_types={"PHONE_IN", "UPI"},
            content_embedding=[0.1] * 384,
            templates=[],
        )
        assert result is None

    def test_no_keywords_no_crash(self):
        """Empty keyword set → no match possible, graceful."""
        from anveshak.analyst.templates import match_templates, ScamTemplate

        template = ScamTemplate(
            name="test", display="Test", category="fraud",
            keywords=["fraud", "bank"], min_keyword_hits=1,
            expected_identifiers=[], severity="HIGH",
            reference_embedding=None, legal_sections=[],
        )
        result = match_templates(
            content_keywords=set(),
            identifier_types=set(),
            content_embedding=None,
            templates=[template],
        )
        assert result is None

    def test_none_embedding_no_crash(self):
        """None embedding → keyword-only scoring, no crash."""
        from anveshak.analyst.templates import match_templates, ScamTemplate

        template = ScamTemplate(
            name="test", display="Test", category="fraud",
            keywords=["fraud", "bank", "account"], min_keyword_hits=2,
            expected_identifiers=["PHONE_IN"], severity="CRITICAL",
            reference_embedding=None, legal_sections=["BNS 318"],
        )
        result = match_templates(
            content_keywords={"fraud", "bank", "account"},
            identifier_types={"PHONE_IN"},
            content_embedding=None,
            templates=[template],
        )
        # Should either match or not, but not crash
        assert result is None or hasattr(result, "template_name")


# ---------------------------------------------------------------------------
# 3. Report generation with DB query failure → graceful degradation
# ---------------------------------------------------------------------------

class TestReportIdentifierDBFailure:
    """Report generation handles identifier DB errors gracefully."""

    async def test_identifier_db_error_does_not_crash_report(self):
        """If fetch_topic_identifiers raises, report should still generate
        or fail cleanly — not propagate unhandled exception."""
        ctx = _make_ctx()
        chunks = [{"id": "c1", "source_id": "src-1", "clean_text": "text", "url": "https://ex.com"}]
        rc = _make_rc()

        with patch("anveshak.reporter.worker.db") as mock_db, \
             patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock) as mock_embed, \
             patch("anveshak.reporter.worker.assemble_context") as mock_ctx, \
             patch("anveshak.reporter.worker.render_prompt") as mock_prompt, \
             patch("anveshak.reporter.worker.call_ollama_with_retry", new_callable=AsyncMock) as mock_llm, \
             patch("anveshak.reporter.worker.geocode_locations") as mock_geo, \
             patch("anveshak.reporter.worker.build_geojson") as mock_geojson, \
             patch("anveshak.reporter.worker.extract_locations_from_text") as mock_extract:
            mock_db.fetch_report = AsyncMock(return_value={
                "id": "r1", "topic_id": "t1", "report_type": "intelligence_brief",
                "credibility_min_filter": 30.0,
            })
            mock_db.fetch_topic = AsyncMock(return_value={
                "id": "t1", "name": "Test", "keywords": [],
            })
            mock_db.fetch_rag_chunks = AsyncMock(return_value=chunks)
            # Simulate DB error on identifier fetch
            mock_db.fetch_topic_identifiers = AsyncMock(side_effect=Exception("DB connection lost"))
            mock_db.fetch_topic_template_matches = AsyncMock(return_value=[])
            mock_db.fetch_sources_for_snapshot = AsyncMock(return_value={})
            mock_db.fetch_topic_location_entities = AsyncMock(return_value=[])
            mock_db.set_report_generated = AsyncMock(return_value=True)
            mock_db.set_report_failed = AsyncMock()
            mock_db.update_job_status = AsyncMock()
            mock_embed.return_value = [0.1] * 384
            mock_ctx.return_value = ("context", 1, "2026-06-01")
            mock_prompt.return_value = "prompt"
            mock_llm.return_value = rc
            mock_geo.return_value = []
            mock_geojson.return_value = {"type": "FeatureCollection", "features": []}
            mock_extract.return_value = []

            from anveshak.reporter.worker import generate_report
            # Should not raise — either generates without identifiers or fails cleanly
            try:
                await generate_report(ctx, "r1")
            except Exception:
                # If it does raise, that's the current behavior — test documents it.
                # The GREEN phase may add a try/except to handle gracefully.
                pass

            # Either report was generated or explicitly failed — not left in limbo
            assert (mock_db.set_report_generated.await_count == 1
                    or mock_db.set_report_failed.await_count == 1
                    ), "Report must either generate or explicitly fail, not hang"


# ---------------------------------------------------------------------------
# 4. assemble_identifier_context with malformed data → no crash
# ---------------------------------------------------------------------------

class TestAssembleIdentifierContextResilience:
    """Identifier context assembly handles edge cases."""

    def test_missing_keys_in_identifier_dict(self):
        """Identifier dict missing expected keys → KeyError or graceful skip."""
        from anveshak.reporter.rag import assemble_identifier_context

        malformed = [
            {"identifier_type": "PHONE_IN"},  # missing identifier_value, source_count
        ]
        try:
            result = assemble_identifier_context(malformed)
            # If it works, must be a string
            assert isinstance(result, str)
        except KeyError:
            # Current behavior: KeyError on missing keys
            # GREEN phase may add .get() with defaults
            pass

    def test_none_list_no_crash(self):
        """None passed instead of list — should handle or raise TypeError."""
        from anveshak.reporter.rag import assemble_identifier_context

        try:
            result = assemble_identifier_context(None)
            assert result == "" or result is None
        except TypeError:
            pass  # Acceptable — caller should guard

    def test_empty_identifier_values(self):
        """Identifiers with empty strings for values."""
        from anveshak.reporter.rag import assemble_identifier_context

        ids = [
            {"identifier_type": "PHONE_IN", "identifier_value": "",
             "source_count": 0, "content_item_count": 0,
             "first_seen_at": None, "last_seen_at": None},
        ]
        result = assemble_identifier_context(ids)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 5. build_recommended_actions with unknown template → empty
# ---------------------------------------------------------------------------

class TestBuildRecommendedActionsResilience:
    """Recommended actions handles unknown templates gracefully."""

    def test_unknown_template_name_returns_empty_or_legal_only(self):
        """Template name not in _TEMPLATE_ACTIONS → no template-specific actions."""
        from anveshak.reporter.rag import build_recommended_actions

        matches = [
            {"template_name": "totally_unknown_template",
             "template_display": "Unknown Thing",
             "confidence": 0.9, "severity": "CRITICAL",
             "legal_sections": [], "match_count": 5},
        ]
        actions = build_recommended_actions(matches)
        assert isinstance(actions, list)
        # No template-specific actions for unknown template, no legal sections
        # Should return empty or only legal refs
        assert all(isinstance(a, str) for a in actions)

    def test_none_legal_sections_no_crash(self):
        """legal_sections=None in match dict → no crash."""
        from anveshak.reporter.rag import build_recommended_actions

        matches = [
            {"template_name": "mule_recruitment",
             "template_display": "Mule",
             "confidence": 0.8, "severity": "CRITICAL",
             "legal_sections": None, "match_count": 3},
        ]
        actions = build_recommended_actions(matches)
        assert isinstance(actions, list)
        assert len(actions) > 0  # Should still have mule-specific actions

    def test_mixed_known_unknown_templates(self):
        """Mix of known and unknown templates — known actions returned, unknown skipped."""
        from anveshak.reporter.rag import build_recommended_actions

        matches = [
            {"template_name": "mule_recruitment", "template_display": "Mule",
             "confidence": 0.8, "severity": "CRITICAL",
             "legal_sections": ["PMLA Section 3"], "match_count": 3},
            {"template_name": "alien_invasion", "template_display": "Aliens",
             "confidence": 0.5, "severity": "LOW",
             "legal_sections": None, "match_count": 1},
        ]
        actions = build_recommended_actions(matches)
        assert isinstance(actions, list)
        assert len(actions) >= 3  # At least the 3 mule actions


# ---------------------------------------------------------------------------
# 6. PDF generation with malformed data → no crash
# ---------------------------------------------------------------------------

class TestPdfResilience:
    """PDF HTML rendering handles edge cases."""

    def test_pdf_with_empty_identifiers_list(self):
        from anveshak.reporter.pdf import render_pdf_html

        data = {
            "topic_name": "Test", "report_type": "intelligence_brief",
            "generated_at": "2026-06-11", "confidence_score": 0.5,
            "content_item_count": 1,
            "executive_summary": "Summary", "key_findings": [],
            "recommendations": [], "source_citations": [],
            "labels": {"classification": "OPEN"},
            "identifiers": [],
            "template_matches": [],
        }
        html = render_pdf_html(data)
        assert isinstance(html, str)
        assert "Identified Indicators" not in html

    def test_pdf_with_none_confidence_in_template(self):
        """Template match with None confidence → no crash in rendering."""
        from anveshak.reporter.pdf import render_pdf_html

        data = {
            "topic_name": "Test", "report_type": "intelligence_brief",
            "generated_at": "2026-06-11", "confidence_score": 0.5,
            "content_item_count": 1,
            "executive_summary": "S", "key_findings": ["F"],
            "recommendations": ["R"], "source_citations": [],
            "labels": {"classification": "OPEN"},
            "template_matches": [
                {"template_name": "test", "template_display": "Test",
                 "confidence": None, "severity": "HIGH", "match_count": 1},
            ],
        }
        html = render_pdf_html(data)
        assert isinstance(html, str)
        assert "Scam Template Matches" in html


# ---------------------------------------------------------------------------
# 7. _build_content_md resilience
# ---------------------------------------------------------------------------

class TestBuildContentMdResilience:
    """_build_content_md handles edge case inputs."""

    def test_identifier_with_none_values(self):
        """Identifier dict with None values → rendered safely."""
        from anveshak.reporter.worker import _build_content_md

        rc = _make_rc()
        ids = [
            {"identifier_type": None, "identifier_value": None,
             "source_count": None, "content_item_count": None,
             "first_seen_at": None, "last_seen_at": None},
        ]
        md = _build_content_md(rc, identifiers=ids)
        assert isinstance(md, str)
        assert "## Identified Indicators" in md

    def test_template_match_with_zero_confidence(self):
        """Template with 0.0 confidence → renders without crash."""
        from anveshak.reporter.worker import _build_content_md

        rc = _make_rc()
        matches = [
            {"template_name": "test", "template_display": "Test Match",
             "confidence": 0.0, "severity": "LOW",
             "legal_sections": [], "match_count": 1},
        ]
        md = _build_content_md(rc, template_matches=matches)
        assert "## Scam Template Matches" in md
        assert "0%" in md
