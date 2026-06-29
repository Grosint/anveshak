# NLP & Language Processing

6 learned instincts. Language detection, NLP enrichment, quality gates, model verification.

## Language Detection Must Not Gatekeep

- `detect_language()` returns real detected language — never filter by downstream model availability (spaCy, NLLB)
  Filtering on model support silently drops content, no error, pipeline completes w/ wrong results
  Each downstream stage decides independently: translate if needed, NER falls back to `en` model
  See: `learned/detect-language-must-not-gatekeep.md`

## NLP Results in Labels JSONB

- Sentiment + keywords stored in `content_items.labels` JSONB — no schema migration needed
  VADER (~0ms, rule-based) and YAKE (~5ms, statistical) are pure Python CPU-only
  Lazy singleton for ML models: load once per worker process
  When NOT to use: need JOINs, aggregate across millions, or enforce NOT NULL — use proper column
  See: `learned/nlp-results-in-jsonb-labels.md`

## Quality Gate at All Consumers

- Quality signal computed → apply filter at EVERY consumption point
  Checklist: SQL query, API response, clustering input, RAG context, report display
  `WHERE score IS NULL OR score >= threshold` — NULL = not yet scored, include for backward compat
  Per-topic override column w/ global fallback. Same `resolve_threshold()` pattern everywhere
  See: `learned/quality-gate-all-consumers.md`

## Unicode-Aware Word Counting

- Word-counting regex MUST cover all supported scripts — missing range = silent content drop (zero words)
  Latin `a-zA-Z`, Cyrillic `\u0400-\u04ff`, Arabic `\u0600-\u06ff`, Devanagari `\u0900-\u097f`, Bengali `\u0980-\u09ff`, CJK `\u4e00-\u9fff`
  Test quality gate w/ sample text from each language after adding ranges
  See: `learned/quality-gate-unicode-ranges.md`

## Quality Ratio Bypass on Length

- `clean_text >= 500 chars` → skip clean/raw ratio check. HTML-heavy sites produce 0.06-0.12 ratio on real articles
  MUST fire AFTER paywall + nav-icon gates — 500-char paywall page still garbage
  Below 500 chars, ratio check useful (short text from heavy page = likely nav fragment)
  See: `learned/quality-ratio-bypass-on-length.md`

## HuggingFace Model Label Order

- Always verify `id2label` from model `config.json` BEFORE writing inference code
  Different models use different orderings — index 0 can mean "fake" or "real", scores look plausible but inverted
  Use named constant (`FAKE_INDEX`), never bare `probs[1]`. Test download access inside Docker container (gated repos return 401)
  See: `learned/hf-model-label-order-verification.md`
