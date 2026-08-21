"""Unit tests for reporter PDF generation.

pytest.mark.unit — WeasyPrint is mocked (no system fonts needed in CI).
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


SAMPLE_REPORT_DATA = {
    "id": "report-abc-123",
    "report_type": "intelligence_brief",
    "topic_name": "UAV Incidents",
    "generated_at": "2026-04-15T10:00:00Z",
    "confidence_score": 0.85,
    "executive_summary": "Increased UAV activity near northern border.",
    "key_findings": ["3 incidents logged", "Sources corroborate timeline"],
    "recommendations": ["Increase patrol frequency"],
    "source_citations": ["https://example.com/report1"],
    "content_item_count": 12,
}


class TestRenderPdfHtml:
    """render_pdf_html returns non-empty HTML string containing key fields."""

    def test_returns_non_empty_string(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_REPORT_DATA)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_html_contains_report_title(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_REPORT_DATA)
        assert "UAV Incidents" in html

    def test_html_contains_executive_summary(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_REPORT_DATA)
        assert "Increased UAV activity near northern border." in html

    def test_html_contains_key_findings(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_REPORT_DATA)
        assert "3 incidents logged" in html

    def test_html_contains_recommendations(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_REPORT_DATA)
        assert "Increase patrol frequency" in html

    def test_html_contains_confidence_level(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_REPORT_DATA)
        # Confidence score should appear somewhere in the rendered HTML
        assert "0.85" in html or "85" in html

    def test_html_contains_generated_at(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_REPORT_DATA)
        assert "2026-04-15" in html

    def test_html_contains_source_citations(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_REPORT_DATA)
        assert "https://example.com/report1" in html


class TestGeneratePdf:
    """generate_pdf returns path string; path matches {output_dir}/{report_id}.pdf."""

    @pytest.mark.asyncio
    async def test_returns_path_string(self):
        import anveshak.reporter.pdf as pdf_mod
        from anveshak.reporter.pdf import generate_pdf

        mock_html_obj = MagicMock()

        def fake_write_pdf(path):
            with open(path, "wb") as f:
                f.write(b"%PDF-stub")

        mock_html_obj.write_pdf.side_effect = fake_write_pdf
        mock_html_cls = MagicMock(return_value=mock_html_obj)

        with tempfile.TemporaryDirectory() as tmpdir:
            original_html = pdf_mod.HTML
            pdf_mod.HTML = mock_html_cls
            try:
                path = await generate_pdf("report-abc-123", SAMPLE_REPORT_DATA, tmpdir)
            finally:
                pdf_mod.HTML = original_html

        assert path.endswith("report-abc-123.pdf")

    @pytest.mark.asyncio
    async def test_path_follows_naming_convention(self):
        """PDF path must be {output_dir}/{report_id}.pdf"""
        import anveshak.reporter.pdf as pdf_mod
        from anveshak.reporter.pdf import generate_pdf

        mock_html_obj = MagicMock()

        def fake_write(p):
            with open(p, "wb") as f:
                f.write(b"%PDF-1.4 stub")

        mock_html_obj.write_pdf.side_effect = fake_write
        mock_html_cls = MagicMock(return_value=mock_html_obj)

        with tempfile.TemporaryDirectory() as tmpdir:
            expected_path = os.path.join(tmpdir, "report-abc-123.pdf")
            original_html = pdf_mod.HTML
            pdf_mod.HTML = mock_html_cls
            try:
                result = await generate_pdf("report-abc-123", SAMPLE_REPORT_DATA, tmpdir)
            finally:
                pdf_mod.HTML = original_html

        assert result == expected_path

    @pytest.mark.asyncio
    async def test_weasyprint_failure_raises_pdf_generation_error(self):
        """WeasyPrint exception → PDFGenerationError with report_id context."""
        import anveshak.reporter.pdf as pdf_mod
        from anveshak.reporter.pdf import PDFGenerationError, generate_pdf

        mock_html_obj = MagicMock()
        mock_html_obj.write_pdf.side_effect = RuntimeError("libpango missing")
        mock_html_cls = MagicMock(return_value=mock_html_obj)

        with tempfile.TemporaryDirectory() as tmpdir:
            original_html = pdf_mod.HTML
            pdf_mod.HTML = mock_html_cls
            try:
                with pytest.raises(PDFGenerationError) as exc_info:
                    await generate_pdf("report-fail", SAMPLE_REPORT_DATA, tmpdir)
                assert "report-fail" in str(exc_info.value)
            finally:
                pdf_mod.HTML = original_html

    @pytest.mark.asyncio
    async def test_disk_write_failure_raises_pdf_generation_error(self):
        """Disk write failure → PDFGenerationError."""
        import anveshak.reporter.pdf as pdf_mod
        from anveshak.reporter.pdf import PDFGenerationError, generate_pdf

        mock_html_obj = MagicMock()
        mock_html_obj.write_pdf.side_effect = OSError("No space left on device")
        mock_html_cls = MagicMock(return_value=mock_html_obj)

        with tempfile.TemporaryDirectory() as tmpdir:
            original_html = pdf_mod.HTML
            pdf_mod.HTML = mock_html_cls
            try:
                with pytest.raises(PDFGenerationError):
                    await generate_pdf("report-disk-full", SAMPLE_REPORT_DATA, tmpdir)
            finally:
                pdf_mod.HTML = original_html

    @pytest.mark.asyncio
    async def test_empty_report_data_does_not_crash(self):
        """Empty report_data should still produce a PDF (with defaults)."""
        import anveshak.reporter.pdf as pdf_mod
        from anveshak.reporter.pdf import generate_pdf

        mock_html_obj = MagicMock()

        def fake_write(p):
            with open(p, "wb") as f:
                f.write(b"%PDF-1.4 stub")

        mock_html_obj.write_pdf.side_effect = fake_write
        mock_html_cls = MagicMock(return_value=mock_html_obj)

        with tempfile.TemporaryDirectory() as tmpdir:
            original_html = pdf_mod.HTML
            pdf_mod.HTML = mock_html_cls
            try:
                path = await generate_pdf("report-empty", {}, tmpdir)
                assert path.endswith("report-empty.pdf")
            finally:
                pdf_mod.HTML = original_html

    @pytest.mark.asyncio
    async def test_creates_output_dir_if_not_exists(self):
        import anveshak.reporter.pdf as pdf_mod
        from anveshak.reporter.pdf import generate_pdf

        mock_html_obj = MagicMock()

        def fake_write(p):
            with open(p, "wb") as f:
                f.write(b"%PDF-1.4 stub")

        mock_html_obj.write_pdf.side_effect = fake_write
        mock_html_cls = MagicMock(return_value=mock_html_obj)

        with tempfile.TemporaryDirectory() as base:
            new_dir = os.path.join(base, "nested", "reports")
            assert not os.path.exists(new_dir)

            original_html = pdf_mod.HTML
            pdf_mod.HTML = mock_html_cls
            try:
                await generate_pdf("report-abc-123", SAMPLE_REPORT_DATA, new_dir)
            finally:
                pdf_mod.HTML = original_html

            assert os.path.exists(new_dir)


# ---------------------------------------------------------------------------
# V2 GROSINT template tests
# ---------------------------------------------------------------------------

SAMPLE_V2_REPORT_DATA = {
    "id": "report-v2-abc-123",
    "report_type": "intelligence_brief",
    "topic_name": "UAV Incidents",
    "generated_at": "2026-04-15T10:00:00Z",
    "confidence_score": 0.85,
    "content_item_count": 148,
    "labels": {"classification": "OPEN", "domain": "report", "owner_org": "anveshak"},
    "bluf": "148 items collected across 9 sources reveal increased UAV activity.",
    "topic_stats": {
        "name": "UAV Incidents",
        "content_count": 148,
        "source_count": 9,
        "cluster_count": 8,
        "signal_count": 5,
    },
    "sources": [
        {"name": "Reuters", "platform": "web", "credibility_score": 72.0, "item_count": 35},
        {"name": "NDTV", "platform": "web", "credibility_score": 65.0, "item_count": 28},
    ],
    "clusters": [
        {
            "label": "Border UAV sightings",
            "item_count": 42,
            "independent_source_count": 3,
            "executive_summary": "Multiple sightings near northern border.",
        },
    ],
    "entities": [
        {"entity_text": "Lakshadweep", "entity_type": "GPE", "mention_count": 12},
    ],
    "keywords": [
        {"keyword": "UAV", "frequency": 45},
        {"keyword": "drone", "frequency": 38},
    ],
    "signals": [
        {
            "description": "3 sources corroborate UAV cluster",
            "cluster_label": "Border UAV",
            "status": "new",
            "created_at": "2026-04-10T10:00:00Z",
        },
    ],
}


class TestRenderPdfHtmlV2:
    """V2 GROSINT-branded template renders data-driven content."""

    def test_v2_template_selected_when_topic_stats_present(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_V2_REPORT_DATA)
        # Wordmark renders as <span>AN</span>VESHAK
        assert "VESHAK" in html
        assert "BLUF" in html

    def test_v2_contains_stats_boxes(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_V2_REPORT_DATA)
        assert "148" in html  # content_count
        assert "Content Items" in html

    def test_v2_contains_source_inventory(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_V2_REPORT_DATA)
        assert "Reuters" in html
        assert "NDTV" in html
        assert "Source Inventory" in html

    def test_v2_contains_cluster_table(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_V2_REPORT_DATA)
        assert "Border UAV sightings" in html
        assert "Narrative Clusters" in html

    def test_v2_contains_entities(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_V2_REPORT_DATA)
        assert "Lakshadweep" in html

    def test_v2_contains_keywords(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_V2_REPORT_DATA)
        assert "UAV" in html
        assert "drone" in html

    def test_v2_contains_bluf_text(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_V2_REPORT_DATA)
        assert "148 items collected" in html

    def test_v2_contains_signals(self):
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_V2_REPORT_DATA)
        assert "3 sources corroborate" in html

    def test_v2_amber_branding(self):
        """GROSINT color tokens present in template."""
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_V2_REPORT_DATA)
        assert "#C96E0A" in html  # amber
        assert "#0D1B2A" in html  # navy

    def test_v1_fallback_for_legacy_data(self):
        """Legacy report data without topic_stats uses v1 template."""
        from anveshak.reporter.pdf import render_pdf_html

        html = render_pdf_html(SAMPLE_REPORT_DATA)
        # v1 template does NOT have GROSINT wordmark
        assert "VESHAK" not in html or "Anveshak" in html
        # But does have the report content
        assert "UAV Incidents" in html
