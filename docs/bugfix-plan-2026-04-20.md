# Anveshak Bug Fix Plan — 2026-04-20

## Bugs Overview

| # | Bug | Severity | Service |
|---|-----|----------|---------|
| B1 | Report history not showing after selecting a topic | HIGH | api + frontend |
| B2 | Reporter worker crash: `'str' object has no attribute 'keys'` | CRITICAL | reporter |
| B3 | Duplicate records within a topic (dual scraping) | HIGH | scraper |
| B4 | Scraper worker TimeoutError (~125s) | MEDIUM | scraper |
| B5 | No recursive scraping (articles not followed for full content) | MEDIUM | scraper |

---

## B1 — Report History Not Loading

**Symptom:** After selecting a topic in the frontend, the "History" tab shows no reports even though reports exist in the database.

**Root Cause:** The `list_topic_reports` SQL query returns raw rows without a `generation_status` field. The frontend `ReportBuilder.tsx` relies on this field to render report cards. The single-report endpoint (`GET /reports/{id}`) computes `generation_status` from `generated_at` / `generation_error`, but the list endpoint does not.

**Files:**
- `services/api/anveshak/api/db/reports.py` — `SQL_LIST_TOPIC_REPORTS` missing status derivation
- `services/api/anveshak/api/routes/reports.py:128-135` — `list_topic_reports` returns raw rows

**Fix:** Add `generation_status` computation in the list endpoint (either via SQL CASE expression or in the route handler).

---

## B2 — Reporter Worker `check_source_warnings` Crash

**Symptom:** Cron job `check_source_warnings` fails every cycle with:
```
AttributeError: 'str' object has no attribute 'keys'
```
at `services/reporter/anveshak/reporter/worker.py:295`.

**Root Cause:** `source_snapshot` is stored as JSONB in PostgreSQL. When asyncpg retrieves it without a registered JSON codec, it returns a JSON **string** instead of a Python **dict**. Line 295 calls `snapshot.keys()` which fails on a string.

**Code:**
```python
# worker.py:291-295 — current (broken)
snapshot: dict[str, Any] = report.get("source_snapshot") or {}
if not snapshot:
    continue
source_ids = list(snapshot.keys())  # ← crashes when snapshot is a str
```

**Fix:** Add defensive JSON parsing:
```python
snapshot = report.get("source_snapshot") or {}
if isinstance(snapshot, str):
    snapshot = json.loads(snapshot)
if not snapshot:
    continue
source_ids = list(snapshot.keys())
```

---

## B3 — Duplicate Records (Dual Scraping)

**Symptom:** Same article appears multiple times within a single topic.

**Root Cause (architectural gap):** Sources are **global** — there is no `topic_sources` join table or `topic_id` on the `sources` table. When `scrape_topic(topic_id)` runs, it fetches **ALL** active web sources and **ALL** active RSS sources, regardless of topic.

```sql
-- jobs.py:38-43 — no topic filter
SELECT s.id, s.url_or_handle, s.credibility_score
FROM sources s
WHERE s.is_active = TRUE AND s.platform = 'web'
  AND s.health_status != 'down'
```

This causes two duplicate pathways:

1. **Cross-topic duplication:** 3 topics × 10 sources = every source scraped 3 times per cycle. `ON CONFLICT(content_hash) DO NOTHING` prevents exact duplicates, but the first topic to insert "wins" and subsequent topics silently lose the content.

2. **Within-topic duplication:** If the same URL exists as both a `web` source and an `rss` source, `scrape_topic` and `poll_rss_sources` both fetch it. Crawl4AI (JS-rendered) and trafilatura (HTML-only) can extract slightly different text → different `content_hash` → two rows for the same article.

**Fix — new `topic_sources` join table:**

```sql
CREATE TABLE topic_sources (
    topic_id   UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    source_id  UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    added_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (topic_id, source_id)
);
```

Then update the scraper queries to scope by topic:

```sql
SELECT s.id, s.url_or_handle, s.credibility_score
FROM sources s
JOIN topic_sources ts ON ts.source_id = s.id
WHERE ts.topic_id = $1
  AND s.is_active = TRUE AND s.platform = 'web'
  AND s.health_status != 'down'
```

**Additional changes needed:**
- New API endpoints: `POST/DELETE /api/v1/topics/{id}/sources/{source_id}` to manage associations
- Frontend: source picker when creating/editing a topic
- Migration: auto-populate `topic_sources` from existing `content_items` (backfill existing associations)
- Update `scrape_topic` and `poll_rss_sources` in `jobs.py` to accept and use `topic_id` in source queries

---

## B4 — Scraper Worker TimeoutError

**Symptom:** Multiple `scrape_topic` jobs fail after ~120-128 seconds with `TimeoutError`. Stack trace shows Crawl4AI browser launch (`playwright.chromium.launch`) getting cancelled by ARQ's `wait_for`.

**Root Cause:** Two compounding issues:

1. **ARQ job timeout too short:** `job_timeout = 120` seconds (jobs.py:407), but each Crawl4AI fetch spawns a **new Chromium browser** (fetch.py:62). Browser startup alone takes 2-3 seconds. With 5 concurrent sources at 30s timeout each, the math barely fits — and if any source is slow, the entire job exceeds 120s.

2. **No browser reuse:** Every call to `_crawl4ai_fetch()` creates and destroys a full browser instance:
   ```python
   async with AsyncWebCrawler(config=browser_cfg) as crawler:
       result = await crawler.arun(url=url, config=run_cfg)
   # browser destroyed here — next URL starts a new one
   ```

**Fix:**
- Increase `job_timeout` to 300 seconds (5 min) — configurable via `SCRAPER_JOB_TIMEOUT_S` env var
- Refactor `_crawl4ai_fetch` to accept a shared `AsyncWebCrawler` instance, created once per `scrape_topic` job and reused across all URLs
- Wrap individual `_process` calls with `asyncio.wait_for(per_url_timeout)` so one slow URL doesn't block others
- Add graceful error handling: if browser launch fails, fall back to trafilatura immediately

**Timeout budget after fix:**
```
300s job timeout
  └─ 5 concurrent slots × 30s per-URL timeout = 150s worst case
  └─ browser startup: 3s (once, shared)
  └─ headroom: ~147s for retries and media download
```

---

## B5 — No Recursive Scraping

**Symptom:** Scraper fetches only the source URL itself. If a source is a news index page (e.g., globalsecurity.org/military), only the index HTML is captured — not the linked articles.

**Current behaviour:** `fetch_url(url)` fetches one page, extracts text, returns it. No link following.

**Fix — depth-1 article extraction:**

Add a `_extract_article_links` helper that parses the fetched HTML for article hyperlinks, then fetches each linked article through the same pipeline:

```python
# New settings
scraper_follow_links: bool = True          # enable recursive scraping
scraper_max_links_per_page: int = 5        # cap followed links
scraper_follow_same_domain_only: bool = True
```

**Behaviour:**
1. Fetch source URL → extract clean text (existing)
2. If `scraper_follow_links` is enabled, parse HTML for `<a href>` links
3. Filter: same-domain only, skip media/PDF/anchor links, cap at `max_links_per_page`
4. Fetch each linked article through `fetch_url` (no further recursion — depth=1 only)
5. Each followed article goes through `compute_content_hash` → `ON CONFLICT DO NOTHING` dedup

**Safeguards:**
- Hard cap: depth=1 only (never follow links from followed pages)
- Max 5 links per source page (configurable)
- Same per-URL timeout applies to followed links
- All dedup rules apply — no duplicate content from link following

---

## Implementation Phases

### Phase 1 — Quick Fixes (B1 + B2)
**Effort:** ~1 hour | **Risk:** LOW | **Dependencies:** None

| Task | File | Change |
|------|------|--------|
| Fix snapshot string→dict | `services/reporter/.../worker.py:291` | Add `json.loads` guard |
| Add generation_status to list | `services/api/.../db/reports.py` | SQL CASE or route logic |
| | `services/api/.../routes/reports.py` | Compute status in list endpoint |

### Phase 2 — Scraper Fixes (B3 + B4)
**Effort:** ~3-4 hours | **Risk:** MEDIUM | **Dependencies:** None (parallel with Phase 1)

| Task | File | Change |
|------|------|--------|
| Create `topic_sources` table | New migration | Join table + backfill |
| Topic-scoped source queries | `services/scraper/.../jobs.py` | Filter sources by topic |
| API endpoints for topic-source mgmt | `services/api/.../routes/topics.py` | POST/DELETE source associations |
| Frontend source picker | `frontend/src/` | UI to assign sources to topics |
| Increase job timeout | `services/scraper/.../jobs.py:407` | 120 → 300 (env var) |
| Browser reuse | `services/scraper/.../fetch.py` | Shared crawler instance |
| Per-URL timeout guard | `services/scraper/.../jobs.py` | `asyncio.wait_for` per source |

### Phase 3 — Recursive Scraping (B5)
**Effort:** ~2 hours | **Risk:** MEDIUM | **Depends on:** Phase 2 (browser reuse)

| Task | File | Change |
|------|------|--------|
| Link extraction helper | `services/scraper/.../fetch.py` | New `_extract_article_links` |
| Deep fetch integration | `services/scraper/.../jobs.py` | Follow links in `_process` |
| New settings | `services/scraper/.../settings.py` | `follow_links`, `max_links_per_page` |

---

## Architecture Decision: `topic_sources` Join Table

This is the most significant change. After this fix, the data model becomes:

```
topics ──┬── topic_sources ──┬── sources
         │                   │
         └── content_items ──┘
```

- **Before:** Sources are global. Every scrape job scrapes every source for every topic.
- **After:** Sources are associated per-topic. Each topic only scrapes its own sources.
- **Migration:** Backfill `topic_sources` from existing `content_items` (SELECT DISTINCT topic_id, source_id).
- **CLAUDE.md update:** Document the `topic_sources` relationship as a canonical architectural rule.

---

## Testing Plan

- [ ] B1: Generate a report for a topic → verify history tab shows it with correct status
- [ ] B2: Start reporter worker → verify `check_source_warnings` cron completes without crash
- [ ] B3: Assign 2 sources to topic A, 3 different sources to topic B → scrape → verify no cross-contamination
- [ ] B3: Verify existing content_items are correctly backfilled into `topic_sources`
- [ ] B4: Add 10+ sources to a topic → verify scrape completes within 300s without timeout
- [ ] B4: Verify browser is launched once per job, not per URL (check logs)
- [ ] B5: Add a news index page as source → verify linked articles are scraped (depth=1)
- [ ] B5: Verify followed links respect `max_links_per_page` cap
- [ ] Regression: All existing unit + e2e tests still pass
