# LLM Integration Patterns

Consolidated from 4 learned instincts. These apply to all LLM usage in reports, assessments, and analysis.

## Stats-First, LLM-Second

Always build deterministic SQL stats as the primary output. LLM narrative is optional,
async, and fail-open.

**Phase 0:** Synchronous SQL stats (sub-second, zero hallucination risk)
**Phase 1:** Optional metadata enrichment via ARQ job (fail-open)
**Phase 2:** LLM brief as separate on-demand endpoint (POST .../brief → 202 + polling)

Frontend shows stats immediately. "Generate Brief" button below for LLM.
`generated_at` stays NULL until LLM brief is stored (immutability contract).

Anti-pattern: bundling stats + LLM into a single async job. The analyst waits 60s
for data that could have been returned in 200ms.
See: `learned/stats-first-llm-second.md`

## Data-Driven Reports (90% SQL, 10% LLM)

When LLM quality is limited (qwen2:7b), flip the ratio:
- 9 concurrent SQL queries via `asyncio.gather` for structured data
- `BlufContent` Pydantic model: `bluf: str`, `confidence_level: float`, `labels: Labels`
- Template fallback: if LLM fails, generate BLUF from stats template (zero LLM dependency)
- `<!-- report-v2 -->` marker for backward compat detection

Report types control section depth, not separate templates:
- `intelligence_brief`: compact (top 10, active signals only)
- `research_summary`: full (all sources, top 30 entities, evidence appendix)
- `weekly_digest`: medium (top 10, trends, new signals this week)

Anti-pattern: asking a 7B model to generate full structured JSON with executive_summary,
key_findings, recommendations, legal_sections. Keep LLM scope minimal.
See: `learned/data-driven-reports-over-llm.md`

## Factual Sections Alongside LLM Output

Split report content into two layers:

**Layer 1 (LLM):** analysis, synthesis, recommendations — validated through Pydantic,
grounded in RAG context with source citations.

**Layer 2 (DB-factual):** identifier tables, cluster summaries, template matches —
fetched directly from pre-aggregated DB tables, appended AFTER LLM output,
never passed through LLM (no hallucination risk).

Inject factual data as READ-ONLY context in the prompt (boundary markers):
```
<identifier_intelligence>
IDENTIFIED INDICATORS: Phones: 9876543210 (5 sources), UPI: scammer@paytm (3 sources)
</identifier_intelligence>
```

LLM can reference identifiers in findings without fabricating them.
Factual sections use `if data:` guards — omitted when empty, never crash.
See: `learned/factual-sections-alongside-llm.md`

## Template-Driven Actions, Not LLM-Generated

Recommended actions (freeze accounts, request CDR, file FIR) are high-stakes.
Map each scam template to a curated, human-reviewed action list:

```python
_TEMPLATE_ACTIONS = {
    "mule_recruitment": ["Freeze accounts under PMLA Section 17", "Request CDR", "File STR"],
    "drug_sale": ["Request CDR/IP logs", "Coordinate NCB controlled delivery", "NDPS 20/22/25"],
}
```

Deterministic assembly from matched templates with deduplication across overlapping matches.
Legal section references are exact (not hallucinated), reviewed by domain experts once.

LLM-generated actions are appropriate ONLY for generic strategic recommendations
("monitor this topic", "increase collection") — these stay in the `recommendations` field.
Template-driven actions go in a SEPARATE "Recommended Actions" section.
See: `learned/template-driven-actions-not-llm.md`
