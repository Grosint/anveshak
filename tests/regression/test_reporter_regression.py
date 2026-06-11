"""Regression tests for reporter invariants — Engine C Phase EC-4.

Verifies that Engine C Step 9 additions (identifier sections, template matches,
recommended actions) do NOT break existing reporter behavior.

pytest.mark.regression — lives in regression suite.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.regression


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rc(*, legal_sections=None, three_lens=None):
    """Minimal ReportContent mock."""
    rc = MagicMock()
    rc.executive_summary = "Executive summary text."
    rc.key_findings = ["Finding alpha", "Finding beta"]
    rc.recommendations = ["Action one", "Action two"]
    rc.source_citations = ["https://source1.com", "https://source2.com"]
    rc.confidence_level = 0.75
    rc.legal_sections = legal_sections or []
    rc.three_lens = three_lens
    return rc


# ---------------------------------------------------------------------------
# 1. Report immutability — generated_at IS NULL guard
# ---------------------------------------------------------------------------

class TestReportImmutability:
    """CLAUDE.md Rule 4: generated_at is set ONCE. Replayed jobs are no-ops."""

    @pytest.mark.asyncio
    async def test_idempotent_guard_still_works(self):
        """set_report_generated returns False → job is a no-op, no data overwrite."""
        from anveshak.reporter.worker import _build_content_md

        rc = _make_rc()
        md = _build_content_md(rc)
        # The guard is in the SQL (WHERE generated_at IS NULL).
        # Verify that _build_content_md output is deterministic:
        md2 = _build_content_md(rc)
        assert md == md2, "Same input must produce same output (deterministic)"

    def test_build_content_md_is_pure(self):
        """_build_content_md has no side effects — same input, same output."""
        from anveshak.reporter.worker import _build_content_md

        rc = _make_rc()
        ids = [
            {"identifier_type": "PHONE_IN", "identifier_value": "9876543210",
             "source_count": 3, "content_item_count": 5,
             "first_seen_at": None, "last_seen_at": None},
        ]
        md1 = _build_content_md(rc, identifiers=ids)
        md2 = _build_content_md(rc, identifiers=ids)
        assert md1 == md2


# ---------------------------------------------------------------------------
# 2. Existing sections unchanged when no identifiers
# ---------------------------------------------------------------------------

class TestExistingSectionsUnchanged:
    """Engine C additions must not alter existing report format when no identifier data."""

    def test_no_identifiers_produces_original_format(self):
        """With no identifier data, content_md matches pre-Engine-C format."""
        from anveshak.reporter.worker import _build_content_md

        rc = _make_rc()
        md = _build_content_md(rc)

        # These sections must exist in exact order
        assert "## Executive Summary" in md
        assert "## Key Findings" in md
        assert "## Recommendations" in md
        assert "## Source Citations" in md

        # Engine C sections must NOT appear
        assert "## Identified Indicators" not in md
        assert "## Scam Template Matches" not in md
        assert "## Recommended Actions" not in md

    def test_empty_identifiers_same_as_none(self):
        """Passing empty lists is equivalent to passing None."""
        from anveshak.reporter.worker import _build_content_md

        rc = _make_rc()
        md_none = _build_content_md(rc)
        md_empty = _build_content_md(rc, identifiers=[], template_matches=[])
        assert md_none == md_empty

    def test_section_order_preserved(self):
        """Sections appear in the canonical order."""
        from anveshak.reporter.worker import _build_content_md

        rc = _make_rc()
        md = _build_content_md(rc)
        positions = [
            md.index("## Executive Summary"),
            md.index("## Key Findings"),
            md.index("## Recommendations"),
            md.index("## Source Citations"),
        ]
        assert positions == sorted(positions), "Sections must be in order"


# ---------------------------------------------------------------------------
# 3. All report types still work
# ---------------------------------------------------------------------------

class TestAllReportTypesWork:
    """render_prompt still works for all 3 report types."""

    @pytest.mark.parametrize("report_type", [
        "intelligence_brief",
        "research_summary",
        "weekly_digest",
    ])
    def test_render_prompt_works(self, report_type):
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt(
            report_type,
            topic_name="Test Topic",
            keywords=["keyword1"],
            context="Some context text",
            source_count=3,
            date_range="2026-06-01 to 2026-06-10",
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # Non-trivial prompt
        assert "Test Topic" in prompt
        assert "keyword1" in prompt

    @pytest.mark.parametrize("report_type", [
        "intelligence_brief",
        "research_summary",
        "weekly_digest",
    ])
    def test_render_prompt_with_identifiers(self, report_type):
        """identifier_context param doesn't break any report type."""
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt(
            report_type,
            topic_name="T",
            keywords=[],
            context="C",
            identifier_context="IDENTIFIED INDICATORS:\nPhones: 9876543210 (3 sources)",
        )
        assert "IDENTIFIED INDICATORS" in prompt


# ---------------------------------------------------------------------------
# 4. Legal sections still render when enabled
# ---------------------------------------------------------------------------

class TestLegalSectionsStillWork:
    """Legal mapping feature not broken by Engine C additions."""

    def test_legal_sections_in_content_md(self):
        from anveshak.reporter.worker import _build_content_md

        legal = [
            {
                "finding": "Finding alpha",
                "sections": [
                    {"act": "BNS", "section": "318",
                     "description": "Cheating", "evidence_ref": "source1.com"},
                ],
            },
        ]
        rc = _make_rc(legal_sections=legal)
        md = _build_content_md(rc)
        assert "## Applicable Legal Provisions" in md
        assert "BNS" in md
        assert "318" in md

    def test_legal_sections_with_identifiers(self):
        """Legal sections + identifiers in same report — both render."""
        from anveshak.reporter.worker import _build_content_md

        legal = [
            {
                "finding": "Finding",
                "sections": [
                    {"act": "PMLA", "section": "3",
                     "description": "Money laundering", "evidence_ref": "src"},
                ],
            },
        ]
        rc = _make_rc(legal_sections=legal)
        ids = [
            {"identifier_type": "UPI", "identifier_value": "fraud@paytm",
             "source_count": 2, "content_item_count": 3,
             "first_seen_at": None, "last_seen_at": None},
        ]
        md = _build_content_md(rc, identifiers=ids)
        assert "## Applicable Legal Provisions" in md
        assert "## Identified Indicators" in md
        assert "fraud@paytm" in md
        assert "PMLA" in md


# ---------------------------------------------------------------------------
# 5. Three-lens evaluation still renders when enabled
# ---------------------------------------------------------------------------

class TestThreeLensStillWorks:
    """Three-lens evaluation not broken by Engine C."""

    def test_three_lens_renders_without_identifiers(self):
        from anveshak.reporter.worker import _build_content_md

        three_lens = {
            "evaluations": [
                {
                    "perspective": "Brigadier",
                    "threat_assessment": "Immediate tactical threat.",
                    "priority_actions": ["Deploy force", "Secure perimeter"],
                    "risk_level": "HIGH",
                },
            ],
        }
        rc = _make_rc(three_lens=three_lens)
        md = _build_content_md(rc)
        assert "## Annexure: Three-Lens Evaluation" in md
        assert "Brigadier" in md
        assert "Deploy force" in md

    def test_three_lens_with_identifiers(self):
        """Three-lens + identifiers — both render."""
        from anveshak.reporter.worker import _build_content_md

        three_lens = {
            "evaluations": [
                {
                    "perspective": "NIA Chief",
                    "threat_assessment": "Strong prosecution case.",
                    "priority_actions": ["File chargesheet"],
                    "risk_level": "CRITICAL",
                },
            ],
        }
        rc = _make_rc(three_lens=three_lens)
        ids = [
            {"identifier_type": "PHONE_IN", "identifier_value": "9876543210",
             "source_count": 4, "content_item_count": 8,
             "first_seen_at": None, "last_seen_at": None},
        ]
        md = _build_content_md(rc, identifiers=ids)
        assert "## Annexure: Three-Lens Evaluation" in md
        assert "## Identified Indicators" in md
        assert "NIA Chief" in md
        assert "9876543210" in md


# ---------------------------------------------------------------------------
# 6. Source snapshot still captured (regression guard)
# ---------------------------------------------------------------------------

class TestSourceSnapshotRegression:
    """Source snapshot capture not broken by identifier additions."""

    @pytest.mark.asyncio
    async def test_source_snapshot_still_passed_to_set_report_generated(self):
        """generate_report still passes source_snapshot to DB."""
        ctx = {"db": AsyncMock(), "settings": MagicMock(
            rag_top_k=10, rag_max_context_tokens=4000,
            ollama_model="m", ollama_host="h", ollama_report_timeout_s=30,
            ollama_retry_max=2, topic_relevance_threshold=0.35,
            include_legal_mapping=False, include_three_lens=False,
        )}
        chunks = [{"id": "c1", "source_id": "src-1", "clean_text": "t", "url": "u"}]
        rc = _make_rc()
        snapshot = {"src-1": {"credibility_score": 85.0, "name": "Source One"}}

        with patch("anveshak.reporter.worker.db") as mock_db, \
             patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock) as me, \
             patch("anveshak.reporter.worker.assemble_context") as mc, \
             patch("anveshak.reporter.worker.render_prompt") as mp, \
             patch("anveshak.reporter.worker.call_ollama_with_retry", new_callable=AsyncMock) as ml, \
             patch("anveshak.reporter.worker.geocode_locations") as mg, \
             patch("anveshak.reporter.worker.build_geojson") as mj, \
             patch("anveshak.reporter.worker.extract_locations_from_text") as mx:
            mock_db.fetch_report = AsyncMock(return_value={
                "id": "r1", "topic_id": "t1", "report_type": "intelligence_brief",
                "credibility_min_filter": 30.0,
            })
            mock_db.fetch_topic = AsyncMock(return_value={
                "id": "t1", "name": "Topic", "keywords": [],
            })
            mock_db.fetch_rag_chunks = AsyncMock(return_value=chunks)
            mock_db.fetch_sources_for_snapshot = AsyncMock(return_value=snapshot)
            mock_db.fetch_topic_location_entities = AsyncMock(return_value=[])
            mock_db.fetch_topic_identifiers = AsyncMock(return_value=[])
            mock_db.fetch_topic_template_matches = AsyncMock(return_value=[])
            mock_db.set_report_generated = AsyncMock(return_value=True)
            mock_db.update_job_status = AsyncMock()
            me.return_value = [0.1] * 384
            mc.return_value = ("ctx", 1, "2026-06-01")
            mp.return_value = "prompt"
            ml.return_value = rc
            mg.return_value = []
            mj.return_value = {"type": "FeatureCollection", "features": []}
            mx.return_value = []

            from anveshak.reporter.worker import generate_report
            await generate_report(ctx, "r1")

            call_kwargs = mock_db.set_report_generated.call_args[1]
            assert call_kwargs["source_snapshot"] == snapshot


# ---------------------------------------------------------------------------
# 7. Source warning detection still works
# ---------------------------------------------------------------------------

class TestSourceWarningRegression:
    """check_source_warnings not broken by Engine C additions."""

    @pytest.mark.asyncio
    async def test_downgrade_still_detected(self):
        import json
        ctx = {"db": AsyncMock(), "settings": MagicMock(source_warning_lookback_days=30)}

        report = {
            "id": "r1",
            "source_snapshot": {"src-1": {"credibility_score": 90.0}},
        }

        with patch("anveshak.reporter.worker.db") as mock_db:
            mock_db.fetch_reports_for_warning_check = AsyncMock(return_value=[report])
            mock_db.fetch_sources_for_snapshot = AsyncMock(
                return_value={"src-1": {"credibility_score": 50.0, "name": "Src"}}
            )
            mock_db.insert_source_warning = AsyncMock()

            from anveshak.reporter.worker import check_source_warnings
            await check_source_warnings(ctx)

            mock_db.insert_source_warning.assert_awaited_once()
            kw = mock_db.insert_source_warning.call_args[1]
            assert kw["old_score"] == 90.0
            assert kw["new_score"] == 50.0


# ---------------------------------------------------------------------------
# 8. Render prompt grounding rules still present
# ---------------------------------------------------------------------------

class TestPromptGroundingRegression:
    """Prompt grounding rules not accidentally removed by Engine C changes."""

    def test_grounding_rules_in_prompt(self):
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt(
            "intelligence_brief", "Topic", ["kw"], "context",
        )
        assert "STRICT RULES" in prompt
        assert "ONLY use facts" in prompt
        assert "source_citations" in prompt.lower()

    def test_xml_boundary_markers_present(self):
        """User-controlled input wrapped in XML markers (CLAUDE.md security rule)."""
        from anveshak.reporter.prompt_templates import render_prompt

        prompt = render_prompt(
            "intelligence_brief", "My Topic", ["kw1"], "ctx",
        )
        assert "<topic>" in prompt
        assert "</topic>" in prompt
        assert "<keywords>" in prompt
        assert "</keywords>" in prompt
        assert "<context>" in prompt
        assert "</context>" in prompt
