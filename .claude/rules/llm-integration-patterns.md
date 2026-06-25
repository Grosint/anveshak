# LLM Integration Patterns

4 instincts. All LLM usage in reports, assessments, analysis.

## Stats-First, LLM-Second

Deterministic SQL stats = primary output. LLM narrative optional, async, fail-open.

**Phase 0:** Synchronous SQL stats (sub-second, zero hallucination risk)
**Phase 1:** Optional metadata enrichment via ARQ job (fail-open)
**Phase 2:** LLM brief as separate on-demand endpoint (POST .../brief → 202 + polling)

Frontend shows stats immediately. "Generate Brief" button for LLM.
`generated_at` stays NULL until LLM brief stored (immutability contract).

Anti-pattern: bundling stats + LLM into single async job. Analyst waits 60s for data returnable in 200ms.
See: `learned/stats-first-llm-second.md`

## Data-Driven Reports (90% SQL, 10% LLM)

Limited LLM quality (qwen2:7b) → flip ratio:
- 9 concurrent SQL queries via `asyncio.gather` for structured data
- `BlufContent` Pydantic model: `bluf: str`, `confidence_level: float`, `labels: Labels`
- Template fallback: LLM fails → generate BLUF from stats template (zero LLM dependency)
- `<!-- report-v2 -->` marker for backward compat detection

Report types control section depth, not separate templates:
- `intelligence_brief`: compact (top 10, active signals only)
- `research_summary`: full (all sources, top 30 entities, evidence appendix)
- `weekly_digest`: medium (top 10, trends, new signals this week)

Anti-pattern: asking 7B model to generate full structured JSON w/ executive_summary, key_findings, recommendations, legal_sections. Keep LLM scope minimal.
See: `learned/data-driven-reports-over-llm.md`

## Factual Sections Alongside LLM Output

Split report into two layers:

**Layer 1 (LLM):** analysis, synthesis, recommendations — Pydantic-validated, RAG-grounded w/ source citations.

**Layer 2 (DB-factual):** identifier tables, cluster summaries, template matches — from pre-aggregated DB tables, appended AFTER LLM output, never passed through LLM (no hallucination risk).

Inject factual data as READ-ONLY prompt context (boundary markers):
```
<identifier_intelligence>
IDENTIFIED INDICATORS: Phones: 9876543210 (5 sources), UPI: scammer@paytm (3 sources)
</identifier_intelligence>
```

LLM references identifiers in findings without fabricating.
Factual sections use `if data:` guards — omitted when empty, never crash.
See: `learned/factual-sections-alongside-llm.md`

## Template-Driven Actions, Not LLM-Generated

Recommended actions (freeze accounts, request CDR, file FIR) = high-stakes.
Map each scam template to curated, human-reviewed action list:

```python
_TEMPLATE_ACTIONS = {
    "mule_recruitment": ["Freeze accounts under PMLA Section 17", "Request CDR", "File STR"],
    "drug_sale": ["Request CDR/IP logs", "Coordinate NCB controlled delivery", "NDPS 20/22/25"],
}
```

Deterministic assembly from matched templates w/ dedup across overlapping matches.
Legal references exact (not hallucinated), reviewed by domain experts once.

LLM-generated actions appropriate ONLY for generic strategic recommendations ("monitor this topic", "increase collection") — stay in `recommendations` field.
Template-driven actions go in SEPARATE "Recommended Actions" section.
See: `learned/template-driven-actions-not-llm.md`