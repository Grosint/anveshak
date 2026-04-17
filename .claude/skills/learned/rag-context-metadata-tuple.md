# RAG Context with Metadata Tuple

## When to load: enriching RAG prompts with source metadata (count, date range, credibility)

---

## Pattern

Return a tuple `(context_string, source_count, date_range)` from context assembly instead of just a string. Pass metadata to the prompt template so the LLM knows context breadth.

```python
# rag.py
def assemble_context(chunks, max_tokens) -> tuple[str, int, str]:
    parts, dates = [], []
    for chunk in chunks:
        cred = chunk.get("credibility_score_at_capture", 50.0)
        date_str = chunk.get("captured_at", "").strftime("%Y-%m-%d")

        header = f"[Source: {url} | Credibility: {cred:.1f} | {date_str}]"
        parts.append(f"{header}\n{text}\n\n")
        dates.append(date_str)

    sorted_dates = sorted(set(dates))
    date_range = f"{sorted_dates[0]} to {sorted_dates[-1]}"
    return "".join(parts), len(parts), date_range

# worker.py
context, source_count, date_range = assemble_context(chunks, max_tokens)
prompt = render_prompt(..., source_count=source_count, date_range=date_range)

# Template uses it:
# <context_metadata>5 sources, date range: 2026-04-10 to 2026-04-15</context_metadata>
```

**Why:** LLM can judge context freshness and breadth without parsing. Chunk headers let the LLM cite specific sources. Metadata is conditional in the template (`{% if source_count > 0 %}`).

---

## Pitfall: changing return type breaks mocks

When you change `-> str` to `-> tuple[str, int, str]`, ALL mocks that set `return_value="context text"` will break with `ValueError: too many values to unpack`.

**Fix pattern:** Search for all `patch("...assemble_context"` and update to `return_value=("context text", 1, "2026-01-01")`.

**Prevention:** Use a NamedTuple or dataclass instead of a bare tuple — mocks are clearer and less fragile.
