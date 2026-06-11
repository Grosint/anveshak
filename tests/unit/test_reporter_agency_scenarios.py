"""Unit tests for 4 agency scenario reports — Engine C Phase EC-4.

Each test verifies that generate_report produces correct content_md
for a specific agency context (MEA, Police, SEBI, NCB) with
appropriate templates, identifiers, legal sections, and actions.

pytest.mark.unit — mocks all DB/LLM calls, no external dependencies.
"""
from __future__ import annotations

from datetime import datetime, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Shared factories
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
    s.include_legal_mapping = True
    s.include_three_lens = False
    return s


def _make_ctx(settings=None):
    s = settings or _make_settings()
    return {"db": AsyncMock(), "settings": s}


def _make_rc(summary="Summary.", findings=None, recs=None, citations=None):
    """Build a mock ReportContent matching Pydantic model shape."""
    rc = MagicMock()
    rc.executive_summary = summary
    rc.key_findings = findings or ["Finding 1"]
    rc.recommendations = recs or ["Recommendation 1"]
    rc.source_citations = citations or ["https://example.com"]
    rc.confidence_level = 0.80
    rc.legal_sections = []
    rc.three_lens = None
    return rc


def _make_chunk(source_id="src-1"):
    return {
        "id": "chunk-1",
        "source_id": source_id,
        "clean_text": "Content text.",
        "url": "https://example.com",
    }


def _patch_worker(mock_db, mock_embed, mock_ctx, mock_prompt, mock_llm,
                   mock_geo, mock_geojson, mock_extract, mock_id_ctx,
                   *, report_row, topic_row, chunks, rc, identifiers, template_matches):
    """Wire up all worker mocks for a generate_report call."""
    mock_db.fetch_report = AsyncMock(return_value=report_row)
    mock_db.fetch_topic = AsyncMock(return_value=topic_row)
    mock_db.fetch_rag_chunks = AsyncMock(return_value=chunks)
    mock_db.fetch_sources_for_snapshot = AsyncMock(return_value={})
    mock_db.fetch_topic_location_entities = AsyncMock(return_value=[])
    mock_db.fetch_topic_identifiers = AsyncMock(return_value=identifiers)
    mock_db.fetch_topic_template_matches = AsyncMock(return_value=template_matches)
    mock_db.set_report_generated = AsyncMock(return_value=True)
    mock_db.update_job_status = AsyncMock()
    mock_embed.return_value = [0.1] * 384
    mock_ctx.return_value = ("context", 3, "2026-06-01 to 2026-06-10")
    mock_prompt.return_value = "prompt"
    mock_llm.return_value = rc
    mock_geo.return_value = []
    mock_geojson.return_value = {"type": "FeatureCollection", "features": []}
    mock_extract.return_value = []
    mock_id_ctx.return_value = "IDENTIFIED INDICATORS..."


async def _run_generate_report(ctx, report_id, *, report_row, topic_row,
                                chunks, rc, identifiers, template_matches):
    """Execute generate_report with full mock wiring, return content_md."""
    with patch("anveshak.reporter.worker.db") as mock_db, \
         patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock) as mock_embed, \
         patch("anveshak.reporter.worker.assemble_context") as mock_ctx, \
         patch("anveshak.reporter.worker.render_prompt") as mock_prompt, \
         patch("anveshak.reporter.worker.call_ollama_with_retry", new_callable=AsyncMock) as mock_llm, \
         patch("anveshak.reporter.worker.geocode_locations") as mock_geo, \
         patch("anveshak.reporter.worker.build_geojson") as mock_geojson, \
         patch("anveshak.reporter.worker.extract_locations_from_text") as mock_extract, \
         patch("anveshak.reporter.worker.assemble_identifier_context") as mock_id_ctx:

        _patch_worker(mock_db, mock_embed, mock_ctx, mock_prompt, mock_llm,
                      mock_geo, mock_geojson, mock_extract, mock_id_ctx,
                      report_row=report_row, topic_row=topic_row,
                      chunks=chunks, rc=rc,
                      identifiers=identifiers,
                      template_matches=template_matches)

        from anveshak.reporter.worker import generate_report
        await generate_report(ctx, report_id)

        assert mock_db.set_report_generated.await_count == 1
        return mock_db.set_report_generated.call_args[1]["content_md"]


# ---------------------------------------------------------------------------
# Agency-specific identifier + template data
# ---------------------------------------------------------------------------

_POLICE_IDENTIFIERS = [
    {"identifier_type": "PHONE_IN", "identifier_value": "9876543210",
     "source_count": 5, "content_item_count": 12,
     "first_seen_at": datetime(2026, 6, 1, tzinfo=UTC),
     "last_seen_at": datetime(2026, 6, 10, tzinfo=UTC)},
    {"identifier_type": "UPI", "identifier_value": "mule123@paytm",
     "source_count": 4, "content_item_count": 8,
     "first_seen_at": datetime(2026, 6, 2, tzinfo=UTC),
     "last_seen_at": datetime(2026, 6, 9, tzinfo=UTC)},
]

_POLICE_TEMPLATES = [
    {"template_name": "mule_recruitment", "template_display": "Mule Account Recruitment",
     "confidence": 0.85, "severity": "CRITICAL",
     "legal_sections": ["PMLA Section 3", "PMLA Section 4"], "match_count": 5},
    {"template_name": "digital_arrest", "template_display": "Digital Arrest Scam",
     "confidence": 0.72, "severity": "HIGH",
     "legal_sections": ["BNS 318", "IT Act 66D"], "match_count": 3},
]

_SEBI_IDENTIFIERS = [
    {"identifier_type": "SEBI_REG", "identifier_value": "INZ000123456",
     "source_count": 3, "content_item_count": 6,
     "first_seen_at": datetime(2026, 6, 3, tzinfo=UTC),
     "last_seen_at": datetime(2026, 6, 10, tzinfo=UTC)},
    {"identifier_type": "TELEGRAM_HANDLE", "identifier_value": "stocktips_guru",
     "source_count": 4, "content_item_count": 10,
     "first_seen_at": datetime(2026, 6, 1, tzinfo=UTC),
     "last_seen_at": datetime(2026, 6, 10, tzinfo=UTC)},
]

_SEBI_TEMPLATES = [
    {"template_name": "pump_and_dump", "template_display": "Pump and Dump",
     "confidence": 0.90, "severity": "CRITICAL",
     "legal_sections": ["SEBI (PFUTP) Regulations"], "match_count": 7},
    {"template_name": "fake_research_report", "template_display": "Fake Research Report",
     "confidence": 0.68, "severity": "HIGH",
     "legal_sections": ["SEBI Act Section 12A"], "match_count": 2},
]

_NCB_IDENTIFIERS = [
    {"identifier_type": "TELEGRAM_HANDLE", "identifier_value": "dealer_420",
     "source_count": 6, "content_item_count": 15,
     "first_seen_at": datetime(2026, 6, 1, tzinfo=UTC),
     "last_seen_at": datetime(2026, 6, 10, tzinfo=UTC)},
    {"identifier_type": "CRYPTO_TRC20", "identifier_value": "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
     "source_count": 3, "content_item_count": 5,
     "first_seen_at": datetime(2026, 6, 4, tzinfo=UTC),
     "last_seen_at": datetime(2026, 6, 9, tzinfo=UTC)},
]

_NCB_TEMPLATES = [
    {"template_name": "drug_sale", "template_display": "Drug Sale",
     "confidence": 0.88, "severity": "HIGH",
     "legal_sections": ["NDPS Act Section 20", "NDPS Act Section 22", "NDPS Act Section 25"],
     "match_count": 8},
    {"template_name": "drug_delivery_recruitment",
     "template_display": "Drug Delivery Recruitment",
     "confidence": 0.65, "severity": "HIGH",
     "legal_sections": ["NDPS Act Section 27A"], "match_count": 2},
]

_MEA_IDENTIFIERS = [
    {"identifier_type": "URL_DOMAIN", "identifier_value": "globaltimes.cn",
     "source_count": 8, "content_item_count": 20,
     "first_seen_at": datetime(2026, 5, 15, tzinfo=UTC),
     "last_seen_at": datetime(2026, 6, 10, tzinfo=UTC)},
    {"identifier_type": "TELEGRAM_HANDLE", "identifier_value": "cn_news_daily",
     "source_count": 5, "content_item_count": 12,
     "first_seen_at": datetime(2026, 5, 20, tzinfo=UTC),
     "last_seen_at": datetime(2026, 6, 8, tzinfo=UTC)},
]

# MEA uses info_op templates — no domestic legal provisions
_MEA_TEMPLATES = []  # Custom templates not in _TEMPLATE_ACTIONS, so no auto-actions


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPoliceScenario:
    """Police Cyber Cell: mule recruitment + digital arrest, PMLA/BNS legal sections."""

    @pytest.mark.asyncio
    async def test_police_report_includes_mule_identifiers(self):
        ctx = _make_ctx()
        md = await _run_generate_report(
            ctx, "rpt-police",
            report_row={"id": "rpt-police", "topic_id": "topic-police",
                        "report_type": "intelligence_brief", "credibility_min_filter": 30.0},
            topic_row={"id": "topic-police", "name": "Cyber Fraud Investigation", "keywords": ["mule", "fraud"]},
            chunks=[_make_chunk()],
            rc=_make_rc(summary="Active mule recruitment network detected."),
            identifiers=_POLICE_IDENTIFIERS,
            template_matches=_POLICE_TEMPLATES,
        )
        assert "## Identified Indicators" in md
        assert "9876543210" in md
        assert "mule123@paytm" in md

    @pytest.mark.asyncio
    async def test_police_report_includes_pmla_actions(self):
        ctx = _make_ctx()
        md = await _run_generate_report(
            ctx, "rpt-police",
            report_row={"id": "rpt-police", "topic_id": "topic-police",
                        "report_type": "intelligence_brief", "credibility_min_filter": 30.0},
            topic_row={"id": "topic-police", "name": "Cyber Fraud", "keywords": ["mule"]},
            chunks=[_make_chunk()],
            rc=_make_rc(),
            identifiers=_POLICE_IDENTIFIERS,
            template_matches=_POLICE_TEMPLATES,
        )
        assert "## Recommended Actions" in md
        md_lower = md.lower()
        assert "pmla" in md_lower
        assert "freeze" in md_lower or "block" in md_lower

    @pytest.mark.asyncio
    async def test_police_report_includes_both_template_matches(self):
        ctx = _make_ctx()
        md = await _run_generate_report(
            ctx, "rpt-police",
            report_row={"id": "rpt-police", "topic_id": "topic-police",
                        "report_type": "intelligence_brief", "credibility_min_filter": 30.0},
            topic_row={"id": "topic-police", "name": "Fraud", "keywords": ["fraud"]},
            chunks=[_make_chunk()],
            rc=_make_rc(),
            identifiers=_POLICE_IDENTIFIERS,
            template_matches=_POLICE_TEMPLATES,
        )
        assert "Mule Account Recruitment" in md
        assert "Digital Arrest" in md
        assert "CRITICAL" in md


class TestSEBIScenario:
    """SEBI Surveillance: pump-and-dump + fake research, PFUTP regulations."""

    @pytest.mark.asyncio
    async def test_sebi_report_includes_sebi_identifiers(self):
        ctx = _make_ctx()
        md = await _run_generate_report(
            ctx, "rpt-sebi",
            report_row={"id": "rpt-sebi", "topic_id": "topic-sebi",
                        "report_type": "intelligence_brief", "credibility_min_filter": 30.0},
            topic_row={"id": "topic-sebi", "name": "Market Manipulation", "keywords": ["pump", "dump"]},
            chunks=[_make_chunk()],
            rc=_make_rc(summary="Pump-and-dump scheme targeting micro-cap stock."),
            identifiers=_SEBI_IDENTIFIERS,
            template_matches=_SEBI_TEMPLATES,
        )
        assert "INZ000123456" in md
        assert "stocktips_guru" in md

    @pytest.mark.asyncio
    async def test_sebi_report_includes_pfutp_actions(self):
        ctx = _make_ctx()
        md = await _run_generate_report(
            ctx, "rpt-sebi",
            report_row={"id": "rpt-sebi", "topic_id": "topic-sebi",
                        "report_type": "intelligence_brief", "credibility_min_filter": 30.0},
            topic_row={"id": "topic-sebi", "name": "Market Manipulation", "keywords": ["pump"]},
            chunks=[_make_chunk()],
            rc=_make_rc(),
            identifiers=_SEBI_IDENTIFIERS,
            template_matches=_SEBI_TEMPLATES,
        )
        assert "## Recommended Actions" in md
        md_lower = md.lower()
        assert "sebi" in md_lower

    @pytest.mark.asyncio
    async def test_sebi_report_template_matches(self):
        ctx = _make_ctx()
        md = await _run_generate_report(
            ctx, "rpt-sebi",
            report_row={"id": "rpt-sebi", "topic_id": "topic-sebi",
                        "report_type": "intelligence_brief", "credibility_min_filter": 30.0},
            topic_row={"id": "topic-sebi", "name": "Market", "keywords": []},
            chunks=[_make_chunk()],
            rc=_make_rc(),
            identifiers=_SEBI_IDENTIFIERS,
            template_matches=_SEBI_TEMPLATES,
        )
        assert "Pump and Dump" in md
        assert "Fake Research Report" in md


class TestNCBScenario:
    """NCB Intelligence: drug sale + delivery recruitment, NDPS legal sections."""

    @pytest.mark.asyncio
    async def test_ncb_report_includes_narco_identifiers(self):
        ctx = _make_ctx()
        md = await _run_generate_report(
            ctx, "rpt-ncb",
            report_row={"id": "rpt-ncb", "topic_id": "topic-ncb",
                        "report_type": "intelligence_brief", "credibility_min_filter": 30.0},
            topic_row={"id": "topic-ncb", "name": "Dark Web Drug Network", "keywords": ["drug", "narco"]},
            chunks=[_make_chunk()],
            rc=_make_rc(summary="Drug sales channel detected on Telegram."),
            identifiers=_NCB_IDENTIFIERS,
            template_matches=_NCB_TEMPLATES,
        )
        assert "dealer_420" in md
        assert "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb" in md

    @pytest.mark.asyncio
    async def test_ncb_report_includes_ndps_actions(self):
        ctx = _make_ctx()
        md = await _run_generate_report(
            ctx, "rpt-ncb",
            report_row={"id": "rpt-ncb", "topic_id": "topic-ncb",
                        "report_type": "intelligence_brief", "credibility_min_filter": 30.0},
            topic_row={"id": "topic-ncb", "name": "Drug Network", "keywords": ["drug"]},
            chunks=[_make_chunk()],
            rc=_make_rc(),
            identifiers=_NCB_IDENTIFIERS,
            template_matches=_NCB_TEMPLATES,
        )
        assert "## Recommended Actions" in md
        md_lower = md.lower()
        assert "ndps" in md_lower
        assert "ncb" in md_lower or "controlled delivery" in md_lower

    @pytest.mark.asyncio
    async def test_ncb_report_template_matches(self):
        ctx = _make_ctx()
        md = await _run_generate_report(
            ctx, "rpt-ncb",
            report_row={"id": "rpt-ncb", "topic_id": "topic-ncb",
                        "report_type": "intelligence_brief", "credibility_min_filter": 30.0},
            topic_row={"id": "topic-ncb", "name": "Drug", "keywords": []},
            chunks=[_make_chunk()],
            rc=_make_rc(),
            identifiers=_NCB_IDENTIFIERS,
            template_matches=_NCB_TEMPLATES,
        )
        assert "Drug Sale" in md
        assert "Drug Delivery Recruitment" in md


class TestMEAScenario:
    """MEA Info Ops: domain/handle identifiers, NO domestic legal actions."""

    @pytest.mark.asyncio
    async def test_mea_report_includes_domain_identifiers(self):
        ctx = _make_ctx()
        md = await _run_generate_report(
            ctx, "rpt-mea",
            report_row={"id": "rpt-mea", "topic_id": "topic-mea",
                        "report_type": "intelligence_brief", "credibility_min_filter": 30.0},
            topic_row={"id": "topic-mea", "name": "Anti-India Narratives Beijing",
                        "keywords": ["Arunachal", "South Tibet"]},
            chunks=[_make_chunk()],
            rc=_make_rc(summary="Coordinated anti-India territorial narrative from Chinese state media."),
            identifiers=_MEA_IDENTIFIERS,
            template_matches=_MEA_TEMPLATES,
        )
        assert "## Identified Indicators" in md
        assert "globaltimes.cn" in md
        assert "cn_news_daily" in md

    @pytest.mark.asyncio
    async def test_mea_report_no_domestic_legal_actions(self):
        """MEA info_op templates have no _TEMPLATE_ACTIONS entry → no recommended actions."""
        ctx = _make_ctx()
        md = await _run_generate_report(
            ctx, "rpt-mea",
            report_row={"id": "rpt-mea", "topic_id": "topic-mea",
                        "report_type": "intelligence_brief", "credibility_min_filter": 30.0},
            topic_row={"id": "topic-mea", "name": "Anti-India", "keywords": []},
            chunks=[_make_chunk()],
            rc=_make_rc(),
            identifiers=_MEA_IDENTIFIERS,
            template_matches=_MEA_TEMPLATES,
        )
        # No template matches → no template section, no actions
        assert "## Recommended Actions" not in md
        assert "## Scam Template Matches" not in md

    @pytest.mark.asyncio
    async def test_mea_report_preserves_standard_sections(self):
        ctx = _make_ctx()
        md = await _run_generate_report(
            ctx, "rpt-mea",
            report_row={"id": "rpt-mea", "topic_id": "topic-mea",
                        "report_type": "intelligence_brief", "credibility_min_filter": 30.0},
            topic_row={"id": "topic-mea", "name": "MEA Topic", "keywords": []},
            chunks=[_make_chunk()],
            rc=_make_rc(),
            identifiers=_MEA_IDENTIFIERS,
            template_matches=_MEA_TEMPLATES,
        )
        assert "## Executive Summary" in md
        assert "## Key Findings" in md
        assert "## Recommendations" in md
        assert "## Source Citations" in md
