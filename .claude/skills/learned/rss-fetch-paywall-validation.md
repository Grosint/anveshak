# RSS Fetch Paywall Validation

## When: enriching RSS entries with full-page fetches from paywalled news sites

## Problem

RSS feeds provide short summaries + article URLs. When the summary is too short
(`< rss_full_text_min_chars`), the scraper fetches the full article via Crawl4AI.
But metered-paywall sites (thehindu.com, etc.) return login/subscription wall HTML
instead of the article. The paywall text is long enough to pass the length check,
so it **replaces** the original RSS summary — making things worse, not better.

## Pattern

**Validate fetched content before accepting it as enrichment.**

```python
# In rss.py — after fetch_url() returns full_text:
full_text = await fetch_url(item.url)
if full_text and len(full_text.strip()) >= min_chars:
    stripped = full_text.strip()
    if is_paywall_page(stripped):
        log.warning("rss.paywall_detected", url=item.url)
        # Fall through to keep original RSS summary
    else:
        # Accept enriched content
        item.raw_text = stripped
        continue
# Keep original RSS summary as fallback
```

**`is_paywall_page()` uses indicator counting, not pattern matching:**
- Define a list of paywall-specific phrases ("you are logged in", "active subscription",
  "subscribers only", "sign in to read", etc.)
- Require 3+ distinct indicators to flag — avoids false positives on articles
  that mention subscriptions
- Runs on raw text before cleaning — catches the full paywall signal

## Why not just mark as low_quality?

Low-quality marking is a safety net, but the RSS summary (even if short) is more
useful than a paywall page. The correct fix is to **not replace good data with junk**,
then mark as low_quality as a secondary defense.

## Key insight

Length checks alone are insufficient for content enrichment. A paywall page can be
500+ chars of login form text. Always validate content semantics, not just length,
before accepting a replacement for existing data.
