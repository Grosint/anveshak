# Content Quality & Relevance Filtering

Consolidated from 4 learned instincts. These apply to all content processing pipelines.

## Quality Gates — Apply Everywhere

- When you compute a quality signal (relevance score, word count, quality score),
  apply the filter at EVERY consumption point — not just one
  Checklist: SQL query → API response → clustering input → RAG context → report display
  Use `WHERE quality IS NULL OR quality >= threshold` for backward compat with pre-migration rows
  See: `learned/quality-gate-all-consumers.md`

## Unicode-Aware Word Counting

- Word-counting regex must cover all supported scripts:
  Latin `\w+`, Devanagari `[\u0900-\u097f]+`, Arabic `[\u0600-\u06ff]+`,
  CJK `[\u4e00-\u9fff]+`, Cyrillic `[\u0400-\u04ff]+`
  Missing ranges silently drop content (zero detected words → filtered out)
  See: `learned/quality-gate-unicode-ranges.md`

## Topic Relevance Gate

- After embedding content, compute cosine similarity against the topic query embedding
  Filter off-topic content BEFORE clustering (not after)
  Threshold calibration: plot histogram of similarity scores, set gate at the valley
  Default: `TOPIC_RELEVANCE_THRESHOLD=0.35`
  See: `learned/post-embedding-relevance-gate.md`

## Language Detection Independence

- `detect_language()` must return the real detected language, not filter based on
  whether a downstream model (spaCy, NLLB) supports it
  Filtering on model availability silently drops content with no log message
  Detection and processing are separate concerns — detect always, process if possible
  See: `learned/detect-language-must-not-gatekeep.md`
