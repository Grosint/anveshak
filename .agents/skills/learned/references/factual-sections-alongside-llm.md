# Pattern: Factual Sections Alongside LLM Output

## When to load: adding structured data sections to LLM-generated reports

---

## Problem

Reports need both LLM-generated analysis (executive summary, findings) and
factual data (identifier tables, template matches, statistics). If you ask
the LLM to generate the factual sections, it will:

1. Hallucinate identifiers that don't exist
2. Miscount source frequencies
3. Miss identifiers the extraction pipeline found
4. Waste token budget on data already in the DB

---

## The Pattern

Split report content into two layers:

**Layer 1: LLM-generated** — analysis, synthesis, recommendations
- Validated through Pydantic (ReportContent model)
- Grounded in RAG context with source citations

**Layer 2: DB-factual** — identifier tables, cluster summaries, template matches
- Fetched directly from pre-aggregated DB tables
- Appended to content_md AFTER LLM output
- Rendered in PDF template with conditional blocks
- Never passed through LLM — no hallucination risk

**Prompt injection** — give the LLM factual data as READ-ONLY context:
```
<identifier_intelligence>
IDENTIFIED INDICATORS IN THIS TOPIC:
Phones: 9876543210 (5 sources)
UPI IDs: scammer@paytm (3 sources)
</identifier_intelligence>
```

This lets the LLM reference identifiers in findings without fabricating them.

---

## Implementation

```python
# Worker: fetch factual data alongside RAG chunks
identifiers = await db.fetch_topic_identifiers(pool, topic_id)
template_matches = await db.fetch_topic_template_matches(pool, topic_id)

# Inject summary into prompt (read-only context for LLM)
identifier_ctx = assemble_identifier_context(identifiers)
prompt = render_prompt(..., identifier_context=identifier_ctx)

# Append factual sections to content_md (NOT from LLM output)
content_md = _build_content_md(
    report_content,  # LLM layer
    identifiers=identifiers,  # DB-factual layer
    template_matches=template_matches,
)
```

---

## Key Rules

- Factual sections use `if data:` guards — omitted when empty, never crash
- Factual sections placed between Key Findings and Source Citations
- PDF template mirrors the same conditional structure
- `assemble_identifier_context()` formats for LLM consumption (text block)
- `_build_content_md()` formats for human consumption (Markdown table)
- These are DIFFERENT formats for DIFFERENT audiences

---

## Implementation reference
- `services/reporter/anveshak/reporter/worker.py` — `_build_content_md()` with identifier params
- `services/reporter/anveshak/reporter/rag.py` — `assemble_identifier_context()`
- `services/reporter/anveshak/reporter/pdf.py` — conditional identifier/template HTML blocks
