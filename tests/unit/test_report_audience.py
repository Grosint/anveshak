"""Unit tests for report audience action sets - issue #57.

A report is addressed to a service. The same matched template produces
prosecution steps for a police cyber cell and assessment tasks for an
intelligence consumer, and neither borrows the other's set.

pytest.mark.unit - reads the versioned config file, no external dependencies.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_audience_cache():
    """load_audiences is lru_cached, so a test that points it at a temp file
    would otherwise leave that file's contents cached for every later test."""
    from anveshak.reporter import audience as audience_module

    audience_module.load_audiences.cache_clear()
    yield
    audience_module.load_audiences.cache_clear()


def _match(name: str, display: str = "Display", legal: list[str] | None = None) -> dict:
    return {
        "template_name": name,
        "template_display": display,
        "confidence": 0.8,
        "severity": "HIGH",
        "legal_sections": legal if legal is not None else ["PMLA Section 3"],
        "match_count": 4,
    }


# ---------------------------------------------------------------------------
# Config file
# ---------------------------------------------------------------------------


class TestAudienceConfig:
    def test_config_loads_with_a_version_and_owner(self):
        from anveshak.reporter.audience import load_audiences

        config = load_audiences()
        assert config.version >= 1
        assert config.owner
        assert config.audiences

    def test_default_audience_is_prosecution(self):
        """Backward compatible: a report with no stated audience reads as before."""
        from anveshak.reporter.audience import load_audiences

        assert load_audiences().default_audience == "prosecution"

    def test_both_audiences_cover_the_same_templates(self):
        """A template covered for one audience and not another is a silent gap."""
        from anveshak.reporter.audience import load_audiences

        config = load_audiences()
        prosecution = set(config.audiences["prosecution"].template_actions)
        advisory = set(config.audiences["advisory"].template_actions)
        assert prosecution == advisory

    def test_advisory_actions_carry_no_prosecution_verbs(self):
        """An intelligence consumer cannot file, freeze, seize or arrest."""
        from anveshak.reporter.audience import load_audiences

        advisory = load_audiences().audiences["advisory"]
        text = " ".join(a for acts in advisory.template_actions.values() for a in acts).lower()
        for verb in ("file an fir", "file fir", "file case", "file str", "freeze", "arrest"):
            assert verb not in text, f"advisory action set uses a power it does not have: {verb}"


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


class TestResolveAudience:
    def test_none_resolves_to_the_configured_default(self):
        from anveshak.reporter.audience import resolve_audience

        assert resolve_audience(None).id == "prosecution"

    def test_known_id_resolves_to_that_audience(self):
        from anveshak.reporter.audience import resolve_audience

        assert resolve_audience("advisory").id == "advisory"

    def test_unknown_id_resolves_to_nothing(self):
        """Deny by default: an unrecognised audience never borrows another's actions."""
        from anveshak.reporter.audience import resolve_audience

        assert resolve_audience("interpol") is None


# ---------------------------------------------------------------------------
# build_recommended_actions
# ---------------------------------------------------------------------------


class TestActionsPerAudience:
    def test_prosecution_actions_are_unchanged(self):
        from anveshak.reporter.rag import build_recommended_actions

        actions = build_recommended_actions([_match("mule_recruitment", "Mule Recruitment")])
        assert "Freeze identified bank accounts and UPI IDs under PMLA Section 17" in actions

    def test_same_template_yields_different_actions_per_audience(self):
        from anveshak.reporter.audience import resolve_audience
        from anveshak.reporter.rag import build_recommended_actions

        matches = [_match("drug_sale", "Drug Sale", ["NDPS Act Section 20"])]
        prosecution = build_recommended_actions(matches, resolve_audience("prosecution"))
        advisory = build_recommended_actions(matches, resolve_audience("advisory"))

        assert prosecution and advisory
        assert set(prosecution).isdisjoint(set(advisory))
        assert any("controlled delivery" in a for a in prosecution)
        assert any("Map the supply network" in a for a in advisory)

    def test_advisory_never_borrows_a_prosecution_action(self):
        from anveshak.reporter.audience import load_audiences, resolve_audience
        from anveshak.reporter.rag import build_recommended_actions

        prosecution_actions = {
            a
            for acts in load_audiences().audiences["prosecution"].template_actions.values()
            for a in acts
        }
        for template in load_audiences().audiences["advisory"].template_actions:
            actions = build_recommended_actions([_match(template)], resolve_audience("advisory"))
            assert prosecution_actions.isdisjoint(set(actions))

    def test_unmapped_template_for_an_audience_yields_no_actions(self):
        """No action set for this template means no actions, not the default set."""
        from anveshak.reporter.audience import ReportAudience
        from anveshak.reporter.rag import build_recommended_actions

        sparse = ReportAudience(
            id="sparse",
            label="Sparse",
            actions_heading="Recommended Actions",
            legal_provisions="omitted",
            template_actions={},
        )
        assert build_recommended_actions([_match("mule_recruitment")], sparse) == []

    def test_unknown_audience_yields_no_actions(self):
        from anveshak.reporter.audience import resolve_audience
        from anveshak.reporter.rag import build_recommended_actions

        actions = build_recommended_actions([_match("mule_recruitment")], resolve_audience("mi6"))
        assert actions == []

    def test_empty_matches_yield_no_actions(self):
        from anveshak.reporter.rag import build_recommended_actions

        assert build_recommended_actions([]) == []


class TestLegalProvisionsPerAudience:
    def test_prosecution_gets_the_provisions_as_its_own(self):
        from anveshak.reporter.audience import resolve_audience
        from anveshak.reporter.rag import build_recommended_actions

        actions = build_recommended_actions(
            [_match("drug_sale", "Drug Sale", ["NDPS Act Section 20"])],
            resolve_audience("prosecution"),
        )
        assert any(a.startswith("Applicable legal provisions for Drug Sale:") for a in actions)

    def test_advisory_gets_the_provisions_attributed_elsewhere(self):
        from anveshak.reporter.audience import resolve_audience
        from anveshak.reporter.rag import build_recommended_actions

        actions = build_recommended_actions(
            [_match("drug_sale", "Drug Sale", ["NDPS Act Section 20"])],
            resolve_audience("advisory"),
        )
        joined = " ".join(actions)
        assert "Applicable legal provisions for" not in joined
        assert "NDPS Act Section 20" in joined
        assert "another agency" in joined

    def test_omitted_drops_the_provisions_entirely(self):
        from anveshak.reporter.audience import ReportAudience
        from anveshak.reporter.rag import build_recommended_actions

        silent = ReportAudience(
            id="silent",
            label="Silent",
            actions_heading="Recommended Actions",
            legal_provisions="omitted",
            template_actions={"drug_sale": ("Assess the network",)},
        )
        actions = build_recommended_actions(
            [_match("drug_sale", "Drug Sale", ["NDPS Act Section 20"])], silent
        )
        assert actions == ["Assess the network"]

    def test_missing_legal_sections_do_not_crash(self):
        from anveshak.reporter.rag import build_recommended_actions

        actions = build_recommended_actions([_match("mule_recruitment", "Mule", [])])
        assert len(actions) == 3


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestOrgAudienceColumn:
    def test_migration_gives_an_organisation_a_report_audience(self):
        from tests.helpers.migrations import migrations_sql

        assert "ADD COLUMN IF NOT EXISTS report_audience" in migrations_sql()

    def test_the_topic_fetch_carries_the_organisation_audience(self):
        """The audience rides along on the topic row, so no extra round trip."""
        from anveshak.reporter.db import SQL_FETCH_TOPIC

        assert "o.report_audience AS org_report_audience" in SQL_FETCH_TOPIC
        assert "LEFT JOIN organizations" in SQL_FETCH_TOPIC


# ---------------------------------------------------------------------------
# A hand-edited file that is wrong
# ---------------------------------------------------------------------------


class TestMalformedConfig:
    """A typo in a customer-edited file must not wedge every report.

    The actions block is additive to a report that is complete without it, so
    the loader degrades and logs rather than raising into generate_report,
    which would leave the row at generated_at IS NULL forever.
    """

    def _load_from(self, monkeypatch, tmp_path, text: str):
        from anveshak.reporter import audience as audience_module

        path = tmp_path / "report_actions.yaml"
        path.write_text(text)
        monkeypatch.setattr(audience_module.settings, "report_audience_config_path", str(path))
        audience_module.load_audiences.cache_clear()
        return audience_module.load_audiences()

    def test_unparseable_yaml_yields_no_audiences(self, monkeypatch, tmp_path):
        config = self._load_from(monkeypatch, tmp_path, "audiences: [unclosed\n  - :::")
        assert config.audiences == {}

    def test_a_file_that_is_not_a_mapping_yields_no_audiences(self, monkeypatch, tmp_path):
        config = self._load_from(monkeypatch, tmp_path, "- just\n- a\n- list\n")
        assert config.audiences == {}

    def test_an_entry_with_no_id_is_skipped_and_the_rest_survive(self, monkeypatch, tmp_path):
        config = self._load_from(
            monkeypatch,
            tmp_path,
            """
version: 1
default_audience: good
audiences:
  - label: No id here
    templates:
      drug_sale: [Do a thing]
  - id: good
    templates:
      drug_sale: [Do the right thing]
""",
        )
        assert sorted(config.audiences) == ["good"]

    def test_a_non_integer_version_reads_as_zero(self, monkeypatch, tmp_path):
        config = self._load_from(
            monkeypatch, tmp_path, "version: one\ndefault_audience: x\naudiences: []\n"
        )
        assert config.version == 0

    def test_a_missing_file_yields_no_audiences(self, monkeypatch, tmp_path):
        from anveshak.reporter import audience as audience_module

        monkeypatch.setattr(
            audience_module.settings,
            "report_audience_config_path",
            str(tmp_path / "absent.yaml"),
        )
        monkeypatch.setattr(audience_module, "_resolve_config_path", lambda: None)
        audience_module.load_audiences.cache_clear()
        config = audience_module.load_audiences()
        assert config.audiences == {}
        assert audience_module.resolve_audience(None) is None


# ---------------------------------------------------------------------------
# The PDF is the deliverable, so the framing has to survive into it
# ---------------------------------------------------------------------------


class TestActionsReachThePdf:
    _MATCHES = [
        {
            "template_name": "mule_recruitment",
            "template_display": "Mule Account Recruitment",
            "confidence": 0.85,
            "severity": "CRITICAL",
            "legal_sections": ["PMLA Section 3"],
            "match_count": 5,
        }
    ]

    def _markdown_for(self, audience_id: str) -> str:
        from anveshak.reporter.audience import resolve_audience
        from anveshak.reporter.llm import BlufContent
        from anveshak.reporter.worker import _build_content_md_v2

        bluf = BlufContent(
            bluf="Bottom line.",
            confidence_level=0.7,
            labels={"classification": "OPEN", "domain": "report", "owner_org": "anveshak"},
        )
        bundle = {
            "topic_stats": {
                "name": "Topic",
                "content_count": 10,
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
        return _build_content_md_v2(
            bluf=bluf,
            data_bundle=bundle,
            identifiers=[],
            template_matches=self._MATCHES,
            report_type="intelligence_brief",
            audience=resolve_audience(audience_id),
        )

    def test_the_stored_markdown_gives_back_its_own_heading(self):
        """The PDF reads the snapshot, so the audience's heading round-trips."""
        from anveshak.reporter.main import extract_actions_from_md

        heading, actions = extract_actions_from_md(self._markdown_for("advisory"))
        assert heading == "Assessment Priorities"
        assert any("Map the recruitment network" in a for a in actions)

    def test_prosecution_round_trips_too(self):
        from anveshak.reporter.main import extract_actions_from_md

        heading, actions = extract_actions_from_md(self._markdown_for("prosecution"))
        assert heading == "Recommended Actions"
        assert any("PMLA Section 17" in a for a in actions)

    @pytest.mark.asyncio
    async def test_generate_report_hands_the_pdf_its_actions_and_heading(self):
        """Wiring: the worker builds the PDF from the same call the markdown uses."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from anveshak.reporter.llm import BlufContent

        settings_mock = MagicMock()
        settings_mock.rag_top_k = 10
        settings_mock.topic_relevance_threshold = 0.35
        settings_mock.ollama_retry_max = 2
        settings_mock.pdf_output_dir = "/tmp"
        ctx = {"db": AsyncMock(), "settings": settings_mock}

        with (
            patch("anveshak.reporter.worker.db") as mock_db,
            patch(
                "anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock
            ) as mock_embed,
            patch(
                "anveshak.reporter.worker.call_ollama_for_bluf", new_callable=AsyncMock
            ) as mock_bluf,
            patch("anveshak.reporter.worker.render_bluf_prompt", return_value="p"),
            patch("anveshak.reporter.worker.geocode_locations", return_value=[]),
            patch("anveshak.reporter.worker.extract_locations_from_text", return_value=[]),
            patch(
                "anveshak.reporter.worker.build_geojson",
                return_value={"type": "FeatureCollection", "features": []},
            ),
            patch("anveshak.reporter.pdf.generate_pdf", new_callable=AsyncMock) as mock_pdf,
        ):
            mock_db.fetch_report = AsyncMock(
                return_value={
                    "id": "r1",
                    "topic_id": "t1",
                    "report_type": "intelligence_brief",
                    "credibility_min_filter": 30.0,
                }
            )
            mock_db.fetch_topic = AsyncMock(
                return_value={
                    "id": "t1",
                    "name": "T",
                    "keywords": [],
                    "org_report_audience": "advisory",
                }
            )
            mock_db.fetch_report_data_bundle = AsyncMock(
                return_value={
                    "topic_stats": {
                        "name": "T",
                        "content_count": 1,
                        "source_count": 1,
                        "cluster_count": 0,
                        "signal_count": 0,
                    },
                    "clusters": [],
                }
            )
            mock_db.fetch_rag_chunks = AsyncMock(
                return_value=[{"id": "c1", "source_id": "s1", "clean_text": "x", "url": "u"}]
            )
            mock_db.fetch_sources_for_snapshot = AsyncMock(return_value={})
            mock_db.fetch_topic_location_entities = AsyncMock(return_value=[])
            mock_db.fetch_topic_identifiers = AsyncMock(return_value=[])
            mock_db.fetch_topic_template_matches = AsyncMock(return_value=self._MATCHES)
            mock_db.set_report_generated = AsyncMock(return_value=True)
            mock_db.update_job_status = AsyncMock()
            mock_embed.return_value = [0.1] * 384
            mock_bluf.return_value = BlufContent(
                bluf="Bottom line.",
                confidence_level=0.7,
                labels={"classification": "OPEN", "domain": "report", "owner_org": "anveshak"},
            )
            mock_pdf.return_value = "/tmp/r1.pdf"

            from anveshak.reporter.worker import generate_report

            await generate_report(ctx, "r1")

            pdf_data = mock_pdf.call_args[0][1]
            assert pdf_data["actions_heading"] == "Assessment Priorities"
            assert any("Map the recruitment network" in a for a in pdf_data["recommended_actions"])

    def test_a_report_with_no_actions_gives_back_nothing(self):
        from anveshak.reporter.main import extract_actions_from_md

        assert extract_actions_from_md("## Executive Summary\n\nText.\n") == ("", [])

    def test_the_section_after_the_matches_is_not_mistaken_for_actions(self):
        """An audience that produced no actions leaves no block, not someone else's."""
        from anveshak.reporter.main import extract_actions_from_md

        md = (
            "## Scam Template Matches\n\n**Mule** - Severity: HIGH\n\n"
            "## Source Citations\n\n- https://example.com/a\n- https://example.com/b\n"
        )
        assert extract_actions_from_md(md) == ("", [])

    def test_an_unresolved_audience_leaves_no_actions_in_the_markdown(self):
        """End to end for the same case: unknown audience, no marker, no block."""
        from anveshak.reporter.main import extract_actions_from_md

        md = self._markdown_for("interpol")
        assert "recommended-actions" not in md
        assert extract_actions_from_md(md) == ("", [])

    def test_curated_actions_never_land_in_the_llm_recommendations(self):
        """Provenance: an LLM recommendation and a curated action are not the same thing."""
        from anveshak.reporter.main import _enrich_report_data_from_md

        md = (
            "## Executive Summary\n\nText.\n\n"
            "## Recommendations\n\n- Keep watching this topic\n\n"
            "## Scam Template Matches\n\n**Mule** - Severity: HIGH\n\n"
            "<!-- recommended-actions -->\n"
            "## Assessment Priorities\n\n- Map the recruitment network\n"
        )
        report_data: dict = {}
        _enrich_report_data_from_md(report_data, md)
        assert report_data["recommendations"] == ["Keep watching this topic"]
        assert report_data["recommended_actions"] == ["Map the recruitment network"]
        assert report_data["actions_heading"] == "Assessment Priorities"


# ---------------------------------------------------------------------------
# Build context
# ---------------------------------------------------------------------------


class TestConfigReachesTheImage:
    """Every config directory a Dockerfile COPYs must survive .dockerignore.

    infra/configs/ is blanket-excluded and re-included per directory, so a new
    config directory is invisible to the build context until it is named. The
    build then fails with "file not found in build context", which is a broken
    image rather than a degraded one. See .dockerignore and the git-build skill.
    """

    def test_every_copied_config_dir_is_reincluded(self):
        import re
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        ignored = (repo_root / ".dockerignore").read_text()
        reincluded = set(re.findall(r"^!infra/configs/([^/\s]+)/", ignored, re.MULTILINE))

        missing = []
        for dockerfile in sorted(repo_root.glob("services/*/Dockerfile")):
            for copied in re.findall(
                r"^COPY infra/configs/([^/\s]+)/", dockerfile.read_text(), re.MULTILINE
            ):
                if copied not in reincluded:
                    missing.append(
                        f"{dockerfile.relative_to(repo_root)} COPYs infra/configs/{copied}/"
                    )

        assert not missing, (
            "these config directories are excluded from the build context, so the "
            f"COPY fails and the image does not build: {missing}"
        )
