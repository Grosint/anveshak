# Anveshak — Tuning History & Parameter Rationale

This file records every parameter change, why it was made, and the evidence behind it.
**Check this file before suggesting parameter changes** — if a value was already tuned,
the rationale explains why it was set to its current value and what went wrong before.

---

## How to read this file

Each entry has:
- **Parameter**: the setting name and where it lives
- **Change**: old value → new value
- **Date**: when the change was made
- **Evidence**: what data drove the decision (query results, pipeline health output)
- **Rationale**: why this value, not another
- **Revert risk**: what would go wrong if someone reverts to the old value

---

## Content Quality Gate — Ratio Threshold

**Parameter:** `_MIN_QUALITY_RATIO` in `services/scraper/anveshak/scraper/clean.py`
**Change:** 0.15 → **0.08**
**Date:** 2026-05-26

**Evidence:**
- Pipeline health showed 53.3% of all content marked `low_quality` (3,164 of 5,939 items)
- The ratio gate (`clean_text / raw_text < 0.15`) was responsible for 62.5% of all rejections (1,978 items)
- 1,373 items in the 0.10–0.15 ratio band were a mix of real articles and garbage
- Real defence content from idrw.org (ratio 0.10, 2.2KB clean text about Indian Army SPAD-GMS procurement) was being falsely rejected
- Modern news sites serve 20–90KB of HTML for a 3–5KB article — ratio of 0.10–0.14 is normal for real articles on HTML-heavy sites

**Rationale:**
- 0.08 rescues real articles from HTML-heavy sites while still catching pure boilerplate (ratio < 0.05 = 138 items, nearly all garbage)
- Items in 0.05–0.08 band (467 items) are mostly category/index pages — safe to reject
- Combined with the 500-char length bypass (see below), this catches the right things

**Revert risk:** Setting back to 0.15 would re-reject ~1,373 items including real defence/intelligence articles from sites like idrw.org, NDTV article pages, and Deccan Chronicle articles. Topics like OCTOPUS would go back to 93.7% rejection rate.

---

## Content Quality Gate — Ratio Bypass for Long Text

**Parameter:** `_RATIO_BYPASS_MIN_CHARS` in `services/scraper/anveshak/scraper/clean.py`
**Change:** (new parameter) → **500**
**Date:** 2026-05-26

**Evidence:**
- Some real articles from extremely HTML-heavy sites have ratios below 0.08 but clean_text of 2–5KB
- The ratio check is a proxy for "is this a real article?" — but if we have 500+ chars of clean text, that's already a substantial article regardless of how bloated the raw HTML was
- The bypass fires AFTER the paywall and nav-icon gates — a 500-char paywall page is still rejected

**Rationale:**
- 500 chars is roughly 3–4 paragraphs of text — definitely an article, not a nav page
- The paywall gate (3+ indicator phrases) and nav-icon gate (40% icon vocabulary) still protect against long garbage pages
- Without this bypass, sites like Al Jazeera (ratio 0.06 due to massive JS bundles) would lose real articles even at the 0.08 threshold

**Revert risk:** Removing this bypass would re-reject articles from sites with extreme HTML-to-content ratios, even those with substantial clean text.

---

## Scraper — Max Links Per Page

**Parameter:** `scraper_max_links_per_page` in `services/scraper/anveshak/scraper/settings.py`
**Change:** 5 → **100**
**Date:** 2026-05-26

**Evidence:**
- With 5 links, the scraper was missing 90%+ of articles from each web source page
- For OSINT, every missed article is a potential missed corroboration for the signal engine
- A homepage typically has 50–200 article links — 5 captures only the first few

**Rationale:**
- 100 captures the vast majority of articles on any section/homepage
- Combined with Redis URL tracking (24h TTL), steady-state fetches are only ~15–20 new articles per cycle (the rest are skipped as already-seen)
- Combined with per-domain rate limiting (1.5s ± 0.5s), 100 links take ~2.5 min per source — well within the job timeout

**Revert risk:** Dropping back to 5 would miss 90%+ of articles from web sources. Signal engine would miss corroboration from articles that were never scraped.

---

## Scraper — Per-Domain Rate Limiting

**Parameter:** `scraper_per_domain_delay_s` in `services/scraper/anveshak/scraper/settings.py`
**Change:** (new parameter) → **1.5**
**Date:** 2026-05-26

**Parameter:** `scraper_per_domain_jitter_s` → **0.5**

**Evidence:**
- At 100 links per source without rate limiting, 100 rapid requests to the same domain would trigger WAF/CDN blocks (Cloudflare, Akamai → 403, CAPTCHA)
- News sites like NDTV, The Hindu typically rate-limit at ~50 requests/min from the same IP

**Rationale:**
- 1.5s base delay + 0.5s jitter = 1.0–2.0s between requests to same domain
- Different domains run in parallel (no cross-domain delay)
- At 1.5s average, 100 links = ~2.5 min per source — well within the 5-min job timeout
- Jitter makes the request pattern less robotic, reducing detection risk

**Revert risk:** Removing rate limiting with 100 links/page would cause immediate WAF blocks on major news sites.

---

## Scraper — URL-Seen Tracking

**Parameter:** `scraper_url_seen_ttl_s` in `services/scraper/anveshak/scraper/settings.py`
**Change:** (new parameter) → **86400** (24 hours)
**Date:** 2026-05-26

**Evidence:**
- Without URL tracking, the scraper re-fetched the same article URLs every cycle
- Deccan Chronicle homepage was fetched 370 times — content_hash dedup prevented duplicate DB rows but the HTTP request still happened every time
- With 100 links/page × 39 sources = 3,900 potential fetches per cycle — most are redundant

**Rationale:**
- 24h TTL: articles change rarely after publication. 24h covers multiple scrape cycles without risk of missing updates
- Redis key pattern `scraper:seen:{sha256(url)}` with auto-expiry — no manual cleanup needed
- Fail-open design: if Redis is down, URLs are fetched normally (no silent content loss)
- Steady-state reduction: ~85% fewer HTTP requests per cycle

**Revert risk:** Disabling URL tracking would cause 3,900 HTTP requests per cycle instead of ~585. Increases network load, risk of rate limiting, and Redis enqueue pressure.

---

## Scraper — Don't Store Source Page as Content

**Parameter:** Architectural change in `_process()` in `services/scraper/anveshak/scraper/jobs.py`
**Change:** Source URL content stored as content_item → Source URL used for link discovery only
**Date:** 2026-05-26

**Evidence:**
- Homepage content was being stored as content_items: Deccan Chronicle 370 times, The Hindu 326 times, NDTV 136 times, ToI 121 times
- These homepage items passed quality gates (especially after the ratio threshold change) and entered clustering, producing garbage clusters
- The source URL was fetched twice: once via Crawl4AI (for content), then again via httpx (for link extraction)

**Rationale:**
- When `scraper_follow_links=True`, the source URL is an index/discovery page, not an article — storing it is always wrong
- When `scraper_follow_links=False`, the source URL IS the article — existing behavior preserved
- Single httpx fetch for link discovery eliminates the redundant Crawl4AI fetch

**Revert risk:** Re-storing source pages would flood the pipeline with homepage garbage. With the 100-link cap, this would be less impactful than before (homepage is 1 item vs 100 articles), but it's still useless content that wastes embedding/clustering resources.

---

## Source Configuration — Homepage URLs to RSS Feeds

**Change:** Multiple web sources converted to RSS feeds
**Date:** 2026-05-26

| Source | Before | After |
|--------|--------|-------|
| Deccan Chronicle (×2) | `deccanchronicle.com` (web) | `deccanchronicle.com/feeds.xml` (rss) |
| NDTV (×3 web + 1 broken RSS) | `ndtv.com` + dead FeedBurner | `feeds.feedburner.com/ndtvnews-top-stories` (1 RSS, 6 topics) |
| India Today | `indiatoday.in` (web) | `indiatoday.in/rss/home` (rss) |
| The Hindu (×5 web + 1 RSS) | `thehindu.com` (web) | Existing RSS linked to all 8 topics |
| ToI (1 web + 1 RSS) | `timesofindia.indiatimes.com` (web) | Existing RSS linked to all 4 topics |
| RTI Kerala (×3 dupes) | 3 identical records | 1 record (2 dupes deleted) |

**Evidence:**
- RSS feeds return 20 article-level URLs per cycle — each is a real article
- Web homepage scraping produced 5 articles + 1 homepage garbage per cycle
- RSS is 4x more articles with zero garbage

**Rationale:**
- RSS is strictly superior for news sites: more articles, direct article URLs, no homepage garbage, no depth-crawling needed
- Web scraping reserved for niche sites without RSS (idrw.org, Bellingcat, defence.pk)

**Revert risk:** Switching back to homepage web scraping would reduce article volume by 4x and reintroduce homepage garbage.

---

## Garbage Cleanup

**Action:** Deleted 2,803 homepage/category content_items + 150,284 extracted_entities + 178 near_duplicates
**Date:** 2026-05-26

Deleted URLs include: all homepage/category pages for Deccan Chronicle, The Hindu, NDTV, ToI, Eenadu, India Today, Manorama, Mathrubhumi.

---

## Clustering — Leiden Edge Threshold

**Parameter:** `clustering_similarity_threshold` in `services/analyst/anveshak/analyst/settings.py`
**Change:** 0.70 → **0.55**
**Date:** 2026-05-26

**Evidence:**
- Pipeline health showed 49–95% of items unassigned across topics after all quality fixes
- LAC topic: 21 items scraped, only 1 assigned to a cluster (95% unassigned)
- IOR topic: 61 items scraped, 47 unassigned (77%)
- Pakistan LoC: 36 items, 24 unassigned (67%)
- Broad topics accept articles with relevance scores as low as 0.117 — these articles cover diverse sub-narratives (shipping, pirates, Chinese navy, Indian deployments) with pairwise cosine similarities of 0.30–0.55, well below the 0.70 edge threshold

**Rationale:**
- 0.55 allows articles with moderate similarity to form edges in the Leiden graph — creates more clusters (each covering a broader narrative)
- For OSINT, not missing signals (recall) matters more than cluster purity (precision)
- The near-duplicate threshold (0.95) is unchanged — it still prevents paraphrased articles from inflating ISC
- Entity MinHash blending (30% weight) helps compensate — articles sharing entities cluster together even at lower cosine similarity

**Revert risk:** Setting back to 0.70 would return to 49–95% unassigned items. Most articles would never enter clusters, never contribute to ISC, and never trigger signals. The signal engine becomes blind to narratives reported by diverse but moderately-similar sources.

---

## Clustering — Incremental Assign Threshold

**Parameter:** `cluster_assign_threshold` in `services/analyst/anveshak/analyst/settings.py`
**Change:** 0.70 → **0.60**
**Date:** 2026-05-26

**Evidence:**
- Same root cause as the Leiden edge threshold — new articles couldn't reach the 0.70 threshold to join existing clusters
- Incremental assignment (new items → nearest existing centroid) uses this threshold independently from Leiden
- Per configuration-hygiene rule: separate thresholds for separate mechanisms

**Rationale:**
- 0.60 is slightly higher than the Leiden threshold (0.55) because assignment to an existing centroid should be stricter than forming a new edge — the centroid represents the cluster's average meaning, so matching it at 0.60 is roughly equivalent to matching individual cluster members at 0.55
- Set independently per the "one setting, one purpose" rule

**Revert risk:** Setting back to 0.70 would cause new items to fail incremental assignment and fall through to full Leiden re-clustering. This wastes compute and can create redundant small clusters instead of growing existing ones.

---

## ISC — Count Distinct Sources, Not Platforms

**Parameter:** `count_independent_sources()` in `services/analyst/anveshak/analyst/clustering.py`
**Change:** `len(set(platforms))` → `len(set(source_ids))`
**Date:** 2026-05-27

**Evidence:**
- After consolidating NDTV, Hindu, ToI from web to RSS sources, all topics had max 2 platforms (rss + web)
- ISC=2 was the ceiling — impossible to reach ISC=3 even with 10 different news organisations all confirming the same narrative
- Example: NDTV RSS + Defense News RSS + The Hindu RSS all in same cluster = ISC 1 (all "rss") — should be ISC 3

**Rationale:**
- ISC measures source independence for corroboration. Three different news organisations reporting the same narrative IS corroboration, regardless of whether they deliver via RSS, web, or Telegram
- The SQL query changed from `SELECT DISTINCT s.platform` to `SELECT DISTINCT ci.source_id`
- `EmbeddingRow` field renamed from `platform` to `source_id`
- `ClusterData` field renamed from `platforms` to `source_ids`

**Revert risk:** Reverting to platform-based ISC would collapse all RSS sources into ISC=1, making it impossible for RSS-heavy topics to fire signals at threshold ≥ 2. This is especially critical after the source consolidation that moved most news sites to RSS.

---

## Parameters NOT YET Changed (candidates for future tuning)

| Parameter | Current | Candidate | Reason to consider |
|-----------|---------|-----------|-------------------|
| `BACKFILL_SIMILARITY_THRESHOLD` | 0.85 | 0.75 | Zero cross-topic matches found for 5 topics at 0.85 |
| `NEAR_DUPLICATE_SIMILARITY_THRESHOLD` | 0.95 | — | Working well, no change needed |
| `_NAV_ICON_HIT_RATIO` | 0.40 | — | Working well, occasional false positives on Al Jazeera |
| `_PAYWALL_THRESHOLD` | 3 indicators | — | Working well |
