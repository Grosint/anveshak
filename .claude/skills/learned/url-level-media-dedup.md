# Pattern: URL-Level Media Dedup (In-Memory Set per Job)

## When to load: any scraper/crawler job that downloads media assets from multiple pages

---

## Problem

During recursive scraping, the same image URL appears on multiple pages (e.g. site logo,
shared article thumbnail, CSS background). Each duplicate triggers an HTTP download,
even though the DB-level `ON CONFLICT(content_hash) DO NOTHING` prevents duplicates in storage.

The wasted bandwidth adds up: 50 pages × 3 shared images = 150 redundant HTTP requests.

---

## Solution: In-Memory URL Set per Job

Create a `set[str]` at the job level (not module level) and pass it through to the
media download function. Each URL is checked before downloading.

```python
async def scrape_topic(ctx: dict, topic_id: str) -> int:
    # ...
    seen_media_urls: set[str] = set()  # scoped to this job invocation

    async def _process(source, crawler, run_cfg):
        # ...
        await _download_page_media(
            page_url=url,
            topic_id=topic_id,
            content_item_id=content_item_id,
            db_pool=db_pool,
            redis=redis,
            seen_media_urls=seen_media_urls,  # shared across pages
        )
```

Inside the download function:

```python
async def _download_page_media(
    ...,
    seen_media_urls: set[str] | None = None,
) -> None:
    for media_url in media_urls:
        if seen_media_urls is not None:
            if media_url in seen_media_urls:
                continue
            seen_media_urls.add(media_url)
        # ... proceed with download
```

---

## Why Not Module-Level or Redis?

| Approach | Pros | Cons |
|----------|------|------|
| Job-scoped `set()` | Zero latency, no coordination | Only deduplicates within one job run |
| Module-level `set()` | Cross-job dedup | Memory leak, stale across restarts |
| Redis `SISMEMBER` | Cross-worker dedup | Network RTT per URL, overkill |
| DB pre-check | Hash-level accuracy | Query per URL, defeats bandwidth saving |

Job-scoped is the right trade-off: catches the most common case (repeated images on a single
site during one scrape) with zero infrastructure overhead.

---

## When the Set Naturally Clears

The set is garbage-collected when the job function returns. Next invocation starts fresh.
This is intentional — between scrape runs, images may have changed at the same URL.

---

## Implementation reference
- `services/scraper/anveshak/scraper/jobs.py` — `seen_media_urls` in `scrape_topic()`
