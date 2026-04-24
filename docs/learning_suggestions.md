# Learning Suggestions

Improvements identified during codebase deep-dive. Will implement after learning is complete.

---

## 1. Orphaned Source Warning + Better Auto-Linking

**Problem:** When a source is created from the Sources page (not from within a topic), no `topic_id` is passed, so the source is created but never scraped. The analyst has no indication that the source is orphaned.

**Current behavior:**
- `POST /api/v1/sources` accepts optional `topic_id` -- auto-links if provided
- Creating from within a topic page works (topic_id is in context)
- Creating from the global Sources page does NOT link to any topic
- No warning shown anywhere that the source has zero topic links

**Suggested fix (3 parts):**

1. **API: Add a `topic_links_count` field to source list response** -- return how many topics each source is linked to. Sources with 0 links are visually flagged.

2. **Frontend: Show warning badge on orphaned sources** -- in `SourceManager.tsx`, sources with `topic_links_count == 0` get an amber "Not linked to any topic" badge. Clicking it opens a topic-picker modal.

3. **Frontend: When creating a source from Sources page, show topic multi-select** -- let the analyst pick one or more topics to link at creation time, rather than requiring them to navigate to each topic separately.

**Files involved:**
- `services/api/anveshak/api/routes/sources.py` -- add count to list query
- `services/api/anveshak/api/db/sources.py` -- SQL join on topic_sources for count
- `frontend/src/pages/SourceManager.tsx` -- warning badge + topic picker
- `frontend/src/components/sources/AddSourceModal.tsx` -- topic multi-select

---

## 2. Skip Redundant Media Downloads (Pre-check by URL or Hash)

**Problem:** When the same image appears on multiple websites (different URLs, identical bytes), Anveshak downloads it every time. The DB dedup works (ON CONFLICT DO NOTHING), and the file overwrite is harmless (same hash = same filename), but the HTTP download bandwidth is wasted.

**Current behavior:**
- `download_media_asset()` in `sdk/anveshak/media/downloader.py` always downloads first, computes SHA-256 after
- `SQL_INSERT_MEDIA_ASSET` uses `ON CONFLICT(content_hash) DO NOTHING` -- DB is clean
- File on disk is overwritten with identical bytes (same content_hash = same filename)
- Vision analysis is idempotent (UNIQUE on media_asset_id) so no duplicate work there
- Only real cost: wasted HTTP download bandwidth

**Suggested fix (2 options, pick one):**

1. **URL-level dedup (lightweight):** Before downloading, check if `media_url` was already seen in this scrape batch. Maintain an in-memory `set()` of URLs per `scrape_topic` job. Skips exact URL duplicates but not same-image-different-URL.

2. **Hash-level pre-check (thorough):** After downloading but before writing to disk, query `SELECT id FROM media_assets WHERE content_hash = $1`. If exists, skip the disk write and vision dispatch. This saves disk I/O but still does the HTTP download. The only way to avoid the download entirely would be server-side ETag/If-None-Match caching, which adds complexity.

**Recommendation:** Option 1 (URL set) is simple and catches the most common case (same `<img src>` appearing in multiple pages from recursive scraping). Option 2 adds a DB query per media URL which may not be worth it.

**Files involved:**
- `services/scraper/anveshak/scraper/jobs.py` -- `_download_page_media()` function, add URL set parameter
- `sdk/anveshak/media/downloader.py` -- no changes needed for option 1

---

## 3. Improve Report Geocoding (Use NER Entities Instead of Regex)

**Problem:** The reporter's geocoder uses a simple regex (`\b[A-Z][a-z]+...\b`) to find location names in the LLM output, then filters against geonamescache (~24K cities + countries). This misses:
- Multi-word regions: "South China Sea", "Andaman Islands", "Line of Actual Control"
- Provinces/states: "Hainan", "Balochistan", "Xinjiang"
- Military installations: "Chandigarh Air Force Station", "INS Kadamba"
- Abbreviated names: "NYC", "UK", "UAE", "PoK"
- Non-English transliterations from translated content

**Current behavior:**
- `extract_locations_from_text()` in `services/reporter/anveshak/reporter/geocoder.py` uses regex + geonamescache filter
- Only matches single/two capitalized words that happen to be in the geonamescache city or country database
- Countries are resolved to their capital city coordinates (India → New Delhi), which is misleading when the report discusses border regions
- Reporter service intentionally does NOT load spaCy (too heavy, ~2GB models)

**Suggested fix (3-layer approach):**

1. **Use extracted_entities from the analyst pipeline (primary source).** The analyst already runs spaCy NER on every content item and stores LOCATION/GPE/FACILITY entities in `extracted_entities`. The reporter should query these entities for the topic's content items instead of re-extracting from LLM text. This is more accurate because spaCy NER is far better than regex, and the entities already exist — zero extra ML cost.

   ```sql
   SELECT DISTINCT ee.entity_text
   FROM extracted_entities ee
   JOIN content_items ci ON ee.content_item_id = ci.id
   WHERE ci.topic_id = $1
     AND ee.entity_type IN ('GPE', 'LOC', 'FACILITY')
     AND ee.confidence >= 0.8
   ```

2. **Also extract from LLM output (secondary, current approach).** Keep the regex extraction as a fallback for locations the LLM synthesizes that weren't in any single source (e.g., LLM infers "India-China border" from context).

3. **Expand geonamescache with a custom overlay.** Add a small JSON file `infra/configs/geocoder/custom_locations.json` with defence-relevant locations that geonamescache doesn't have:
   ```json
   {
     "Andaman Islands": [11.74, 92.65],
     "Line of Actual Control": [34.0, 78.0],
     "South China Sea": [12.0, 113.0],
     "Ladakh": [34.16, 77.58],
     "PoK": [34.0, 74.0],
     "INS Kadamba": [14.79, 74.10]
   }
   ```
   Loaded at startup alongside geonamescache. Analyst can add entries via a config file without code changes.

**Why this is better:**
- Layer 1 reuses work the analyst already did (zero extra compute)
- Layer 2 catches LLM-synthesized location references
- Layer 3 handles defence-specific locations that no general database will have
- All offline, no API calls (sovereign requirement preserved)

**Files involved:**
- `services/reporter/anveshak/reporter/geocoder.py` -- add `geocode_from_entities()` function, load custom overlay JSON
- `services/reporter/anveshak/reporter/worker.py` -- in `generate_report()`, query extracted_entities before falling back to regex extraction
- `services/reporter/anveshak/reporter/db/__init__.py` -- add SQL query for topic location entities
- `infra/configs/geocoder/custom_locations.json` -- new file, defence-relevant location overrides

---

## 4. Surface Sentiment & Keywords in Frontend (Analytics Value)

**Problem:** VADER sentiment and YAKE keywords are computed for every content_item and stored in `content_items.labels` JSONB, but nothing in the API or frontend reads them. They're dead data costing CPU cycles with zero user value.

**Current behavior:**
- `analyse_content()` in `services/analyst/anveshak/analyst/jobs.py` runs VADER + YAKE on every item
- Results stored in labels: `{"sentiment": {"compound": -0.78, ...}, "keywords": ["term1", ...]}`
- No API endpoint exposes them
- Frontend never reads them

**Suggested fix (4 features):**

### 4a. Content Feed: Sentiment Filter + Badge
- Add sentiment badge on each `ContentCard` (green=positive, grey=neutral, red=negative based on compound score)
- Add filter dropdown in `FilterBar`: "All / Positive / Neutral / Negative"
- API: Add `sentiment` query param to `GET /api/v1/topics/{id}/content` that filters by `labels->'sentiment'->>'compound'` range

**Files:** `services/api/anveshak/api/routes/topics.py`, `services/api/anveshak/api/db/content.py`, `frontend/src/components/content/ContentCard.tsx`, `frontend/src/components/content/FilterBar.tsx`

### 4b. Topic Dashboard: Sentiment Trend Chart
- New component `SentimentTrend.tsx` — line chart showing compound sentiment over time (daily average)
- API: New endpoint `GET /api/v1/topics/{id}/sentiment-trend?days=30` that aggregates sentiment by day
- SQL: `SELECT DATE(captured_at), AVG((labels->'sentiment'->>'compound')::float) FROM content_items WHERE topic_id=$1 GROUP BY DATE(captured_at) ORDER BY 1`
- Helps analyst see: "coverage of this topic turned hostile 3 days ago"

**Files:** `services/api/anveshak/api/routes/topics.py`, `frontend/src/components/topics/SentimentTrend.tsx`, `frontend/src/pages/TopicsDashboard.tsx`

### 4c. Topic Dashboard: Trending Keywords Widget
- New component `TrendingKeywords.tsx` — shows top 10-15 keywords extracted from recent content (last 7 days)
- API: New endpoint `GET /api/v1/topics/{id}/trending-keywords?days=7&limit=15`
- SQL: unnest the keywords array from labels JSONB, count frequency, return top N
- Helps analyst see: "Chinese submarine" appeared 47 times this week, up from 12 last week

**Files:** `services/api/anveshak/api/routes/topics.py`, `frontend/src/components/topics/TrendingKeywords.tsx`, `frontend/src/pages/TopicsDashboard.tsx`

### 4d. Sentiment Shift Signal (New Signal Type)
- New signal type: `sentiment_shift` — fires when average sentiment for a topic drops sharply (e.g., compound drops >0.3 within 24h window vs previous 7-day average)
- Analyst gets alert: "Sentiment on 'India-China border' shifted from neutral (0.1) to strongly negative (-0.6) in last 24 hours"
- Implementation: Add check in `signal_engine.py` alongside the existing cluster threshold check

**Files:** `services/analyst/anveshak/analyst/signal_engine.py`, `sdk/anveshak/models/signal.py` (add SENTIMENT_SHIFT to SignalType enum)

---

## 5. Analyst Hybrid Architecture: ARQ Workers + Lightweight Scheduler

**Problem:** The analyst service runs 6 async loops in a single process via `asyncio.gather()`. This has four issues:
1. **NLP blocks everything** — CPU-heavy ML work (spaCy, NLLB, sentence-transformer) blocks the event loop. While processing 50 items (~25 min with translation), clustering and signal checks wait.
2. **No horizontal scaling** — 500 unprocessed items = 83 min on 1 core. Can't add more workers.
3. **No failure isolation** — crashed items are logged and skipped. No retry count, no dead letter queue, no visibility into backlog.
4. **No queue depth observability** — no way to know "how many items are waiting for NLP?" without querying the DB.

**Current behavior:**
- `services/analyst/anveshak/analyst/main.py` runs `asyncio.gather(nlp_loop, cluster_loop, signal_check_loop, credibility_update_loop, backfill_loop, convergence_loop)`
- All 6 loops share one Python process, one DB pool, one event loop
- All ML models (~3GB) loaded in this single process
- The analyst also has ARQ `WorkerSettings` in `jobs.py` but the main process doesn't use them — it calls the job functions directly

**Suggested architecture: split into 2 containers:**

### Container 1: analyst-worker (ARQ, scalable, CPU-heavy)
Handles all per-item independent work. Scales horizontally via Docker replicas.

```yaml
analyst-worker:
  command: python -m arq anveshak.analyst.jobs.WorkerSettings
  mem_limit: 6g
  deploy:
    replicas: ${ANALYST_WORKER_REPLICAS:-1}  # 1 on laptop, 4 on server
```

Jobs (all already defined in `jobs.py`, just need to be the primary path):
- `analyse_content` — NLP pipeline per item (enqueued by scraper/social after insert)
- `generate_cluster_label` — Ollama call per cluster (enqueued by scheduler after clustering)
- `run_cross_verification` — credibility boost per topic (enqueued by scheduler after clustering)
- `backfill_topic` — per-topic backfill (ARQ cron every 10 min)
- `update_source_credibility` — deepfake drop pass (ARQ cron every 24h)
- `run_contradiction_scoring` — contradiction drop pass (ARQ cron daily 02:00)

Scaling: 1 worker = 6GB RAM. 4 workers = 24GB RAM. Same code, same image. Redis BLPOP guarantees each job goes to exactly one worker — no duplicates possible.

### Container 2: analyst-scheduler (loops, single instance, lightweight)
Handles batch work that needs global state. Does NOT load spaCy/NLLB/sentence-transformers.

```yaml
analyst-scheduler:
  command: python -m anveshak.analyst.scheduler
  mem_limit: 512m  # no ML models, just SQL + numpy
```

Loops:
- `cluster_loop` (every 5 min) — HDBSCAN needs ALL embeddings for a topic at once. Can't split across workers. Loads vectors from DB, runs numpy clustering, upserts results.
- `signal_check` (every 5 min) — one SQL query checking `independent_source_count >= threshold`. Takes <100ms. ARQ overhead would exceed the work itself.
- `convergence_check` (every 15 min) — compares cluster centroids across topics. Needs global view.
- `orphan_sweep` (every 5 min, NEW) — `SELECT id FROM content_items WHERE embedding IS NULL`, enqueues missed items to ARQ. Safety net for cases where scraper's enqueue failed after insert.

### Why this split:

| Work Type | Needs all data? | CPU-heavy? | Independent per item? | → Where |
|-----------|----------------|------------|----------------------|---------|
| NLP/embed | No | Yes (10s/item) | Yes | ARQ worker |
| Clustering | Yes (all vectors) | Medium | No (per-topic batch) | Scheduler loop |
| Signal check | Yes (all clusters) | No (<100ms) | No (global scan) | Scheduler loop |
| Convergence | Yes (all centroids) | Low | No (cross-topic) | Scheduler loop |
| Credibility | No | Low | Yes (per-source) | ARQ cron |
| Backfill | No | Medium | Yes (per-topic) | ARQ cron |
| Label gen | No | Low (Ollama) | Yes (per-cluster) | ARQ job |
| Orphan sweep | No | No (just SQL) | N/A | Scheduler loop |

### Migration path (non-breaking):
1. Scraper/social already call `enqueue_job("analyse_content", ...)` after insert — this is already going to ARQ. Just need the worker to be the primary consumer instead of the loop.
2. Remove `nlp_loop` from `main.py` — the ARQ worker handles it.
3. Keep `cluster_loop`, `signal_check_loop`, `convergence_loop` in a new `scheduler.py`.
4. Add `orphan_sweep` loop as safety net.
5. Move credibility/backfill/contradiction to ARQ cron jobs (they already have ARQ function definitions).

**Files involved:**
- `services/analyst/anveshak/analyst/main.py` → strip to scheduler-only (remove nlp_loop, credibility_loop, backfill_loop)
- `services/analyst/anveshak/analyst/scheduler.py` → new file, lightweight loops (cluster, signal, convergence, orphan sweep)
- `services/analyst/anveshak/analyst/jobs.py` → add cron entries for credibility/backfill/contradiction to WorkerSettings
- `infra/compose.yml` → split analyst into analyst-scheduler + analyst-worker with configurable replicas
- `.env.example` → add ANALYST_WORKER_REPLICAS (default: 1)

---
---

# Discussion Required

Suggestions where the right approach isn't obvious. Need to weigh tradeoffs before deciding.

---

## D1. Should the Scraper Filter Content by Keyword Relevance?

**Context:** Currently the scraper fetches EVERYTHING from linked web/RSS sources. If thehindu.com is linked to topic "India-China border" with keywords ["LAC", "Ladakh", "Galwan"], the scraper still ingests cricket articles, Bollywood news, and everything else on the homepage. The analyst pipeline sorts relevance later via embeddings and clustering.

**Current behavior by platform:**
- Scraper (web/RSS): Keywords IGNORED -- fetches full pages and all linked articles
- Telegram: Keywords IGNORED -- fetches all channel messages
- Reddit: Keywords IGNORED -- fetches all subreddit posts
- X/Twitter: Keywords ARE the search query -- only matching tweets returned
- Bluesky: Keywords ARE the search query -- only matching posts returned

**The argument FOR filtering at scrape time:**
- Saves DB storage (irrelevant articles never inserted)
- Saves analyst CPU (no embedding/NER on irrelevant content)
- Reduces noise in clustering (fewer garbage clusters)
- A topic with 5 broad sources could ingest hundreds of irrelevant articles per day

**The argument AGAINST filtering at scrape time:**
- Keyword matching is dumb -- "Modi visits France to discuss Indo-Pacific strategy" doesn't contain "LAC" or "Ladakh" but IS relevant to India-China dynamics
- The whole point of embeddings is that they catch semantic relevance that keywords miss
- You might miss important content that mentions the topic indirectly
- Source credibility scoring needs volume -- if you filter 80% of articles, you don't have enough data to judge if a source is reliable
- Contradiction scoring (credibility pass 3) counts unclustered vs clustered items ratio -- filtering would skew this

**Possible middle ground:**
1. **Post-embedding relevance scoring:** After the analyst computes embeddings, compute cosine similarity between the content embedding and the topic's keyword embedding. If similarity < threshold (e.g., 0.3), mark as `low_relevance` in labels but DON'T delete. This way:
   - Content still exists for credibility scoring
   - Low-relevance items can be hidden from the UI feed
   - RAG retrieval naturally ignores them (too far in vector space)
   - No information loss

2. **UI-level filtering only:** Add a toggle in ContentFeed: "Show all" vs "Show relevant only". Filter client-side by similarity score. Scraper and analyst unchanged.

3. **Source-level approach:** Instead of filtering content, guide users to link more specific sources. Instead of thehindu.com (entire site), link thehindu.com/news/national/defence/ (defence section RSS). The source itself becomes the filter.

**Decision needed:** Is the current "ingest everything, sort later" approach causing real problems (storage, CPU, noise)? Or is this a theoretical concern? If the demo dataset (148 items) doesn't show the problem, it may not matter until scale increases.

**Files that would be involved (if we proceed):**
- `services/analyst/anveshak/analyst/jobs.py` -- add relevance scoring post-embedding
- `sdk/anveshak/models/content.py` -- add relevance_score field or label
- `services/api/anveshak/api/routes/topics.py` -- filter by relevance in content listing
- `frontend/src/pages/ContentFeed.tsx` -- relevance toggle

---

## D2. CLIP Category Guidance + Possible Fine-Tuning for Military Identification

**Context:** CLIP is a zero-shot classifier trained on 400M internet image-text pairs. It works well for BROAD categories ("military vehicle" vs "civilian car") but poorly for SPECIFIC identification ("Sukhoi Su-30" vs "Rafale"). The analyst may not understand these limitations and set overly specific clip_categories expecting accurate results.

**CLIP's reliability spectrum:**
- HIGH confidence (>0.85): "military vehicle" vs "civilian vehicle", "fighter jet" vs "commercial airplane", "satellite image" vs "ground photo" — visually distinct categories
- MEDIUM confidence (0.5-0.7): "Sukhoi" vs "Rafale", "aircraft carrier" vs "destroyer" — similar shapes, some differences
- LOW confidence (<0.4): "Su-30MKI" vs "Su-30SM", "INS Vikrant" vs "INS Vikramaditya" — nearly identical variants, requires expert knowledge CLIP doesn't have

**Why CLIP fails on specific military models:** CLIP learned from internet captions. Most captions say "fighter jet" not "Sukhoi Su-30MKI with thrust-vectoring nozzles." The fine-grained visual features (canard configuration, IRST placement, engine nacelle shape) were never linked to specific text labels in training data.

**Three possible approaches:**

1. **UI guidance only (cheapest, immediate):** When the analyst defines clip_categories in the topic creation form, show a tooltip or helper text:
   - "CLIP works best with broad categories like 'military vehicle' or 'fighter aircraft'"
   - "For specific identification (Su-30 vs Rafale), use your own expertise on the image"
   - Could show a reliability indicator next to each category based on how generic/specific the text is

2. **Fine-tune CLIP on military dataset (medium effort, big improvement):**
   - Take CLIP base model + train on 5,000-10,000 labeled military images
   - Needs: open-source military image datasets (some exist on Kaggle/HuggingFace)
   - Result: CLIP that CAN distinguish Sukhoi from Rafale with high confidence
   - Constraint: fine-tuned model must stay within hardware.md upgrade path, needs to run on CPU
   - Risk: classified military imagery can't be used for training in most contexts

3. **Dedicated military classifier as separate vision module (highest effort, best results):**
   - Train a standalone CNN (e.g., EfficientNet-B0) specifically for military equipment identification
   - Separate from CLIP — runs as an additional step in the vision pipeline
   - Could cover: aircraft types, naval vessel classes, vehicle types, weapon systems
   - Would need significant labeled data per class
   - Adds another model to the vision container (~20-100MB)

**Recommendation:** Start with option 1 (UI guidance). It's zero code on the vision side — just frontend tooltip. If IAF specifically requests fine-grained identification, then explore option 2.

**Files involved (option 1 only):**
- `frontend/src/components/topics/CreateTopicModal.tsx` -- add tooltip/helper text for clip_categories input
- No backend changes needed
