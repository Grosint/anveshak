# Data-Driven Reports Over LLM-Heavy Reports

## Pattern
When LLM quality is low (small model, qwen2:7b), flip the ratio: compute 90% of report content from deterministic SQL queries and use LLM only for a short summary paragraph (BLUF).

## Why
qwen2:7b generates mediocre prose — vague, repetitive, sometimes hallucinated. But the data already exists in PostgreSQL: source inventories, entity counts, cluster labels, signal descriptions, content snippets. Presenting this data in structured tables/cards is more useful to analysts than bad LLM prose.

## Structure
1. `fetch_report_data_bundle()` — 9 concurrent SQL queries via `asyncio.gather`
2. `BlufContent` — minimal Pydantic model: `bluf: str`, `confidence_level: float`, `labels: Labels`
3. `render_bluf_prompt()` — short prompt with pre-computed stats + cluster summaries as context
4. `_build_content_md_v2()` — assembles markdown tables from SQL data + BLUF paragraph
5. Template fallback — if LLM fails, generate BLUF from stats template (zero LLM dependency)

## Section structure by report_type
- `intelligence_brief`: compact (top 10 sources/entities, active signals only, no evidence appendix)
- `research_summary`: full (all sources, top 30 entities, evidence appendix, methodology)
- `weekly_digest`: medium (top 10, trend focus, new signals this week)

## Key decisions
- `<!-- report-v2 -->` marker on first line of content_md for backward compat detection
- Old `_build_content_md()` preserved for v1 reports
- PDF template auto-selects v1 or v2 based on `topic_stats` key presence
- Report type controls section depth, not separate templates

## Anti-pattern
Asking a 7B model to generate a full structured JSON report with executive_summary, key_findings, recommendations, legal_sections, three_lens evaluation. The model can't do it reliably. Keep LLM scope minimal.
