#!/usr/bin/env python3
"""Convert docs/case_study_iaf.md to PDF via WeasyPrint.

Uses basic regex-based markdown→HTML (no external markdown lib needed).
Run inside report-worker container.
"""
import re
from weasyprint import HTML

INPUT = "/tmp/case_study_iaf.md"
OUTPUT = "/tmp/case_study_iaf.pdf"

CSS = """
@page {
    size: A4;
    margin: 2cm 2.5cm;
    @bottom-center { content: counter(page); font-size: 9pt; color: #666; }
}
body {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #1a1a1a;
}
h1 {
    font-size: 20pt;
    color: #0a2540;
    border-bottom: 3px solid #0a2540;
    padding-bottom: 8px;
    margin-top: 0;
}
h2 {
    font-size: 15pt;
    color: #0a2540;
    border-bottom: 1px solid #ccc;
    padding-bottom: 4px;
    margin-top: 24px;
    page-break-after: avoid;
}
h3 {
    font-size: 12pt;
    color: #1a3a5c;
    margin-top: 18px;
    page-break-after: avoid;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 10pt;
    page-break-inside: avoid;
}
th {
    background: #0a2540;
    color: white;
    padding: 8px 10px;
    text-align: left;
    font-weight: 600;
}
td {
    padding: 6px 10px;
    border-bottom: 1px solid #ddd;
}
tr:nth-child(even) td { background: #f7f9fb; }
blockquote {
    border-left: 4px solid #0a2540;
    margin: 12px 0;
    padding: 8px 16px;
    background: #f0f4f8;
    font-style: italic;
    color: #333;
    page-break-inside: avoid;
}
hr {
    border: none;
    border-top: 2px solid #0a2540;
    margin: 24px 0;
}
strong { color: #0a2540; }
code {
    background: #f0f0f0;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 10pt;
}
.banner {
    background: #0a2540;
    color: white;
    text-align: center;
    padding: 6px;
    font-size: 10pt;
    font-weight: bold;
    letter-spacing: 2px;
    margin-bottom: 20px;
}
ul, ol { margin: 8px 0; padding-left: 24px; }
li { margin: 4px 0; }
p { margin: 8px 0; }
"""


def md_to_html(md: str) -> str:
    """Minimal markdown to HTML converter — handles what case study uses."""
    lines = md.split("\n")
    html_lines: list[str] = []
    in_table = False
    in_list = False
    in_blockquote = False
    in_ol = False
    bq_lines: list[str] = []

    def flush_bq():
        nonlocal in_blockquote, bq_lines
        if bq_lines:
            content = "<br>".join(bq_lines)
            html_lines.append(f"<blockquote>{content}</blockquote>")
            bq_lines = []
        in_blockquote = False

    def flush_list():
        nonlocal in_list
        if in_list:
            html_lines.append("</ul>")
            in_list = False

    def flush_ol():
        nonlocal in_ol
        if in_ol:
            html_lines.append("</ol>")
            in_ol = False

    def inline(text: str) -> str:
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        return text

    i = 0
    while i < len(lines):
        line = lines[i]

        # Blockquote
        if line.startswith("> ") or line.startswith(">"):
            if not in_blockquote:
                flush_list()
                flush_ol()
                in_blockquote = True
            bq_lines.append(inline(line.lstrip("> ")))
            i += 1
            continue
        elif in_blockquote:
            flush_bq()

        # Headings
        m = re.match(r'^(#{1,4})\s+(.+)', line)
        if m:
            flush_list()
            flush_ol()
            level = len(m.group(1))
            html_lines.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # HR
        if re.match(r'^---+\s*$', line):
            flush_list()
            flush_ol()
            html_lines.append("<hr>")
            i += 1
            continue

        # Table
        if "|" in line and not line.startswith(" "):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if cells:
                if not in_table:
                    flush_list()
                    flush_ol()
                    in_table = True
                    html_lines.append("<table>")
                    # Check if next line is separator
                    if i + 1 < len(lines) and re.match(r'^[\|\-\s:]+$', lines[i + 1]):
                        html_lines.append("<tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells) + "</tr>")
                        i += 2  # skip separator
                        continue
                html_lines.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
                continue
        elif in_table:
            html_lines.append("</table>")
            in_table = False

        # Unordered list
        m = re.match(r'^[-*]\s+(.+)', line)
        if m:
            flush_ol()
            if not in_list:
                in_list = True
                html_lines.append("<ul>")
            html_lines.append(f"<li>{inline(m.group(1))}</li>")
            i += 1
            continue
        elif in_list:
            flush_list()

        # Ordered list
        m = re.match(r'^\d+\.\s+(.+)', line)
        if m:
            flush_list()
            if not in_ol:
                in_ol = True
                html_lines.append("<ol>")
            html_lines.append(f"<li>{inline(m.group(1))}</li>")
            i += 1
            continue
        elif in_ol:
            flush_ol()

        # Empty line
        if not line.strip():
            i += 1
            continue

        # Paragraph
        html_lines.append(f"<p>{inline(line)}</p>")
        i += 1

    flush_bq()
    flush_list()
    flush_ol()
    if in_table:
        html_lines.append("</table>")

    return "\n".join(html_lines)


with open(INPUT) as f:
    md_text = f.read()

html_body = md_to_html(md_text)

full_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>{CSS}</style></head>
<body>
<div class="banner">FOR OFFICIAL USE ONLY</div>
{html_body}
<div class="banner" style="margin-top:30px">FOR OFFICIAL USE ONLY</div>
</body>
</html>"""

HTML(string=full_html).write_pdf(OUTPUT)
print(f"PDF written to {OUTPUT}")
