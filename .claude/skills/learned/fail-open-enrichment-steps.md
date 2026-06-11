# Pattern: Fail-Open on Non-Critical Enrichment Steps

## When to load: adding optional data enrichment to an existing pipeline

---

## Problem

Pipeline step A→B→C→D where step C adds optional enrichment data (identifiers,
metadata, labels). If C's DB query fails, the entire pipeline crashes — even
though A→B→D would produce a valid (if less rich) result.

In Engine C Step 9, `fetch_topic_identifiers` raising an exception killed
report generation entirely. The report was left in limbo (neither generated
nor explicitly failed).

---

## The Pattern

Wrap non-critical enrichment in try/except with:
1. Structured log warning (not silent)
2. Safe defaults (empty list/dict/None)
3. Downstream code already handles empty data via `if data:` guards

```python
# Fail-open: enrichment enhances output but is not required.
try:
    identifiers = await db.fetch_topic_identifiers(pool, topic_id)
    template_matches = await db.fetch_topic_template_matches(pool, topic_id)
except Exception:
    log.warning("reporter.identifier_fetch_failed",
                report_id=report_id, topic_id=topic_id)
    identifiers = []
    template_matches = []
```

---

## When to Apply

- Step is additive (adds sections/data to output, doesn't gate it)
- Output is valid without the enrichment data
- Downstream rendering uses `if data:` guards
- The critical path (LLM call, DB write) must not be blocked

## When NOT to Apply

- Step produces data that downstream steps REQUIRE (e.g., RAG chunks for LLM)
- Step validates data integrity (content_hash, dedup)
- Failure indicates a systemic issue that should halt processing

---

## Implementation reference
- `services/reporter/anveshak/reporter/worker.py` lines 125-134 — identifier fetch fail-open
- Downstream `_build_content_md()` already uses `if identifiers:` / `if template_matches:` guards
- PDF template uses `{% if report_data.get('identifiers') %}` conditional blocks
