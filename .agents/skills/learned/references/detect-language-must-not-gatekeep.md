# Language Detection Must Not Gatekeep on Downstream Models

## Problem

`detect_language()` in `nlp.py` correctly detected non-English languages (zh, ru, hi, bn)
via langdetect, but then checked `if lang not in _MODELS` (spaCy models — English only)
and fell back to returning `"en"`. This meant `needs_translation("en")` returned `False`,
and **NLLB translation never triggered for any language**.

The entire multilingual pipeline was silently broken — non-English content was processed
as English through NER and embedding, producing garbage entities and wrong embeddings.

## Root Cause

Language detection was coupled to NER model availability. The function had two
responsibilities (detect language + check NER readiness) when it should have had one.

## Rule

`detect_language()` returns the **real detected language** — always. Each downstream
stage decides independently what to do with it:

```
detect_language("中国部署...") → "zh"        ← just detection, no gatekeeping
needs_translation("zh")       → True         ← translation decides
translate_to_english(text)    → English       ← NLLB handles it
parse_entities(english_text)  → uses en model ← NER falls back in _get_nlp()
```

If a function detects a value and also filters it, the filter will silently break
every consumer that needed the unfiltered value.

## Detection Pattern

When this bug is present, the only symptom is `translated=False` in analyst logs
for content that should have been translated. There's no error — the pipeline
completes successfully with wrong results.

**How we caught it**: The multilingual pipeline test (`scripts/test_multilingual_pipeline.py`)
runs real NLLB translation inside the container and asserts that key terms survive
the translate→NER chain. With the bug, NER returned Chinese characters as "entities"
instead of English terms.

## Files
- `services/analyst/anveshak/analyst/nlp.py` — `detect_language()` line 62-84
- `services/analyst/anveshak/analyst/jobs.py` — `analyse_content()` calls detect then translate
