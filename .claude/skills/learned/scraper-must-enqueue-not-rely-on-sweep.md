# Scraper Must Enqueue analyse_content — Never Rely on Orphan Sweep

## Problem

The scraper inserted content_items rows but never enqueued `analyse_content` ARQ
jobs. It relied entirely on the analyst orphan sweep (1h window, 100 batch, 5min
interval) to discover new rows and enqueue them.

When scrape volume exceeded 100 items/hour, the sweep couldn't keep up. Items that
aged past the 1-hour window were permanently orphaned — no embedding, no relevance
score, no clustering, invisible to signals and reports.

243 orphaned items accumulated over 8 days (May 14–22). The temporal pattern was a
steady trickle (2-16 items/hour) not a single outage, confirming it was throughput
overflow, not a Redis failure.

## Root Cause

The insert + enqueue is not atomic (PostgreSQL and Redis aren't transactional
together). The orphan sweep was designed as a **safety net** for the rare case where
enqueue fails after insert. But when the scraper never enqueues at all, the sweep
becomes the **primary mechanism** — and it was never sized for that.

## Fix

Every content insert path must enqueue `analyse_content` directly:

```python
if result is not None:
    content_item_id = result["id"]
    try:
        await redis.enqueue_job(
            "analyse_content", content_item_id,
            _queue_name="arq:analyst",
        )
    except Exception as exc:
        log.warning("scraper.enqueue_analyse_failed",
                    content_item_id=content_item_id, error=str(exc))
    return content_item_id
```

All 3 scraper insert paths must do this: web (`_insert_content`), RSS (inline),
darkweb (`_insert_darkweb_content`). The social service already did this correctly
via `ingest_raw_item()`.

The orphan sweep remains as a safety net for enqueue failures — not as the primary
delivery mechanism.

## Diagnostic Pattern

To identify orphaned items: look for items where ALL NLP pipeline outputs are NULL
(embedding, translated_text, topic_relevance_score) — not just embedding. If all are
NULL, the job never ran. If only embedding is NULL, the job ran but failed mid-pipeline.

```sql
SELECT COUNT(*),
  COUNT(*) FILTER (WHERE translated_text IS NOT NULL) as has_translation,
  COUNT(*) FILTER (WHERE topic_relevance_score IS NOT NULL) as has_relevance
FROM content_items
WHERE embedding IS NULL AND content_quality = 'good';
-- All zeros = job never ran (enqueue problem)
-- Mixed = job ran but failed (processing problem)
```
