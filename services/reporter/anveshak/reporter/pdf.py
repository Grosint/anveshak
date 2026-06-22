"""PDF generation for intelligence reports.

Uses WeasyPrint (HTML → PDF) with inline Jinja2 HTML templates.
CLAUDE.md rule 6: hardware independence — no hardcoded model/device choices here.

Two templates:
- PDF_TEMPLATE_V1: legacy LLM-dependent reports (backward compat)
- PDF_TEMPLATE_V2: GROSINT-branded data-driven reports
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


def _format_timestamp(value: str | object) -> str:
    """Format a timestamp string or datetime to 'DD Mon YYYY, HH:MM UTC'."""
    from datetime import datetime as _dt
    if not value:
        return "N/A"
    if isinstance(value, _dt):
        return value.strftime("%d %b %Y, %H:%M UTC")
    s = str(value)
    try:
        # Parse ISO format (with or without timezone)
        clean = s.replace("+00:00", "").replace("Z", "")
        if "." in clean:
            clean = clean.split(".")[0]  # strip microseconds
        dt = _dt.fromisoformat(clean)
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except (ValueError, TypeError):
        return s


_env.filters["fmtts"] = _format_timestamp

# ---------------------------------------------------------------------------
# Anveshak icon SVG (inline — no filesystem dependency)
# ---------------------------------------------------------------------------
_ANVESHAK_ICON_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="none" width="42" height="42">
  <rect width="100" height="100" rx="16" ry="16" fill="#1E2533"/>
  <line x1="0" y1="12" x2="100" y2="12" stroke="#F5A623" stroke-width="3.2" stroke-linecap="square"/>
  <circle cx="50" cy="55" r="43" stroke="#C47A0B" stroke-width="2.5" fill="none"/>
  <circle cx="50" cy="55" r="29" stroke="#F5A623" stroke-width="2.5" fill="none"/>
  <polygon points="50,30 28,67 72,67" fill="#2A3347" stroke="#F5A623" stroke-width="2" stroke-linejoin="miter"/>
  <circle cx="50" cy="55" r="5.5" fill="#F5A623"/>
</svg>"""


# ---------------------------------------------------------------------------
# V1 template — legacy (kept for backward compatibility)
# ---------------------------------------------------------------------------
PDF_TEMPLATE_V1 = """\
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
  &nbsp;|&nbsp;
  <strong>Generated:</strong> {{ report_data.get('generated_at', 'N/A') }}
  &nbsp;|&nbsp;
  <strong>Confidence:</strong>
  <span class="confidence">{{ "%.0f"|format(report_data.get('confidence_score', 0) * 100) }}%</span>
  &nbsp;|&nbsp;
  <strong>Sources:</strong> {{ report_data.get('content_item_count', 0) }} items
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
  <li class="citation">{{ citation }}</li>
{% else %}
  <li><em>No citations recorded.</em></li>
{% endfor %}
</ul>
{% if report_data.get('identifiers') %}
<h2>Identified Indicators</h2>
<table style="width: 100%; border-collapse: collapse; font-size: 10pt; margin-top: 8px;">
  <tr style="background: #0f3460; color: white;">
    <th style="padding: 6px; text-align: left;">Type</th>
    <th style="padding: 6px; text-align: left;">Value</th>
    <th style="padding: 6px; text-align: right;">Sources</th>
    <th style="padding: 6px; text-align: right;">Items</th>
  </tr>
  {% for ident in report_data.get('identifiers', []) %}
  <tr style="border-bottom: 1px solid #ddd;">
    <td style="padding: 5px;">{{ ident.get('identifier_type', '') }}</td>
    <td style="padding: 5px; font-family: monospace;">{{ ident.get('identifier_value', '') }}</td>
    <td style="padding: 5px; text-align: right;">{{ ident.get('source_count', 0) }}</td>
    <td style="padding: 5px; text-align: right;">{{ ident.get('content_item_count', 0) }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

{% if report_data.get('template_matches') %}
<h2>Scam Template Matches</h2>
<table style="width: 100%; border-collapse: collapse; font-size: 10pt; margin-top: 8px;">
  <tr style="background: #0f3460; color: white;">
    <th style="padding: 6px; text-align: left;">Template</th>
    <th style="padding: 6px; text-align: left;">Severity</th>
    <th style="padding: 6px; text-align: right;">Confidence</th>
    <th style="padding: 6px; text-align: right;">Matches</th>
  </tr>
  {% for match in report_data.get('template_matches', []) %}
  <tr style="border-bottom: 1px solid #ddd;">
    <td style="padding: 5px;">{{ match.get('template_display', match.get('template_name', '')) }}</td>
    <td style="padding: 5px;">{{ match.get('severity', '') }}</td>
    <td style="padding: 5px; text-align: right;">{{ "%.0f"|format((match.get('confidence') or 0) * 100) }}%</td>
    <td style="padding: 5px; text-align: right;">{{ match.get('match_count', 0) }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

{% if report_data.get('recommended_actions') %}
<h2>Recommended Actions</h2>
<ul>
{% for action in report_data.get('recommended_actions', []) %}
  <li>{{ action }}</li>
{% endfor %}
</ul>
{% endif %}

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


# ---------------------------------------------------------------------------
# V2 template — GROSINT branded, data-driven
# ---------------------------------------------------------------------------
PDF_TEMPLATE_V2 = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>{{ rd.get('topic_name', 'Intelligence Report') }} — Anveshak OSINT</title>
  <style>
    /* ── Design tokens ── */
    :root {
      --amber: #C96E0A;
      --amber-pale: #FDF3E7;
      --navy: #0D1B2A;
      --slate: #2C3E50;
      --mid: #5A6A7A;
      --light: #8A9BAB;
      --green: #1A7A4A;
      --bg: #FFFFFF;
      --off: #F8F6F2;
      --border: #E2D9CC;
    }

    @page { size: A4 portrait; margin: 15mm 12mm 18mm 12mm; }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'DejaVu Serif', 'Liberation Serif', Georgia, serif;
      font-size: 9.5pt; color: var(--navy); line-height: 1.55;
      background: var(--bg);
    }

    /* ── Header ── */
    .hdr { display: table; width: 100%; margin-bottom: 4mm; }
    .hdr-left { display: table-cell; vertical-align: middle; }
    .hdr-right { display: table-cell; vertical-align: middle; text-align: right; }
    .wordmark {
      font-family: 'DejaVu Sans', 'Liberation Sans', sans-serif;
      font-size: 15pt; font-weight: 700; letter-spacing: 0.05em; color: var(--navy);
    }
    .wordmark span { color: var(--amber); }
    .subtitle {
      font-family: 'DejaVu Sans', sans-serif;
      font-size: 6.5pt; color: var(--mid); letter-spacing: 0.08em; text-transform: uppercase;
      margin-top: 1mm;
    }
    .top-rule { height: 3px; background: linear-gradient(90deg, var(--amber) 0%, #E87D14 50%, #0070A8 100%); margin-bottom: 4mm; }

    /* ── Meta strip ── */
    .meta-strip {
      background: var(--off); border: 1px solid var(--border); border-radius: 3px;
      padding: 3mm 4mm; margin-bottom: 5mm;
    }
    .meta-strip table { width: 100%; border-collapse: collapse; }
    .meta-strip td {
      font-family: 'DejaVu Sans', sans-serif; font-size: 7pt; color: var(--mid);
      padding: 1mm 2mm; vertical-align: top;
    }
    .meta-label { font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--light); width: 25mm; }

    /* ── Stats boxes ── */
    .stats { display: table; width: 100%; margin-bottom: 5mm; }
    .stat-box {
      display: table-cell; width: 25%; text-align: center;
      background: var(--off); border: 1px solid var(--border); border-radius: 3px;
      padding: 3mm 2mm;
    }
    .stat-n {
      font-family: 'DejaVu Sans', sans-serif; font-size: 16pt; font-weight: 700;
      color: var(--amber); line-height: 1;
    }
    .stat-n.green { color: var(--green); }
    .stat-l { font-size: 6.5pt; color: var(--mid); margin-top: 1mm; text-transform: uppercase; letter-spacing: 0.1em; }

    /* ── Section headings ── */
    .part-label {
      font-family: 'DejaVu Sans', sans-serif; font-size: 6pt; font-weight: 700;
      letter-spacing: 0.18em; text-transform: uppercase; color: var(--amber);
      margin-bottom: 1mm;
    }
    h1 {
      font-family: 'DejaVu Sans', sans-serif; font-size: 16pt; font-weight: 700;
      color: var(--navy); margin-bottom: 3mm; line-height: 1.1;
    }
    h2 {
      font-family: 'DejaVu Sans', sans-serif; font-size: 11pt; font-weight: 700;
      color: var(--navy); margin-top: 5mm; margin-bottom: 2mm;
    }
    h3 {
      font-family: 'DejaVu Sans', sans-serif; font-size: 9pt; font-weight: 700;
      color: var(--navy); margin-top: 4mm; margin-bottom: 1.5mm;
    }
    .rule { height: 2px; background: linear-gradient(90deg, var(--amber), rgba(201,110,10,0.1)); margin: 3mm 0; }

    /* ── Tables ── */
    table.data {
      width: 100%; border-collapse: collapse; font-size: 8.5pt; margin-top: 2mm; margin-bottom: 3mm;
    }
    table.data th {
      background: var(--navy); color: white; padding: 2mm 3mm; text-align: left;
      font-family: 'DejaVu Sans', sans-serif; font-size: 6pt; font-weight: 700;
      letter-spacing: 0.1em; text-transform: uppercase;
    }
    table.data td { padding: 2mm 3mm; border-bottom: 1px solid var(--border); vertical-align: top; }
    table.data tr:nth-child(even) { background: var(--off); }
    table.data td.num { text-align: right; font-family: 'DejaVu Sans Mono', monospace; }

    /* ── Evidence cards ── */
    .evidence-card {
      border: 1px solid var(--border); border-radius: 4px; padding: 3mm 4mm;
      margin-bottom: 3mm; page-break-inside: avoid;
    }
    .evidence-card .ec-head {
      font-family: 'DejaVu Sans', sans-serif; font-size: 9pt; font-weight: 700;
      color: var(--navy); margin-bottom: 1.5mm;
    }
    .evidence-card .ec-meta {
      font-family: 'DejaVu Sans', sans-serif; font-size: 7pt; color: var(--mid);
      margin-bottom: 1.5mm;
    }
    .evidence-card .ec-quote {
      border-left: 2.5px solid var(--amber); padding-left: 3mm;
      font-style: italic; color: var(--slate); font-size: 8.5pt;
    }

    /* ── BLUF box ── */
    .bluf-box {
      background: var(--off); border: 1px solid var(--border); border-left: 3px solid var(--amber);
      border-radius: 4px; padding: 4mm 5mm; margin-bottom: 4mm;
    }
    .bluf-box .bluf-label {
      font-family: 'DejaVu Sans', sans-serif; font-size: 6pt; font-weight: 700;
      letter-spacing: 0.15em; text-transform: uppercase; color: var(--amber);
      margin-bottom: 1.5mm;
    }

    /* ── Keywords ── */
    .kw-badge {
      display: inline-block; font-family: 'DejaVu Sans', sans-serif;
      font-size: 6.5pt; letter-spacing: 0.08em; color: var(--amber);
      background: var(--amber-pale); border: 1px solid rgba(201,110,10,0.22);
      border-radius: 2px; padding: 1px 5px; margin: 1px 2px;
    }

    /* ── Footer ── */
    .footer {
      border-top: 2px solid var(--amber); padding-top: 3mm; margin-top: 6mm;
      display: table; width: 100%;
    }
    .footer-left {
      display: table-cell; vertical-align: middle;
      font-family: 'DejaVu Sans', sans-serif; font-size: 6pt; color: var(--light);
      letter-spacing: 0.06em;
    }
    .footer-right {
      display: table-cell; vertical-align: middle; text-align: right;
      font-family: 'DejaVu Sans', sans-serif; font-size: 6pt; color: var(--light);
    }

    /* ── Page breaks ── */
    .page-break { page-break-before: always; }

    /* ── Print ── */
    @media print {
      * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    }
  </style>
</head>
<body>

<!-- ══ HEADER ══ -->
<div class="top-rule"></div>
<div class="hdr">
  <div class="hdr-left">
    """ + _ANVESHAK_ICON_SVG + """
    <span class="wordmark" style="margin-left: 3mm;"><span>AN</span>VESHAK</span>
    <div class="subtitle">Open Source Intelligence Platform</div>
  </div>
  <div class="hdr-right">
    <div style="font-family: DejaVu Sans, sans-serif; font-size: 6pt; color: var(--light); letter-spacing: 0.12em; text-transform: uppercase;">
      REPORT {{ rd.get('id', '')[:8] | upper }}
    </div>
  </div>
</div>

<!-- ══ COVER META ══ -->
<div class="meta-strip">
  <table>
    <tr>
      <td class="meta-label">Subject</td>
      <td>{{ rd.get('topic_name', 'Intelligence Report') }}</td>
      <td class="meta-label">Report Type</td>
      <td>{{ rd.get('report_type', 'intelligence_brief') | replace('_', ' ') | title }}</td>
    </tr>
    <tr>
      <td class="meta-label">Generated</td>
      <td>{{ rd.get('generated_at', 'N/A')|fmtts }}</td>
      <td class="meta-label">Handling</td>
      <td>{{ rd.get('labels', {}).get('classification', 'OPEN') }} — For Official Use</td>
    </tr>
    <tr>
      <td class="meta-label">Sources</td>
      <td>{{ rd.get('content_item_count', 0) }} content items</td>
      <td class="meta-label">Confidence</td>
      <td>{{ "%.0f"|format(rd.get('confidence_score', 0) * 100) }}%</td>
    </tr>
  </table>
</div>

<!-- ══ BLUF ══ -->
<div class="part-label">0 · BLUF</div>
<h1>{{ rd.get('topic_name', 'Intelligence Report') }}</h1>
<div class="rule"></div>

{% set stats = rd.get('topic_stats', {}) %}
<div class="stats">
  <div class="stat-box" style="margin-right: 2mm;">
    <div class="stat-n">{{ stats.get('content_count', 0) }}</div>
    <div class="stat-l">Content Items</div>
  </div>
  <div class="stat-box" style="margin-right: 2mm;">
    <div class="stat-n">{{ stats.get('source_count', 0) }}</div>
    <div class="stat-l">Sources</div>
  </div>
  <div class="stat-box" style="margin-right: 2mm;">
    <div class="stat-n">{{ stats.get('cluster_count', 0) }}</div>
    <div class="stat-l">Clusters</div>
  </div>
  <div class="stat-box">
    <div class="stat-n green">{{ stats.get('signal_count', 0) }}</div>
    <div class="stat-l">Signals</div>
  </div>
</div>

<div class="bluf-box">
  <div class="bluf-label">Bottom-Line Judgement</div>
  <p>{{ rd.get('bluf', rd.get('executive_summary', 'No summary available.')) }}</p>
</div>

<!-- ══ PART I: DATA SHEET ══ -->
<div class="part-label">Part I · Data Sheet</div>
<h2>Source Inventory</h2>
{% if rd.get('sources') %}
<table class="data">
  <tr>
    <th>Source</th>
    <th>Platform</th>
    <th>Credibility</th>
    <th>Items</th>
  </tr>
  {% for src in rd.get('sources', []) %}
  <tr>
    <td>{{ src.get('name', '') }}</td>
    <td>{{ src.get('platform', '') }}</td>
    <td class="num">{{ "%.0f"|format(src.get('credibility_score', 0)) }}</td>
    <td class="num">{{ src.get('item_count', 0) }}</td>
  </tr>
  {% endfor %}
</table>
{% else %}
<p><em>No sources linked to this topic.</em></p>
{% endif %}

{% if rd.get('clusters') %}
<h2>Narrative Clusters</h2>
<table class="data">
  <tr>
    <th>Cluster</th>
    <th>Items</th>
    <th>Indep. Sources</th>
    <th>Summary</th>
  </tr>
  {% for cl in rd.get('clusters', []) %}
  <tr>
    <td>{{ cl.get('label', '') }}</td>
    <td class="num">{{ cl.get('item_count', 0) }}</td>
    <td class="num">{{ cl.get('independent_source_count', 0) }}</td>
    <td>{{ cl.get('executive_summary', '')[:80] }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

{% if rd.get('entities') %}
<h2>Top Entities</h2>
<table class="data">
  <tr>
    <th>Entity</th>
    <th>Type</th>
    <th>Mentions</th>
  </tr>
  {% for ent in rd.get('entities', [])[:20] %}
  <tr>
    <td>{{ ent.get('entity_text', '') }}</td>
    <td>{{ ent.get('entity_type', '') }}</td>
    <td class="num">{{ ent.get('mention_count', 0) }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

{% if rd.get('keywords') %}
<h2>Trending Keywords</h2>
<p>
{% for kw in rd.get('keywords', [])[:15] %}
  <span class="kw-badge">{{ kw.get('keyword', '') }} ({{ kw.get('frequency', 0) }})</span>
{% endfor %}
</p>
{% endif %}

{% if rd.get('language_breakdown') %}
<h2>Language Breakdown</h2>
<table class="data">
  <tr><th>Language</th><th>Items</th></tr>
  {% for lang in rd.get('language_breakdown', []) %}
  <tr><td>{{ lang.get('language', 'unknown') }}</td><td class="num">{{ lang.get('count', 0) }}</td></tr>
  {% endfor %}
</table>
{% endif %}

<!-- ══ PART II: INVESTIGATIVE ANNEX ══ -->
{% set has_annex = rd.get('signals') or rd.get('identifiers') or rd.get('template_matches') %}
{% if has_annex %}
<div class="page-break"></div>
<div class="part-label">Part II · Investigative Annex</div>
<h1>Signals, Identifiers &amp; Patterns</h1>
<div class="rule"></div>

{% if rd.get('signals') %}
<h2>Active Signals</h2>
<table class="data">
  <tr><th>Signal</th><th>Cluster</th><th>Status</th><th>Date</th></tr>
  {% for sig in rd.get('signals', [])[:20] %}
  <tr>
    <td>{{ sig.get('description', '')[:120] }}</td>
    <td>{{ sig.get('cluster_label', '') }}</td>
    <td>{{ sig.get('status', '') }}</td>
    <td>{{ (sig.get('created_at', '')|string)[:10] }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

{% if rd.get('identifiers') %}
<h2>Identified Indicators</h2>
<table class="data">
  <tr><th>Type</th><th>Value</th><th>Sources</th><th>Items</th></tr>
  {% for ident in rd.get('identifiers', []) %}
  <tr>
    <td>{{ ident.get('identifier_type', '') }}</td>
    <td style="font-family: DejaVu Sans Mono, monospace;">{{ ident.get('identifier_value', '') }}</td>
    <td class="num">{{ ident.get('source_count', 0) }}</td>
    <td class="num">{{ ident.get('content_item_count', 0) }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

{% if rd.get('template_matches') %}
<h2>Scam Template Matches</h2>
<table class="data">
  <tr><th>Template</th><th>Severity</th><th>Confidence</th><th>Matches</th></tr>
  {% for match in rd.get('template_matches', []) %}
  <tr>
    <td>{{ match.get('template_display', match.get('template_name', '')) }}</td>
    <td>{{ match.get('severity', '') }}</td>
    <td class="num">{{ "%.0f"|format((match.get('confidence') or 0) * 100) }}%</td>
    <td class="num">{{ match.get('match_count', 0) }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}
{% endif %}

<!-- ══ PART III: EVIDENCE APPENDIX ══ -->
{% if rd.get('evidence_items') %}
<div class="page-break"></div>
<div class="part-label">Part III · Evidence Appendix</div>
<h1>Content Item Records</h1>
<div class="rule"></div>

{% for item in rd.get('evidence_items', [])[:30] %}
<div class="evidence-card">
  <div class="ec-head">{{ item.get('title', item.get('snippet', 'Untitled')[:50]) }}</div>
  <div class="ec-meta">
    {{ item.get('source_name', 'Unknown') }} · {{ item.get('platform', '') }}
    &nbsp;·&nbsp; {{ (item.get('captured_at', '')|string)[:10] }}
    &nbsp;·&nbsp; Credibility: {{ "%.0f"|format(item.get('credibility_score_at_capture', 0)) }}
  </div>
  {% if item.get('snippet') %}
  <div class="ec-quote">{{ item.get('snippet', '') }}</div>
  {% endif %}
  {% if item.get('url') %}
  <div style="font-size: 7pt; color: var(--mid); margin-top: 1.5mm; word-break: break-all;">{{ item.get('url', '') }}</div>
  {% endif %}
</div>
{% endfor %}
{% endif %}

<!-- ══ PART IV: METHODOLOGY ══ -->
{% if rd.get('report_type') == 'research_summary' %}
<div class="page-break"></div>
<div class="part-label">Part IV · Methodology</div>
<h1>Sourcing, Limitations &amp; Confidence</h1>
<div class="rule"></div>

<h3>Data Acquisition</h3>
<p>Automated open-source collection via Anveshak platform. Sources configured by analyst — web scraping (Crawl4AI), social media adapters (Telegram, Reddit, Bluesky, X), and RSS feeds.</p>

<h3>Analysis Period</h3>
<p>{{ stats.get('content_count', 0) }} content items from {{ stats.get('source_count', 0) }} sources, processed through multilingual NLP (spaCy + NLLB-200), narrative clustering (Leiden algorithm), and entity extraction.</p>

<h3>Confidence Calibration</h3>
<p>Confidence level ({{ "%.0f"|format(rd.get('confidence_score', 0) * 100) }}%) reflects the fraction of narrative clusters corroborated by 2+ independent sources. Individual source credibility scores are auto-adjusted based on deepfake detection, contradiction analysis, and analyst feedback.</p>

<h3>Limitations</h3>
<p>This report is a point-in-time snapshot. Source credibility scores may have changed since generation. All AI-generated summaries require analyst verification. Legal provision mappings (if present) are AI-generated and require verification by a qualified legal officer.</p>
{% endif %}

<!-- ══ FOOTER ══ -->
<div class="footer">
  <div class="footer-left">
    OSINT · Public-source · Handle: {{ rd.get('labels', {}).get('classification', 'OPEN') }}
  </div>
  <div class="footer-right">
    Anveshak AI-OSINT Platform · {{ rd.get('generated_at', '')|fmtts }} · Immutable after generation
  </div>
</div>

</body>
</html>
"""

# Pre-compile templates
_COMPILED_V1 = _env.from_string(PDF_TEMPLATE_V1)
_COMPILED_V2 = _env.from_string(PDF_TEMPLATE_V2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_pdf_html(report_data: dict[str, Any]) -> str:
    """Render the Jinja2 HTML template for a given report data dict.

    Automatically selects v2 (GROSINT branded) template when data bundle
    fields are present (topic_stats, sources, clusters). Falls back to
    v1 for legacy reports.
    """
    if report_data.get("topic_stats") or report_data.get("sources"):
        # v2 data-driven template
        return _COMPILED_V2.render(rd=report_data)
    # v1 legacy template
    return _COMPILED_V1.render(report_data=report_data)


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
