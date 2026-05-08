# Pattern: Unicode Range Coverage in Content Quality Gates

## When to load: modifying content_quality.py, adding new language support, debugging why content is silently dropped

---

## Problem

The content quality gate counts "words" using a regex to filter boilerplate. But the regex only included Latin, Cyrillic, Arabic, and CJK ranges — **Hindi (Devanagari) was missing**. All Hindi-only articles were silently dropped with 0 words detected → 0 embeddings → invisible to clustering.

## Solution

Always check the word-counting regex covers ALL supported NLLB languages:

```python
# BEFORE (missing Devanagari):
r"[a-zA-Z\u0400-\u04ff\u0600-\u06ff]{2,}|[\u4e00-\u9fff\u3400-\u4dbf]"

# AFTER (with Devanagari):
r"[a-zA-Z\u0400-\u04ff\u0600-\u06ff\u0900-\u097f]{2,}|[\u4e00-\u9fff\u3400-\u4dbf]"
```

## Unicode Ranges for Supported Languages

| Language | Script | Range | Pattern |
|----------|--------|-------|---------|
| English | Latin | U+0041-007A | `a-zA-Z` |
| Russian | Cyrillic | U+0400-04FF | `\u0400-\u04ff` |
| Arabic/Urdu | Arabic | U+0600-06FF | `\u0600-\u06ff` |
| Hindi | Devanagari | U+0900-097F | `\u0900-\u097f` |
| Bengali | Bengali | U+0980-09FF | `\u0980-\u09ff` |
| Chinese | CJK Unified | U+4E00-9FFF | `\u4e00-\u9fff` |

## Pitfall: Silent Failure

This bug is invisible — no error, no warning. The quality gate returns `False`, the item is logged as "skipped_quality" with `text_len=251`, and no embedding is generated. The only symptom is missing embeddings for non-Latin content.

**Always test the quality gate with sample text from each supported language after adding new Unicode ranges.**

## Files

- `services/analyst/anveshak/analyst/content_quality.py` — `is_quality_content()` word regex
