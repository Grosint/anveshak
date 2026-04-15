"""Unit tests for reporter PDF generation.

pytest.mark.unit — WeasyPrint is mocked (no system fonts needed in CI).
"""
from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

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
