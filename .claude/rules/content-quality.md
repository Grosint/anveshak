# Content Quality & Relevance Filtering

Consolidated from 9 learned instincts. These apply to all content processing pipelines.

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

## Pipeline Data Threading — Never Skip a Stage

- When querying content for a topic, always include BOTH `topic_id = $1` AND
  `id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1)`.
  Backfilled items are invisible if only the first path is used.
  See: `learned/cross-topic-join-table-queries.md`

- ARQ child jobs must be enqueued from the parent job (not the scheduler) with
  scope: `if clusters: enqueue("label_clusters", topic_id)`. Prevents empty
  enqueues and ensures the parent's output exists before the child runs.
  See: `learned/causal-arq-job-chaining.md`

## Credibility Flows Through the Pipeline

- `credibility_score_at_capture` is set at scrape/ingest time and NEVER updated
- RAG context assembly filters by `credibility_min` — low-credibility chunks
  are excluded from report prompts
- Report `source_snapshot` captures scores at generation time for audit trail
- If a source is later downgraded, `report_source_warnings` is inserted —
  the report itself is immutable (CLAUDE.md rule 4)

## Content Enrichment at Ingest Time

- Detect language at scrape time (`detect_language(clean_text)`) — not hardcoded "en"
- Score content quality at scrape time — enables filtering before clustering
- Compute `content_hash` (SHA-256) and `clean_hash` at scrape time for dedup
- Extract title at scrape time for display
