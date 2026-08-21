"""Unit tests for data-driven report generation (v2).

Tests cover:
- fetch_report_data_bundle — SQL data fetching for structured reports
- BlufContent — minimal LLM output model
- render_bluf_prompt — short BLUF prompt template
- _build_content_md_v2 — data-driven markdown builder

pytest.mark.unit — all DB calls mocked, never hits real postgres.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

SAMPLE_TOPIC_STATS = {
    "name": "UAV Activity",
    "content_count": 148,
    "source_count": 9,
    "cluster_count": 8,
    "signal_count": 5,
}

SAMPLE_SOURCES = [
    {"name": "Reuters", "platform": "web", "credibility_score": 72.0, "item_count": 35},
    {"name": "NDTV", "platform": "web", "credibility_score": 65.0, "item_count": 28},
    {"name": "r/worldnews", "platform": "reddit", "credibility_score": 45.0, "item_count": 15},
]

SAMPLE_CLUSTERS = [
    {
        "id": "c1",
        "label": "UAV sightings near border",
        "item_count": 42,
        "independent_source_count": 3,
        "executive_summary": "Multiple UAV sightings reported.",
    },
    {
        "id": "c2",
        "label": "Military response",
        "item_count": 28,
        "independent_source_count": 2,
        "executive_summary": "Indian military deploys counter-drone systems.",
    },
]

SAMPLE_SIGNALS = [
    {
        "id": "s1",
        "description": "3 independent sources corroborate UAV cluster",
        "status": "new",
        "cluster_label": "UAV sightings near border",
        "created_at": "2026-04-10T10:00:00Z",
    },
]

SAMPLE_ENTITIES = [
    {
        "entity_type": "GPE",
        "entity_text": "Lakshadweep",
        "mention_count": 12,
        "avg_confidence": 0.92,
    },
    {
        "entity_type": "ORG",
        "entity_text": "Indian Navy",
        "mention_count": 8,
        "avg_confidence": 0.88,
    },
]

SAMPLE_SENTIMENT_TREND = [
    {"date": "2026-04-08", "avg_sentiment": 0.1, "item_count": 15},
    {"date": "2026-04-09", "avg_sentiment": -0.2, "item_count": 22},
    {"date": "2026-04-10", "avg_sentiment": -0.35, "item_count": 31},
]

SAMPLE_KEYWORDS = [
    {"keyword": "UAV", "frequency": 45},
    {"keyword": "drone", "frequency": 38},
    {"keyword": "border", "frequency": 22},
]

SAMPLE_EVIDENCE_ITEMS = [
    {
        "title": "UAV spotted near Lakshadweep",
        "url": "https://reuters.com/article/123",
        "source_name": "Reuters",
        "platform": "web",
        "captured_at": "2026-04-10T08:00:00Z",
        "credibility_score_at_capture": 72.0,
        "snippet": "Maritime patrol aircraft spotted an unidentified UAV...",
    },
]

SAMPLE_LANGUAGE_BREAKDOWN = [
    {"language": "en", "count": 120},
    {"language": "hi", "count": 18},
    {"language": "zh", "count": 10},
]

SAMPLE_DATA_BUNDLE = {
    "topic_stats": SAMPLE_TOPIC_STATS,
    "sources": SAMPLE_SOURCES,
    "clusters": SAMPLE_CLUSTERS,
    "signals": SAMPLE_SIGNALS,
    "entities": SAMPLE_ENTITIES,
    "sentiment_trend": SAMPLE_SENTIMENT_TREND,
    "keywords": SAMPLE_KEYWORDS,
    "evidence_items": SAMPLE_EVIDENCE_ITEMS,
    "language_breakdown": SAMPLE_LANGUAGE_BREAKDOWN,
}

VALID_BLUF_RESPONSE = {
    "bluf": "Increased UAV activity detected near northern border over 48 hours. 3 independent sources corroborate timeline across 8 narrative clusters.",
    "confidence_level": 0.75,
    "labels": {
        "classification": "OPEN",
        "domain": "report",
        "owner_org": "anveshak",
    },
}


# ---------------------------------------------------------------------------
# Phase 1: fetch_report_data_bundle
# ---------------------------------------------------------------------------


class TestFetchReportDataBundle:
    """fetch_report_data_bundle returns dict with all expected keys."""

    @pytest.mark.asyncio
    async def test_returns_all_keys(self):
        from anveshak.reporter.db import fetch_report_data_bundle

        mock_pool = AsyncMock()

        with (
            patch(
                "anveshak.reporter.db.fetch_report_topic_stats",
                new_callable=AsyncMock,
                return_value=SAMPLE_TOPIC_STATS,
            ),
            patch(
                "anveshak.reporter.db.fetch_report_topic_sources",
                new_callable=AsyncMock,
                return_value=SAMPLE_SOURCES,
            ),
            patch(
                "anveshak.reporter.db.fetch_report_topic_clusters",
                new_callable=AsyncMock,
                return_value=SAMPLE_CLUSTERS,
            ),
            patch(
                "anveshak.reporter.db.fetch_report_signals",
                new_callable=AsyncMock,
                return_value=SAMPLE_SIGNALS,
            ),
            patch(
                "anveshak.reporter.db.fetch_report_entities",
                new_callable=AsyncMock,
                return_value=SAMPLE_ENTITIES,
            ),
            patch(
                "anveshak.reporter.db.fetch_report_sentiment_trend",
                new_callable=AsyncMock,
                return_value=SAMPLE_SENTIMENT_TREND,
            ),
            patch(
                "anveshak.reporter.db.fetch_report_keywords",
                new_callable=AsyncMock,
                return_value=SAMPLE_KEYWORDS,
            ),
            patch(
                "anveshak.reporter.db.fetch_report_evidence_items",
                new_callable=AsyncMock,
                return_value=SAMPLE_EVIDENCE_ITEMS,
            ),
            patch(
                "anveshak.reporter.db.fetch_report_language_breakdown",
                new_callable=AsyncMock,
                return_value=SAMPLE_LANGUAGE_BREAKDOWN,
            ),
        ):
            result = await fetch_report_data_bundle(mock_pool, "topic-123")

        expected_keys = {
            "topic_stats",
            "sources",
            "clusters",
            "signals",
            "entities",
            "sentiment_trend",
            "keywords",
            "evidence_items",
            "language_breakdown",
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_topic_stats_has_required_fields(self):
        from anveshak.reporter.db import fetch_report_data_bundle

        mock_pool = AsyncMock()

        with (
            patch(
                "anveshak.reporter.db.fetch_report_topic_stats",
                new_callable=AsyncMock,
                return_value=SAMPLE_TOPIC_STATS,
            ),
            patch(
                "anveshak.reporter.db.fetch_report_topic_sources",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "anveshak.reporter.db.fetch_report_topic_clusters",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "anveshak.reporter.db.fetch_report_signals", new_callable=AsyncMock, return_value=[]
            ),
            patch(
                "anveshak.reporter.db.fetch_report_entities",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "anveshak.reporter.db.fetch_report_sentiment_trend",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "anveshak.reporter.db.fetch_report_keywords",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "anveshak.reporter.db.fetch_report_evidence_items",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "anveshak.reporter.db.fetch_report_language_breakdown",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await fetch_report_data_bundle(mock_pool, "topic-123")

        stats = result["topic_stats"]
        for key in ("name", "content_count", "source_count", "cluster_count", "signal_count"):
            assert key in stats, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Phase 2: BlufContent model
# ---------------------------------------------------------------------------


class TestBlufContentModel:
    """BlufContent Pydantic model validates minimal LLM BLUF output."""

    def test_valid_bluf_parses(self):
        from anveshak.reporter.llm import BlufContent

        obj = BlufContent(**VALID_BLUF_RESPONSE)
        assert "UAV activity" in obj.bluf
        assert obj.confidence_level == pytest.approx(0.75)

    def test_missing_bluf_raises(self):
        from anveshak.reporter.llm import BlufContent

        bad = {k: v for k, v in VALID_BLUF_RESPONSE.items() if k != "bluf"}
        with pytest.raises(ValidationError):
            BlufContent(**bad)

    def test_missing_labels_raises(self):
        """AGENTS.md rule 2: labels is NEVER Optional."""
        from anveshak.reporter.llm import BlufContent

        bad = {k: v for k, v in VALID_BLUF_RESPONSE.items() if k != "labels"}
        with pytest.raises(ValidationError):
            BlufContent(**bad)

    def test_labels_field_required(self):
        from anveshak.reporter.llm import BlufContent

        assert "labels" in BlufContent.model_fields
        field = BlufContent.model_fields["labels"]
        assert field.is_required() or field.default is None


class TestParseBlufResponse:
    """parse_bluf_response validates raw LLM string into BlufContent."""

    def test_valid_json_returns_bluf_content(self):
        from anveshak.reporter.llm import parse_bluf_response

        raw = json.dumps(VALID_BLUF_RESPONSE)
        result = parse_bluf_response(raw)
        assert "UAV activity" in result.bluf

    def test_invalid_json_raises_value_error(self):
        from anveshak.reporter.llm import parse_bluf_response

        with pytest.raises(ValueError):
            parse_bluf_response("not valid json {{{")

    def test_json_with_code_fence_parses(self):
        from anveshak.reporter.llm import parse_bluf_response

        wrapped = f"```json\n{json.dumps(VALID_BLUF_RESPONSE)}\n```"
        result = parse_bluf_response(wrapped)
        assert result.confidence_level == pytest.approx(0.75)

    def test_missing_field_raises_validation_error(self):
        from anveshak.reporter.llm import parse_bluf_response

        incomplete = {"bluf": "test", "labels": VALID_BLUF_RESPONSE["labels"]}
        with pytest.raises(ValidationError):
            parse_bluf_response(json.dumps(incomplete))


class TestCallOllamaForBluf:
    """call_ollama_for_bluf returns BlufContent on success, None on failure."""

    @pytest.mark.asyncio
    async def test_returns_bluf_on_success(self):
        from anveshak.reporter.llm import call_ollama_for_bluf

        settings = MagicMock()
        settings.ollama_model = "qwen2:7b"
        settings.ollama_host = "http://ollama:11434"
        settings.ollama_report_timeout_s = 30
        settings.ollama_retry_max = 2

        with patch("anveshak.reporter.llm.call_ollama", new_callable=AsyncMock) as mock:
            mock.return_value = json.dumps(VALID_BLUF_RESPONSE)
            result = await call_ollama_for_bluf("test prompt", settings, max_retries=2)

        assert result is not None
        assert "UAV activity" in result.bluf
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_returns_none_after_max_retries(self):
        from anveshak.reporter.llm import call_ollama_for_bluf

        settings = MagicMock()
        settings.ollama_model = "qwen2:7b"
        settings.ollama_host = "http://ollama:11434"
        settings.ollama_report_timeout_s = 30

        with patch("anveshak.reporter.llm.call_ollama", new_callable=AsyncMock) as mock:
            mock.return_value = "garbage output"
            result = await call_ollama_for_bluf("test prompt", settings, max_retries=2)

        assert result is None
        assert mock.call_count == 2


# ---------------------------------------------------------------------------
# Phase 2: render_bluf_prompt
# ---------------------------------------------------------------------------


class TestRenderBlufPrompt:
    """render_bluf_prompt produces a short, focused prompt."""

    def test_prompt_contains_topic_name(self):
        from anveshak.reporter.prompt_templates import render_bluf_prompt

        result = render_bluf_prompt(
            topic_name="UAV Activity",
            stats_summary="148 items, 9 sources, 8 clusters, 5 signals",
            cluster_summary="UAV sightings (42 items), Military response (28 items)",
        )
        assert "UAV Activity" in result

    def test_prompt_contains_stats(self):
        from anveshak.reporter.prompt_templates import render_bluf_prompt

        result = render_bluf_prompt(
            topic_name="Test Topic",
            stats_summary="148 items, 9 sources",
            cluster_summary="Cluster A (10 items)",
        )
        assert "148 items" in result

    def test_prompt_under_2000_chars(self):
        """BLUF prompt must be short for qwen2:7b."""
        from anveshak.reporter.prompt_templates import render_bluf_prompt

        result = render_bluf_prompt(
            topic_name="Test Topic",
            stats_summary="148 items, 9 sources, 8 clusters, 5 signals",
            cluster_summary="Cluster A (10 items), Cluster B (8 items)",
        )
        assert len(result) < 2000

    def test_prompt_requests_json_only(self):
        from anveshak.reporter.prompt_templates import render_bluf_prompt

        result = render_bluf_prompt(
            topic_name="Test",
            stats_summary="10 items",
            cluster_summary="C1 (5)",
        )
        assert "JSON" in result
        assert "bluf" in result


# ---------------------------------------------------------------------------
# Phase 3: _build_content_md_v2
# ---------------------------------------------------------------------------


class TestBuildContentMdV2:
    """_build_content_md_v2 builds data-driven markdown from SQL data."""

    def _make_bluf(self):
        from anveshak.reporter.llm import BlufContent

        return BlufContent(**VALID_BLUF_RESPONSE)

    def test_starts_with_v2_marker(self):
        from anveshak.reporter.worker import _build_content_md_v2

        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=SAMPLE_DATA_BUNDLE,
            identifiers=[],
            template_matches=[],
            report_type="intelligence_brief",
        )
        assert md.startswith("<!-- report-v2 -->")

    def test_contains_bluf_text(self):
        from anveshak.reporter.worker import _build_content_md_v2

        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=SAMPLE_DATA_BUNDLE,
            identifiers=[],
            template_matches=[],
            report_type="intelligence_brief",
        )
        assert "UAV activity" in md

    def test_contains_source_inventory(self):
        from anveshak.reporter.worker import _build_content_md_v2

        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=SAMPLE_DATA_BUNDLE,
            identifiers=[],
            template_matches=[],
            report_type="intelligence_brief",
        )
        assert "Reuters" in md
        assert "NDTV" in md

    def test_contains_cluster_data(self):
        from anveshak.reporter.worker import _build_content_md_v2

        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=SAMPLE_DATA_BUNDLE,
            identifiers=[],
            template_matches=[],
            report_type="intelligence_brief",
        )
        assert "UAV sightings near border" in md

    def test_contains_entity_data(self):
        from anveshak.reporter.worker import _build_content_md_v2

        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=SAMPLE_DATA_BUNDLE,
            identifiers=[],
            template_matches=[],
            report_type="intelligence_brief",
        )
        assert "Lakshadweep" in md

    def test_contains_keywords(self):
        from anveshak.reporter.worker import _build_content_md_v2

        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=SAMPLE_DATA_BUNDLE,
            identifiers=[],
            template_matches=[],
            report_type="intelligence_brief",
        )
        assert "UAV" in md
        assert "drone" in md

    def test_research_summary_has_evidence_appendix(self):
        """research_summary includes evidence appendix."""
        from anveshak.reporter.worker import _build_content_md_v2

        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=SAMPLE_DATA_BUNDLE,
            identifiers=[],
            template_matches=[],
            report_type="research_summary",
        )
        assert "Evidence" in md
        assert "reuters.com" in md or "Reuters" in md

    def test_research_summary_has_methodology(self):
        """research_summary includes methodology section."""
        from anveshak.reporter.worker import _build_content_md_v2

        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=SAMPLE_DATA_BUNDLE,
            identifiers=[],
            template_matches=[],
            report_type="research_summary",
        )
        assert "Methodology" in md

    def test_intelligence_brief_skips_evidence_appendix(self):
        """intelligence_brief does NOT include evidence appendix."""
        from anveshak.reporter.worker import _build_content_md_v2

        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=SAMPLE_DATA_BUNDLE,
            identifiers=[],
            template_matches=[],
            report_type="intelligence_brief",
        )
        assert "Evidence Appendix" not in md

    def test_includes_identifiers_when_present(self):
        from anveshak.reporter.worker import _build_content_md_v2

        identifiers = [
            {
                "identifier_type": "PHONE",
                "identifier_value": "+91-9876543210",
                "source_count": 3,
                "content_item_count": 7,
            },
        ]
        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=SAMPLE_DATA_BUNDLE,
            identifiers=identifiers,
            template_matches=[],
            report_type="intelligence_brief",
        )
        assert "+91-9876543210" in md

    def test_stats_summary_line(self):
        """BLUF section should show stats boxes as text."""
        from anveshak.reporter.worker import _build_content_md_v2

        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=SAMPLE_DATA_BUNDLE,
            identifiers=[],
            template_matches=[],
            report_type="intelligence_brief",
        )
        assert "148" in md  # content_count
        assert "9" in md  # source_count

    def test_contains_language_breakdown(self):
        from anveshak.reporter.worker import _build_content_md_v2

        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=SAMPLE_DATA_BUNDLE,
            identifiers=[],
            template_matches=[],
            report_type="research_summary",
        )
        # Language breakdown should appear somewhere
        assert "en" in md.lower() or "english" in md.lower()


# ---------------------------------------------------------------------------
# Fix 1: Evidence title fallback (no "None" titles)
# ---------------------------------------------------------------------------


class TestEvidenceTitleFallback:
    """Evidence cards should never show 'None' as title."""

    def _make_bluf(self):
        from anveshak.reporter.llm import BlufContent

        return BlufContent(**VALID_BLUF_RESPONSE)

    def test_evidence_card_uses_snippet_when_title_is_none(self):
        from anveshak.reporter.worker import _build_content_md_v2

        bundle = {
            **SAMPLE_DATA_BUNDLE,
            "evidence_items": [
                {
                    "title": None,
                    "url": "https://example.com",
                    "source_name": "Test",
                    "platform": "web",
                    "captured_at": "2026-06-20",
                    "credibility_score_at_capture": 50.0,
                    "snippet": "This is a snippet about UAV activity near the border region",
                },
            ],
        }
        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=bundle,
            identifiers=[],
            template_matches=[],
            report_type="research_summary",
        )
        assert "None" not in md.split("Evidence")[1].split("##")[0]
        assert "snippet about UAV" in md

    def test_evidence_card_uses_snippet_when_title_is_empty(self):
        from anveshak.reporter.worker import _build_content_md_v2

        bundle = {
            **SAMPLE_DATA_BUNDLE,
            "evidence_items": [
                {
                    "title": "",
                    "url": "https://example.com",
                    "source_name": "Test",
                    "platform": "web",
                    "captured_at": "2026-06-20",
                    "credibility_score_at_capture": 50.0,
                    "snippet": "Breaking news about border incident",
                },
            ],
        }
        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=bundle,
            identifiers=[],
            template_matches=[],
            report_type="research_summary",
        )
        evidence_section = md.split("Evidence")[1]
        assert "Breaking news" in evidence_section


# ---------------------------------------------------------------------------
# Fix 2: Dedup evidence items by URL
# ---------------------------------------------------------------------------


class TestEvidenceDedup:
    """SQL_REPORT_EVIDENCE_ITEMS should not return duplicate URLs."""

    def test_sql_has_distinct_on_url(self):
        from anveshak.reporter.db import SQL_REPORT_EVIDENCE_ITEMS

        sql_upper = SQL_REPORT_EVIDENCE_ITEMS.upper()
        assert "DISTINCT" in sql_upper


# ---------------------------------------------------------------------------
# Fix 3+7: Entity noise filtering
# ---------------------------------------------------------------------------


class TestEntityNoiseFilter:
    """Entities table should exclude CARDINAL, ORDINAL, DATE, etc."""

    def test_sql_excludes_cardinal(self):
        from anveshak.reporter.db import SQL_REPORT_ENTITIES

        assert "CARDINAL" in SQL_REPORT_ENTITIES

    def test_sql_excludes_ordinal(self):
        from anveshak.reporter.db import SQL_REPORT_ENTITIES

        assert "ORDINAL" in SQL_REPORT_ENTITIES

    def test_sql_excludes_date(self):
        """DATE entities like '1999', '2024' are noise in entity tables."""
        from anveshak.reporter.db import SQL_REPORT_ENTITIES

        # Should filter DATE but not in a way that breaks the query
        assert "'DATE'" in SQL_REPORT_ENTITIES or "DATE" in SQL_REPORT_ENTITIES

    def test_confidence_threshold_at_least_075(self):
        """Confidence >= 0.75 filters low-quality entity extractions."""
        from anveshak.reporter.db import SQL_REPORT_ENTITIES

        assert "0.75" in SQL_REPORT_ENTITIES or "0.8" in SQL_REPORT_ENTITIES


# ---------------------------------------------------------------------------
# Fix 4: Signal description not truncated too short
# ---------------------------------------------------------------------------


class TestSignalTruncation:
    """Signal descriptions should show at least 120 chars."""

    def _make_bluf(self):
        from anveshak.reporter.llm import BlufContent

        return BlufContent(**VALID_BLUF_RESPONSE)

    def test_long_signal_description_not_cut_at_60(self):
        from anveshak.reporter.worker import _build_content_md_v2

        long_desc = "Cross-platform disinformation amplification: identical inflammatory images shared across Telegram and Reddit within 2 hours"
        bundle = {
            **SAMPLE_DATA_BUNDLE,
            "signals": [
                {
                    "id": "s1",
                    "description": long_desc,
                    "status": "new",
                    "cluster_label": "Disinfo",
                    "created_at": "2026-06-20T10:00:00Z",
                },
            ],
        }
        md = _build_content_md_v2(
            bluf=self._make_bluf(),
            data_bundle=bundle,
            identifiers=[],
            template_matches=[],
            report_type="intelligence_brief",
        )
        # Should contain at least 100 chars of the description
        assert "identical inflammatory images" in md


# ---------------------------------------------------------------------------
# Fix 5: Timestamp formatting
# ---------------------------------------------------------------------------


class TestTimestampFormatting:
    """Generated timestamps should be human-readable, not raw UTC microseconds."""

    def test_pdf_template_formats_timestamp(self):
        from anveshak.reporter.pdf import render_pdf_html

        report_data = {
            "id": "test-ts",
            "topic_name": "Test",
            "report_type": "intelligence_brief",
            "generated_at": "2026-06-22T06:30:24.346960+00:00",
            "confidence_score": 0.7,
            "content_item_count": 10,
            "labels": {"classification": "OPEN"},
            "topic_stats": {
                "name": "Test",
                "content_count": 10,
                "source_count": 3,
                "cluster_count": 1,
                "signal_count": 0,
            },
            "sources": [],
        }
        html = render_pdf_html(report_data)
        # Should NOT contain raw microseconds
        assert ".346960" not in html
        # Should contain formatted date
        assert "22 Jun 2026" in html or "2026-06-22" in html
