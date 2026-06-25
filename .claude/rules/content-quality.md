# Content Quality & Relevance Filtering

13 learned instincts. All content processing pipelines.

## Quality Gates — Apply Everywhere

- Quality signal computed → apply filter at EVERY consumption point, not one
  Checklist: SQL query → API response → clustering input → RAG context → report display
  `WHERE quality IS NULL OR quality >= threshold` for backward compat with pre-migration rows
  See: `learned/quality-gate-all-consumers.md`

## Unicode-Aware Word Counting

- Word-counting regex must cover all scripts:
  Latin `\w+`, Devanagari `[\u0900-\u097f]+`, Arabic `[\u0600-\u06ff]+`,
  CJK `[\u4e00-\u9fff]+`, Cyrillic `[\u0400-\u04ff]+`
  Missing ranges silently drop content (zero words → filtered out)
  See: `learned/quality-gate-unicode-ranges.md`

## Topic Relevance Gate

- After embedding, compute cosine similarity against topic query embedding
  Filter off-topic BEFORE clustering (not after)
  Threshold calibration: plot similarity histogram, set gate at valley
  Default: `TOPIC_RELEVANCE_THRESHOLD=0.35`
  See: `learned/post-embedding-relevance-gate.md`

## Language Detection Independence

- `detect_language()` must return real detected language, not filter by downstream model support (spaCy, NLLB)
  Filtering on model availability silently drops content, no log
  Detection and processing separate concerns — detect always, process if possible
  See: `learned/detect-language-must-not-gatekeep.md`

## Pipeline Data Threading — Never Skip a Stage

- Topic content queries must include BOTH `topic_id = $1` AND
  `id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1)`.
  Backfilled items invisible if only first path used.
  See: `learned/cross-topic-join-table-queries.md`

- ARQ child jobs enqueued from parent job (not scheduler) with
  scope: `if clusters: enqueue("label_clusters", topic_id)`. Prevents empty
  enqueues, ensures parent output exists before child runs.
  See: `learned/causal-arq-job-chaining.md`

## Credibility Flows Through the Pipeline

- `credibility_score_at_capture` set at scrape/ingest time, NEVER updated
- RAG context filters by `credibility_min` — low-credibility chunks excluded from report prompts
- Report `source_snapshot` captures scores at gen time for audit
- Source later downgraded → `report_source_warnings` inserted — report immutable (CLAUDE.md rule 4)

## Per-Topic Relevance Auto-Calibration

- Global threshold fails for mixed-breadth topics (IOR median 0.14 vs LAC 0.26)
  PERCENTILE_CONT of each topic's score distribution → auto per-topic thresholds
  Clamp [floor=0.08, ceiling=0.50], skip topics < 20 scored items
  Runs startup + every 6h in analyst-scheduler; `topics.topic_relevance_threshold` column
  Global default (0.35) fallback for topics without enough data
  See: `learned/per-topic-relevance-auto-calibration.md`

## URL-Level Deduplication

- In-memory URL set per scrape job skips duplicate media downloads
  Redis URL dedup: SHA-256 key, 24h TTL, fail-open on Redis errors
  Mark URL seen AFTER successful insert (not before fetch) — avoids missing content on retry
  See: `learned/redis-url-dedup-sha256-ttl.md`, `learned/url-level-media-dedup.md`

## RSS/Web Paywall Validation

- Fetching full article from RSS: validate content BEFORE replacing summary
  Count paywall indicators ("subscribe", "premium content", "sign in to read")
  Paywall detected → keep RSS summary, mark source "degraded" (not "down")
  Bypass clean/raw ratio check if `clean_text >= 500 chars` — fires AFTER paywall gates
  See: `learned/rss-fetch-paywall-validation.md`, `learned/quality-ratio-bypass-on-length.md`

## NLP Results in Labels JSONB

- Sentiment + keywords stored in `content_items.labels` JSONB (not separate columns)
  Thread through CTE UNION ALL + DISTINCT ON dedup for API surfacing
  Post-process in Python to extract sentiment/keywords from labels dict
  See: `learned/nlp-results-in-jsonb-labels.md`, `learned/jsonb-labels-api-surfacing.md`

## Content Enrichment at Ingest Time

- Detect language at scrape time (`detect_language(clean_text)`) — not hardcoded "en"
- Score content quality at scrape time — enables filtering before clustering
- Compute `content_hash` (SHA-256) and `clean_hash` at scrape time for dedup
- Extract title at scrape time for display