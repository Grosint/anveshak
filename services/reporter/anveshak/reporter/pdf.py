"""PDF generation for intelligence reports.

Uses WeasyPrint (HTML → PDF) with an inline Jinja2 HTML template.
CLAUDE.md rule 6: hardware independence — no hardcoded model/device choices here.
"""
from __future__ import annotations

import os
import pathlib
from typing import Any

import structlog
from jinja2 import Environment, Undefined

# WeasyPrint is imported lazily in generate_pdf() so that unit tests on macOS
# (where libpango is not installed) can mock it without an import-time crash.
HTML = None  # populated on first use inside generate_pdf()

log = structlog.get_logger(__name__)


class PDFGenerationError(Exception):
    """Raised when PDF generation fails (WeasyPrint, disk I/O, etc.)."""

# ---------------------------------------------------------------------------
# Jinja2 environment
# ---------------------------------------------------------------------------
_env = Environment(undefined=Undefined, autoescape=True)

# ---------------------------------------------------------------------------
# Inline HTML template (avoids filesystem dependency for template files)
# ---------------------------------------------------------------------------
PDF_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>{{ report_data.get('topic_name', 'Intelligence Report') }} — Anveshak</title>
  <style>
    body { font-family: DejaVu Sans, Liberation Sans, Arial, sans-serif;
           margin: 40px; color: #1a1a2e; font-size: 11pt; }
    h1 { font-size: 18pt; color: #16213e; border-bottom: 2px solid #0f3460; padding-bottom: 6px; }
    h2 { font-size: 13pt; color: #0f3460; margin-top: 24px; }
    .meta { font-size: 9pt; color: #555; margin-bottom: 20px; }
    .confidence { font-weight: bold; color: #0f3460; }
    ul { margin: 6px 0 12px 0; padding-left: 20px; }
    li { margin-bottom: 4px; }
    .citation { font-size: 9pt; color: #0066cc; word-break: break-all; }
    .footer { font-size: 8pt; color: #888; margin-top: 40px;
              border-top: 1px solid #ccc; padding-top: 8px; }
    .badge { display: inline-block; background: #e8f4fd; border: 1px solid #0f3460;
             border-radius: 4px; padding: 2px 8px; font-size: 9pt; }
  </style>
</head>
<body>

<h1>{{ report_data.get('topic_name', 'Intelligence Report') }}</h1>

<div class="meta">
  <strong>Report Type:</strong> {{ report_data.get('report_type', 'intelligence_brief') | replace('_', ' ') | title }}
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <strong>Generated:</strong> {{ report_data.get('generated_at', 'N/A') }}
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <strong>Confidence:</strong>
  <span class="confidence">{{ "%.0f"|format(report_data.get('confidence_score', 0) * 100) }}%</span>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <strong>Sources:</strong> {{ report_data.get('content_item_count', 0) }} items
  &nbsp;&nbsp;
  <span class="badge">{{ report_data.get('labels', {}).get('classification', 'OPEN') }}</span>
</div>

<h2>Executive Summary</h2>
<p>{{ report_data.get('executive_summary', '') }}</p>

<h2>Key Findings</h2>
<ul>
{% for finding in report_data.get('key_findings', []) %}
  <li>{{ finding }}</li>
{% else %}
  <li><em>No findings recorded.</em></li>
{% endfor %}
</ul>

<h2>Recommendations</h2>
<ul>
{% for rec in report_data.get('recommendations', []) %}
  <li>{{ rec }}</li>
{% else %}
  <li><em>No recommendations recorded.</em></li>
{% endfor %}
</ul>

<h2>Source Citations</h2>
<ul>
{% for citation in report_data.get('source_citations', []) %}
  <li class="citation"><a href="{{ citation }}">{{ citation }}</a></li>
{% else %}
  <li><em>No citations recorded.</em></li>
{% endfor %}
</ul>

{% if report_data.get('legal_sections') %}
<h2>Applicable Legal Provisions</h2>
<p style="font-size: 9pt; color: #666; font-style: italic;">
  AI-generated mappings — require verification by a qualified legal officer before use in any proceedings.
</p>
<table style="width: 100%; border-collapse: collapse; font-size: 10pt; margin-top: 8px;">
  <tr style="background: #0f3460; color: white;">
    <th style="padding: 6px; text-align: left;">Finding</th>
    <th style="padding: 6px; text-align: left;">Act</th>
    <th style="padding: 6px; text-align: left;">Section</th>
    <th style="padding: 6px; text-align: left;">Provision</th>
    <th style="padding: 6px; text-align: left;">Evidence</th>
  </tr>
  {% for mapping in report_data.get('legal_sections', []) %}
    {% for sec in mapping.get('sections', []) %}
  <tr style="border-bottom: 1px solid #ddd;">
    <td style="padding: 5px;">{{ mapping.get('finding', '') }}</td>
    <td style="padding: 5px;">{{ sec.get('act', '') }}</td>
    <td style="padding: 5px;">{{ sec.get('section', '') }}</td>
    <td style="padding: 5px;">{{ sec.get('description', '') }}</td>
    <td style="padding: 5px; font-size: 9pt;">{{ sec.get('evidence_ref', '') }}</td>
  </tr>
    {% endfor %}
  {% endfor %}
</table>
{% endif %}

{% if report_data.get('three_lens') %}
<h2 style="page-break-before: always;">Annexure: Three-Lens Evaluation</h2>
{% for ev in report_data.get('three_lens', {}).get('evaluations', []) %}
<div style="border: 1px solid #0f3460; border-radius: 6px; padding: 12px; margin-bottom: 12px;">
  <div style="font-size: 12pt; font-weight: bold; color: #0f3460;">
    {{ ev.get('perspective', '') }}
    <span class="badge" style="float: right;">Risk: {{ ev.get('risk_level', '') }}</span>
  </div>
  <p style="margin: 8px 0;">{{ ev.get('threat_assessment', '') }}</p>
  <strong>Priority Actions:</strong>
  <ul>
  {% for action in ev.get('priority_actions', []) %}
    <li>{{ action }}</li>
  {% endfor %}
  </ul>
</div>
{% endfor %}
{% endif %}

<div class="footer">
  Produced by Anveshak AI-OSINT Platform — {{ report_data.get('generated_at', '') }}.
  This report is a point-in-time snapshot and is immutable after generation.
  Classification: {{ report_data.get('labels', {}).get('classification', 'OPEN') }}
</div>

</body>
</html>
"""

# Pre-compile template
_COMPILED_TEMPLATE = _env.from_string(PDF_TEMPLATE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_pdf_html(report_data: dict[str, Any]) -> str:
    """Render the Jinja2 HTML template for a given report data dict."""
    return _COMPILED_TEMPLATE.render(report_data=report_data)


async def generate_pdf(
    report_id: str,
    report_data: dict[str, Any],
    output_dir: str,
) -> str:
    """Render HTML and write PDF via WeasyPrint.

    Creates output_dir if it does not exist.
    Returns the absolute path string of the written PDF file.

    WeasyPrint is imported lazily so that this module can be imported on
    systems without libpango (e.g. macOS dev machines running unit tests).
    """
    global HTML  # noqa: PLW0603
    if HTML is None:
        from weasyprint import HTML as _HTML  # type: ignore[import]
        HTML = _HTML

    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"{report_id}.pdf")

    html_content = render_pdf_html(report_data)
    log.info("reporter.pdf_rendering", report_id=report_id)
    try:
        HTML(string=html_content).write_pdf(pdf_path)
    except Exception as exc:
        log.error("reporter.pdf_generation_failed", report_id=report_id, error=str(exc))
        raise PDFGenerationError(
            f"PDF generation failed for report {report_id}: {exc}"
        ) from exc
    log.info("reporter.pdf_written", report_id=report_id, path=pdf_path)
    return pdf_path
