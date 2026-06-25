# Content Quality & Relevance Filtering

Consolidated from 13 learned instincts. These apply to all content processing pipelines.

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

## Per-Topic Relevance Auto-Calibration

- A global relevance threshold fails for mixed-breadth topics (IOR median 0.14 vs LAC 0.26)
  Use PERCENTILE_CONT of each topic's score distribution to auto-set per-topic thresholds
  Clamp to [floor=0.08, ceiling=0.50], skip topics with < 20 scored items
  Runs on startup + every 6h in analyst-scheduler; `topics.topic_relevance_threshold` column
  Global default (0.35) is fallback only for topics without enough data
  See: `learned/per-topic-relevance-auto-calibration.md`

## URL-Level Deduplication

- Use in-memory URL set per scrape job to skip duplicate media downloads
  Redis URL dedup: SHA-256 key with 24h TTL, fail-open on Redis errors
  Mark URL as seen AFTER successful insert (not before fetch) to avoid missing content on retry
  See: `learned/redis-url-dedup-sha256-ttl.md`, `learned/url-level-media-dedup.md`

## RSS/Web Paywall Validation

- When fetching full article text from RSS links, validate content BEFORE replacing summary
  Count paywall indicators ("subscribe", "premium content", "sign in to read")
  If paywall detected: keep RSS summary, mark source as "degraded" (not "down")
  Bypass clean/raw ratio check if `clean_text >= 500 chars` — fires AFTER paywall gates
  See: `learned/rss-fetch-paywall-validation.md`, `learned/quality-ratio-bypass-on-length.md`

## NLP Results in Labels JSONB

- Sentiment scores and keywords are stored in `content_items.labels` JSONB (not separate columns)
  Thread through CTE UNION ALL + DISTINCT ON dedup for API surfacing
  Post-process in Python to extract sentiment/keywords from labels dict
  See: `learned/nlp-results-in-jsonb-labels.md`, `learned/jsonb-labels-api-surfacing.md`

## Content Enrichment at Ingest Time

- Detect language at scrape time (`detect_language(clean_text)`) — not hardcoded "en"
- Score content quality at scrape time — enables filtering before clustering
- Compute `content_hash` (SHA-256) and `clean_hash` at scrape time for dedup
- Extract title at scrape time for display
