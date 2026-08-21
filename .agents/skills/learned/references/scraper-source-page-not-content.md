---
name: Source page is discovery, not content
description: When scraper_follow_links=True, source URL is fetched for link discovery only — never stored as content_item
type: pattern
confidence: high
---

## Problem

The scraper treated source URLs (e.g. `ndtv.com`) as both a content source AND a link discovery page. This caused:
- Homepages stored as content_items (Deccan Chronicle homepage scraped 370 times)
- Double HTTP fetch: Crawl4AI for content, then httpx for link extraction
- Garbage items entering clustering/signals pipeline

## Solution

Split `_process()` into two paths:

```python
if settings.scraper_follow_links:
    # Discovery mode: fetch HTML once for links, don't store source page
    html = await fetch_html(url)          # single httpx fetch
    article_links = extract_article_links(html, url)
    for link_url in article_links:
        # ... rate limit, URL-seen check, fetch, store ...
else:
    # Direct article mode: source URL IS the content (existing behavior)
    fetched = await fetch_url_with_crawler(url, crawler, run_cfg)
    await _insert_content(fetched, url, ...)
```

**Key rule:** The source URL's content is NEVER passed to `_insert_content()` when link-following is enabled. Only the discovered article links are stored.

## Why this matters

A homepage/index page will always pass quality gates after cleaning (it has text, it's not a paywall, it has reasonable ratio). The only reliable signal that it's NOT an article is that it's the *source URL itself* — which is architectural knowledge, not detectable by content analysis.

## Boundary case

When `scraper_follow_links=False`, the source URL IS a direct article link (e.g. `idrw.org/specific-article`). In this mode, the original store-as-content behavior must be preserved.
