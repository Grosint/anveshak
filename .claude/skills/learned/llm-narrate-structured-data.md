# LLM Should Narrate Structured Data, Not Discover It

## Pattern

When using a small LLM (7B) to generate labels/summaries, feed it **pre-computed structured context** — don't ask it to discover patterns from raw text.

## Why

qwen2:7b given raw text snippets produces entity-soup labels ("TGCSB — Telangana — Hyderabad"). Same model given structured context (entity table, platform breakdown, scam templates, identifier counts) produces actionable labels ("Mule account recruitment via Telegram").

The pipeline already computes intelligence (Engine C templates, entity extraction, identifier clustering). The LLM's job is to **narrate**, not **analyse**.

## Implementation

Build prompt with structured blocks:
1. Topic name + keywords (context)
2. Entity table with types and counts (who/what/where)
3. Platform breakdown with source names (provenance)
4. Detected scam templates from labels JSONB (crime type)
5. Identifier counts (actionable indicators)
6. Text excerpts LAST (supporting evidence)

Use single CTE query to fetch all context in one round-trip.

## Anti-pattern

```python
# BAD — raw text, LLM must discover everything
excerpts = "\n\n".join(t[:300] for t in texts)
prompt = f"Label this cluster:\n{excerpts}"

# GOOD — structured context, LLM narrates
prompt = f"""Topic: {topic_name}
Entities: ORG: TGCSB (30), GPE: Hyderabad (15)
Sources: 3 Telegram channels, 2 RSS feeds
Detected patterns: mule_recruitment (5 items)
Identifiers: 3 phones, 2 UPI IDs

{boundary}{excerpts}{boundary}"""
```

## Results

- LLM success: labels like "Pump and Dump Scheme Promotion via Telegram" (0.85 confidence)
- Fallback (LLM fails): "Telangana Cyber Fraud Intelligence: TGCSB, Hyderabad" — still useful because topic name provides context

## See also

- `learned/data-driven-reports-over-llm.md` — same principle for reports (90% SQL, 10% LLM)
- `learned/stats-first-llm-second.md` — deterministic data first, LLM narrative optional
