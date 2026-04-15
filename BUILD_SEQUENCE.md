# ANVESHAK — BUILD SEQUENCE

Phase-by-phase implementation plan. Each phase has concrete, verifiable exit criteria.
Run `/phase-check N` to verify exit criteria before moving to the next phase.

**Product:** Sovereign AI-OSINT platform for iDEX ADITI 4.0 PS-18 (IAF)
**Grant:** ₹25 Crore | **Deadline:** 4 May 2026
**Strategy:** Ship Anveshak standalone. Drishti is the upsell.

---

## DATA FLOW — CANONICAL

Understanding this flow is required before building any phase.

```
[Analyst creates Topic]
        │
        ▼
[Scraper + Social collect ContentItems]
        │ content_hash dedup (ON CONFLICT DO NOTHING)
        ▼
[content_items table: raw_text, clean_text, url, source_id, topic_id]
        │
        ▼  ARQ job: analyse_content(content_item_id)
[Analyst service NLP pipeline]
        ├─ langdetect → language code
        ├─ spaCy (en/ru/zh) → NER → extracted_entities table
        ├─ sentence-transformers → embedding vector(384)
        └─ UPDATE content_items SET embedding = $1, language = $2
        │
        ▼  ARQ job: run_clustering(topic_id)
[HDBSCAN clustering]
        ├─ Groups content_items by cosine similarity
        ├─ narrative_clusters table (label, item_count, embedding_centroid)
        ├─ UPDATE narrative_clusters SET independent_source_count =
        │      COUNT(DISTINCT sources.platform) for items in cluster
        └─ ARQ job: generate_cluster_label(cluster_id) → Ollama
        │
        ▼  Signal engine (polling loop in analyst service)
[Signal check: independent_source_count >= topic.signal_threshold?]
        └─ YES → INSERT INTO signals + WebSocket push to analyst sessions
        │
        ▼  Analyst reviews signal, requests report
[Reporter ARQ job: generate_report(report_id)]
        ├─ pgvector: SELECT embedding <-> $query ORDER BY dist LIMIT k
        ├─ Build RAG prompt with top-k content chunks
        ├─ Ollama mistral:7b → structured JSON
        ├─ Pydantic validation
        └─ UPDATE reports SET content_md=$1, generated_at=NOW(),
               source_snapshot=$2 WHERE generated_at IS NULL
```

---

## PHASE 0 — Scaffold ✅

**Goal:** Project skeleton exists. Stack is defined. `make up` works structurally.

### Exit Criteria

- [ ] 0.1 `CLAUDE.md` exists with all 12 architectural rules
- [ ] 0.2 `hardware.md` exists with upgrade path for every ML component
- [ ] 0.3 `pyproject.toml` uv workspace with all 7 members declared
- [ ] 0.4 `Makefile` has `up`, `down`, `init`, `migrate`, `test`, `seed-demo`, `demo-check`
- [ ] 0.5 `.env.example` has all required vars (no hardcoded secrets)
- [ ] 0.6 `.gitignore` excludes `.env`, `*.pem`, `models/`, `data/`
- [ ] 0.7 `infra/compose.yml` defines all 11 services with health checks
- [ ] 0.8 `infra/compose.vision.yml` overlay exists for vision service
- [ ] 0.9 `infra/compose.bridge.yml` overlay exists for Drishti bridge
- [ ] 0.10 `init-pgvector.sql` creates pgvector extension on DB init
- [ ] 0.11 SDK: `Labels`, `Topic`, `Source`, `ContentItem`, `Signal`, `Report`, `AnalysisJob` models exist
- [ ] 0.12 SDK: `labels` field is non-Optional on every model (CLAUDE.md rule 2)
- [ ] 0.13 SDK: `DrishtiBridgeEmitter` exists and is no-op when `ANVESHAK_DRISHTI_BRIDGE=false`
- [ ] 0.14 Migration `001_initial_schema.py` creates all 13 tables with correct FK constraints
- [ ] 0.15 Migration creates `UNIQUE(content_hash)` on `content_items` (dedup rule)
- [ ] 0.16 Migration creates IVFFlat vector index on `content_items.embedding`
- [ ] 0.17 Migration creates `credibility_audit_log` (no updated_at — immutable)
- [ ] 0.18 Migration creates `report_source_warnings` table
- [ ] 0.19 `reports.generated_at` column is nullable (SET ONCE rule)
- [ ] 0.20 All 5 service skeletons have `settings.py` with hardware-controlled env vars
- [ ] 0.21 All ML model names/devices in `settings.py` — NONE hardcoded in service logic
- [ ] 0.22 Frontend: React + Vite + Tailwind + 6 page components scaffold
- [ ] 0.23 `tests/unit/test_models_labels.py` asserts labels non-Optional on all models
- [ ] 0.24 `scripts/verify_labels.py` — importable, scans models
- [ ] 0.25 `scripts/verify_reports_immutable.py` — importable, scans routes
- [ ] 0.26 `scripts/seed_demo.sql` — valid SQL with 3 topics, 5 sources, 1 signal
- [ ] 0.27 `docs/architecture.md` — system diagram + data flow documented
- [ ] 0.28 `docs/x_api_application.md` — X API use case text ready to submit
- [ ] 0.29 `.claude/` governance: commands, agents, rules, skills all present

### How to verify Phase 0

```bash
find /anveshak -name "*.py" | xargs grep -l "cpu\|cuda\|nano\|xlarge\|mistral\|llama" | grep -v settings.py | grep -v hardware.md
# Must return nothing — no hardcoded ML strings outside settings.py

python -c "from anveshak.models.base import Labels, Topic, Source; print('SDK OK')"
python scripts/verify_labels.py
python scripts/verify_reports_immutable.py
uv run --package anveshak-tests pytest tests/unit/ -v
```

---

## PHASE 1 — Content Ingestion Pipeline

**Goal:** Topics collect real content. NLP runs. Embeddings stored. Analyst sees content in UI.

**Services modified:** scraper, analyst, api (new routes)
**New DB rows:** content_items, extracted_entities (embeddings populated)

### Exit Criteria

#### Scraper (M2)

- [ ] 1.1 `ScraperJob` ARQ function exists: `scrape_topic(topic_id: str) -> int`
- [ ] 1.2 Crawl4AI fetches clean text from a given URL (unit-testable, pure function)
- [ ] 1.3 trafilatura used as fallback when Crawl4AI returns empty body
- [ ] 1.4 `content_hash = sha256(normalize(clean_text))` — normalise = lowercase + collapse whitespace
- [ ] 1.5 INSERT uses `ON CONFLICT(content_hash) DO NOTHING` — duplicate URLs do not create duplicate rows
- [ ] 1.6 `ContentItem.credibility_score_at_capture` is populated from `sources.credibility_score` at insert time (not FK join — snapshot)
- [ ] 1.7 Scraper respects `settings.scraper_request_timeout_s` — no hardcoded timeout
- [ ] 1.8 Scraper respects `settings.scraper_concurrency` — uses asyncio semaphore
- [ ] 1.9 Failed URL fetch → logs `url` and error, does NOT crash the loop
- [ ] 1.10 Tor proxy: if `settings.tor_proxy_url` is set, route requests through it

#### Analyst NLP pipeline (M2)

- [ ] 1.11 `analyse_content(content_item_id: str)` ARQ function exists
- [ ] 1.12 `langdetect(clean_text)` → routes to correct spaCy model (en/ru/zh)
- [ ] 1.13 Unknown language → falls back to English model, logs warning
- [ ] 1.14 spaCy NER → entities stored in `extracted_entities` with `entity_type`, `entity_text`, `confidence`
- [ ] 1.15 `sentence_transformers.encode(clean_text)` → `embedding vector(384)`
- [ ] 1.16 `UPDATE content_items SET embedding=$1, language=$2 WHERE id=$3`
- [ ] 1.17 spaCy model loaded ONCE at service startup (not per-request)
- [ ] 1.18 sentence-transformers model loaded ONCE at service startup

#### API — new content routes

- [ ] 1.19 `GET /api/v1/topics/{id}/content` returns paginated content_items (newest first)
- [ ] 1.20 Response includes: `id`, `url`, `clean_text` (truncated 500 chars), `language`, `credibility_score_at_capture`, `captured_at`
- [ ] 1.21 `GET /api/v1/content/{id}` returns full content_item including extracted entities
- [ ] 1.22 `GET /api/v1/topics/{id}/content?has_embedding=false` filters unprocessed items
- [ ] 1.23 `GET /api/v1/search?q=...&topic_id=...` performs pgvector cosine similarity search
- [ ] 1.24 Search returns results with `similarity_score` field (float 0.0–1.0)

#### Data flow assertions

- [ ] 1.25 Create topic → wait 60s → content_items exist for that topic
- [ ] 1.26 content_items with same URL scraped twice → exactly ONE row (dedup)
- [ ] 1.27 content_items.embedding is NOT NULL after analyst processes item
- [ ] 1.28 extracted_entities rows exist for content items with named entities in text
- [ ] 1.29 content_items.language is set correctly (not NULL, not default 'en' for non-English text)

#### Test coverage

- [ ] 1.30 Unit test: `normalise_text()` function (pure, no DB)
- [ ] 1.31 Unit test: `compute_content_hash(text)` returns consistent SHA-256
- [ ] 1.32 Unit test: `parse_entities(spacy_doc)` returns list of `ExtractedEntity`
- [ ] 1.33 Integration test: scrape → DB → analyst → embedding stored (Docker Compose)
- [ ] 1.34 All tests pass on CPU with default model settings

---

## PHASE 2 — Clustering + Signal Engine

**Goal:** Related content groups into clusters. When a cluster hits threshold → analyst gets notified.

**Services modified:** analyst, api (WebSocket + signals route)
**New DB rows:** narrative_clusters, signals

### Exit Criteria

#### Clustering (M2)

- [ ] 2.1 `run_clustering(topic_id: str)` ARQ function exists
- [ ] 2.2 HDBSCAN runs over `content_items.embedding` filtered by `topic_id`
- [ ] 2.3 Minimum 3 items required to form a cluster (configurable: `settings.hdbscan_min_cluster_size`)
- [ ] 2.4 Each cluster → `narrative_clusters` row with `item_count`, `embedding_centroid`
- [ ] 2.5 `independent_source_count = COUNT(DISTINCT sources.platform)` for items in cluster
- [ ] 2.6 Cluster label generated by Ollama `llama3.2:3b` via ARQ job `generate_cluster_label(cluster_id)`
- [ ] 2.7 Ollama output validated through `ClusterLabel(BaseModel)` before storage
- [ ] 2.8 If Ollama fails → cluster label defaults to `"Cluster {N}: {top_entity}"` (never NULL)
- [ ] 2.9 Historical backfill: on new topic creation, pgvector cosine search over existing corpus assigns relevant existing items to new topic
- [ ] 2.10 `GET /api/v1/topics/{id}/clusters` returns clusters sorted by `item_count DESC`

#### Signal engine

- [ ] 2.11 Signal engine runs every `settings.signal_check_interval_s` (default: 300s)
- [ ] 2.12 Fires when `cluster.independent_source_count >= topic.signal_threshold`
- [ ] 2.13 Signal dedup: same `cluster_id` + same `signal_type` does NOT create duplicate signal within 24h
- [ ] 2.14 Signal status flow: `new` → `acknowledged` → `dismissed` (no other states)
- [ ] 2.15 `PATCH /api/v1/signals/{id}/acknowledge` sets status=acknowledged
- [ ] 2.16 `PATCH /api/v1/signals/{id}/dismiss` sets status=dismissed
- [ ] 2.17 WebSocket endpoint: `WS /api/v1/ws/{analyst_session_id}` — authenticated
- [ ] 2.18 New signal → pushed immediately to all connected WebSocket sessions for that topic
- [ ] 2.19 WebSocket message schema: `{"type": "signal", "signal_id": "...", "topic_id": "...", "severity": "HIGH"}`
- [ ] 2.20 WebSocket reconnect: client receives missed signals since last disconnect on reconnect

#### Source credibility auto-feedback (M1)

- [ ] 2.21 Source credibility auto-update loop runs every `settings.credibility_update_interval_s`
- [ ] 2.22 Source that amplified a confirmed deepfake (deepfake_score > 0.8) has score reduced
- [ ] 2.23 Score change ALWAYS writes `credibility_audit_log` row — no silent updates
- [ ] 2.24 Score update and audit log write are in a SINGLE DB transaction
- [ ] 2.25 `GET /api/v1/sources/{id}/audit-log` returns full audit history

#### Data flow assertions

- [ ] 2.26 Ingest 5+ items from 3 different source platforms on same topic → cluster forms
- [ ] 2.27 `narrative_clusters.independent_source_count` accurately reflects platform diversity (not item count)
- [ ] 2.28 Setting `topic.signal_threshold = 2` and ingesting from 2 platforms → signal fires
- [ ] 2.29 WebSocket client receives signal push within 10s of signal firing
- [ ] 2.30 Duplicate scrape run does NOT create duplicate signal for same cluster

#### Test coverage

- [ ] 2.31 Unit test: signal dedup logic (pure function, no DB)
- [ ] 2.32 Unit test: `count_independent_sources(content_item_ids, db)` SQL correctness
- [ ] 2.33 Integration test: items → cluster → signal → WebSocket message received

---

## PHASE 3 — Social Media Adapters (M3)

**Goal:** Telegram, Reddit, Bluesky, X all ingest content into the same pipeline.

**Services modified:** social
**New DB rows:** content_items (from social platforms), sources (platform-tagged)

### Exit Criteria

#### Adapter framework

- [ ] 3.1 `SourceAdapterBase` ABC exists: `async def collect(topic: Topic) -> AsyncIterator[RawItem]`
- [ ] 3.2 All 4 adapters implement `SourceAdapterBase`
- [ ] 3.3 `SourceAdapterConformanceSuite` has ≥5 assertions — all pass for each adapter
- [ ] 3.4 Raw items from all adapters → same `content_items` table (platform field distinguishes them)
- [ ] 3.5 Each adapter has `is_enabled` check — disabled adapter logs warning and skips silently

#### Telegram adapter

- [ ] 3.6 Reads from `settings.telegram_api_id`, `telegram_api_hash`, `telegram_session_string`
- [ ] 3.7 Session string bootstrap documented in `.env.example` + README note
- [ ] 3.8 Monitors channels/groups defined as sources (by `url_or_handle` in sources table)
- [ ] 3.9 New message → ContentItem with `platform=telegram`, `url=t.me/{channel}/{msg_id}`
- [ ] 3.10 Media attachments → download → stored at `media/{topic_id}/{date}/{content_hash}.{ext}`
- [ ] 3.11 Graceful handling of channel access errors (banned, private) — logs, does not crash

#### Reddit adapter

- [ ] 3.12 Reads from `settings.reddit_client_id`, `reddit_client_secret`
- [ ] 3.13 Subreddits from sources table (`url_or_handle = "r/subreddit"`)
- [ ] 3.14 Polls `new` + `hot` feeds; dedup by `content_hash` eliminates re-ingestion
- [ ] 3.15 ContentItem `url` = full Reddit post URL
- [ ] 3.16 Rate limit: PRAW default 60 req/min respected; exponential backoff on 429

#### Bluesky adapter

- [ ] 3.17 Reads from `settings.bluesky_handle`, `settings.bluesky_password`
- [ ] 3.18 Keyword search via `app.bsky.feed.searchPosts` API
- [ ] 3.19 ContentItem `url` = `https://bsky.app/profile/{handle}/post/{rkey}`

#### X / Twitter adapter

- [ ] 3.20 Reads from `settings.x_bearer_token`
- [ ] 3.21 Uses `GET /2/tweets/search/recent` with topic keywords as query
- [ ] 3.22 **SPEND GUARD**: `monthly_read_count >= settings.x_monthly_read_cap` → halt + warn log, never exceed silently
- [ ] 3.23 Monthly read count persisted in DB (`social_adapter_stats` table or Redis key)
- [ ] 3.24 Read count resets on 1st of month
- [ ] 3.25 Polling interval: `settings.x_poll_interval_s` (default: 900 = 15 min)
- [ ] 3.26 `X_ADAPTER_MODE=polling` is default; `stream` mode raises `NotImplementedError` (Enterprise only)

#### Data flow assertions

- [ ] 3.27 Each adapter produces ContentItems with correct `platform` value
- [ ] 3.28 Telegram + Reddit item for same story → content_hash differs (different text), but cluster groups them
- [ ] 3.29 `independent_source_count` counts `telegram` and `reddit` as 2 distinct platforms
- [ ] 3.30 X adapter: after reaching `X_MONTHLY_READ_CAP`, subsequent calls return immediately (no API call made)

---

## PHASE 4 — Vision Analysis Pipeline (M4)

**Goal:** Images and video frames are analysed for deepfakes, objects, EXIF anomalies.

**Services modified:** vision, analyst (triggers vision jobs), api (vision routes)
**New DB rows:** media_assets, vision_results

### Exit Criteria

#### Media ingestion

- [ ] 4.1 Scraper downloads images from scraped pages → saves to `media/{topic_id}/{date}/{content_hash}.ext`
- [ ] 4.2 Social adapters download media attachments → same storage path pattern
- [ ] 4.3 `media_assets` row created for each downloaded file
- [ ] 4.4 `content_hash` of media file stored (SHA-256 of raw bytes) — not URL hash
- [ ] 4.5 EXIF extracted using `exiftool` or `Pillow` → stored in `media_assets.exif_data` JSONB
- [ ] 4.6 pHash computed → stored in `media_assets.phash` (bigint) for near-duplicate detection

#### YOLO object detection

- [ ] 4.7 `run_yolo(media_asset_id: str)` ARQ function exists
- [ ] 4.8 Model loaded from `settings.yolo_model_size` (never hardcoded)
- [ ] 4.9 Returns list of detections: `[{"label": "person", "confidence": 0.98, "bbox": [x1,y1,x2,y2]}]`
- [ ] 4.10 Stored in `vision_results.yolo_detections` JSONB
- [ ] 4.11 Detections for weapons/aircraft/vehicles → tagged in `content_items.labels` JSONB

#### Deepfake detection — face/image

- [ ] 4.12 `DeepfakeDetector` ABC with `.score(image_bytes: bytes) -> float`
- [ ] 4.13 `FacetorchDetector` implements ABC — CPU default (`settings.vision_device=cpu`)
- [ ] 4.14 Score is float 0.0–1.0 — NEVER bool — stored in `vision_results.deepfake_score`
- [ ] 4.15 `vision_results.deepfake_model` records which model produced the score
- [ ] 4.16 `CUDAExecutionProvider` used when `settings.vision_device=cuda` — zero code change from CPU

#### Deepfake detection — non-face/video/landscape

- [ ] 4.17 `EfficientNetDetector` implements same `DeepfakeDetector` ABC
- [ ] 4.18 `VISION_DEEPFAKE_VIDEO_MODEL=efficientnet` → EfficientNetDetector instantiated
- [ ] 4.19 `VISION_DEEPFAKE_VIDEO_MODEL=dire` → `DIREDetector` instantiated (GPU required)
- [ ] 4.20 Video: keyframes extracted every `settings.video_keyframe_interval_s` seconds
- [ ] 4.21 Each keyframe analysed independently; worst-case score propagated to media_asset

#### CLIP semantic classification

- [ ] 4.22 `run_clip(media_asset_id: str, categories: list[str])` ARQ function exists
- [ ] 4.23 Categories come from `topic.clip_categories` (user-defined at topic creation)
- [ ] 4.24 Results stored in `vision_results.clip_labels` JSONB

#### pHash reverse lookup

- [ ] 4.25 `GET /api/v1/vision/reverse-search?phash={hash}&threshold={n}` finds near-duplicates
- [ ] 4.26 Hamming distance threshold from `settings.phash_duplicate_threshold` (default: 8)
- [ ] 4.27 Returns list of matching media_assets with their content_items

#### API — vision routes

- [ ] 4.28 `POST /api/v1/vision/analyse` accepts image upload (multipart) → dispatches ARQ job → returns `job_id`
- [ ] 4.29 `GET /api/v1/vision/jobs/{job_id}` returns job status + results when complete
- [ ] 4.30 `GET /api/v1/content/{id}/vision` returns all vision_results for a content_item's media_assets

#### Data flow assertions

- [ ] 4.31 Scraped article with images → media_assets rows created → vision ARQ job dispatched
- [ ] 4.32 vision_results.deepfake_score is always float (0.0–1.0), never NULL after processing
- [ ] 4.33 Deepfake score > 0.8 on a source → triggers credibility auto-downgrade (Phase 2 integration)
- [ ] 4.34 Same image URL scraped from two sources → media_assets.content_hash dedup → ONE vision_results row

---

## PHASE 5 — LLM Report Generation (M5)

**Goal:** Analyst requests a report → ARQ background job → RAG-grounded brief appears in UI.

**Services modified:** reporter, api (reports routes)
**New DB rows:** reports, report_source_warnings

### Exit Criteria

#### RAG pipeline

- [ ] 5.1 `generate_report(report_id: str)` ARQ function exists
- [ ] 5.2 Query embedding generated from `report.topic.name + report.topic.keywords`
- [ ] 5.3 `SELECT id, clean_text, credibility_score_at_capture FROM content_items WHERE topic_id=$1 AND embedding IS NOT NULL ORDER BY embedding <-> $2 LIMIT $3` — top-k retrieved
- [ ] 5.4 `settings.rag_top_k` controls k (default: 10, never hardcoded)
- [ ] 5.5 Only items where `credibility_score_at_capture >= report.credibility_min_filter` are included
- [ ] 5.6 Context tokens capped at `settings.rag_max_context_tokens` (default: 4000)
- [ ] 5.7 Prompt template clearly instructs: "Only use information from the provided context. Do not hallucinate."
- [ ] 5.8 User input (topic keywords) is sanitised before being embedded in prompt — boundary markers used

#### LLM call (CLAUDE.md rule 9: validate before storage)

- [ ] 5.9 Ollama call uses `settings.ollama_report_model` — never hardcoded
- [ ] 5.10 Response parsed through `ReportContent(BaseModel)` before any storage
- [ ] 5.11 LLM output includes: `executive_summary`, `key_findings` (list), `confidence_level`, `source_citations`
- [ ] 5.12 If Pydantic validation fails → job status = `failed`, error logged, report NOT stored
- [ ] 5.13 No cloud LLM call — Ollama must be at `settings.ollama_host` (localhost or Docker network)

#### Report immutability (CLAUDE.md rule 4)

- [ ] 5.14 Report created with `generated_at = NULL`
- [ ] 5.15 ARQ job sets `generated_at = NOW()` ONCE via `WHERE id=$1 AND generated_at IS NULL`
- [ ] 5.16 If `generated_at IS NOT NULL` when job runs → job exits without overwriting (idempotent)
- [ ] 5.17 `source_snapshot` captures `{source_id: {name, credibility_score}}` at generation time
- [ ] 5.18 If source credibility changes after report generation → `report_source_warnings` row inserted
- [ ] 5.19 `GET /api/v1/reports/{id}` response includes `source_warnings` array

#### Report types

- [ ] 5.20 `intelligence_brief` — 1–3 page summary, executive summary + key findings + recommendations
- [ ] 5.21 `research_summary` — detailed deep-dive, all entities, timeline of events
- [ ] 5.22 `weekly_digest` — aggregated across all active topics for a 7-day window
- [ ] 5.23 Scheduled reports: if `topic.scheduled_report_cron` is set, ARQ cron triggers generation

#### PDF export

- [ ] 5.24 `GET /api/v1/reports/{id}/pdf` returns PDF file
- [ ] 5.25 PDF includes: report title, generation timestamp, confidence level, source citations, content
- [ ] 5.26 PDF generation does NOT block API — generated async, cached at `settings.pdf_output_dir`

#### GIS output

- [ ] 5.27 Locations extracted by spaCy NER → geocoded (static reference lookup, not live API)
- [ ] 5.28 `report.geojson` field populated with GeoJSON FeatureCollection of mentioned locations
- [ ] 5.29 `GET /api/v1/reports/{id}/geojson` returns GeoJSON directly

#### API routes

- [ ] 5.30 `POST /api/v1/reports` accepts `{topic_id, report_type, time_window_start, time_window_end}`
- [ ] 5.31 Returns `{report_id, status: "queued", arq_job_id}` immediately (never blocks)
- [ ] 5.32 `GET /api/v1/reports/{id}` returns full report + `generation_status` (queued/generating/complete/failed)
- [ ] 5.33 `GET /api/v1/topics/{id}/reports` returns all reports for topic

#### Data flow assertions

- [ ] 5.34 `POST /api/v1/reports` → response in <100ms (job dispatched, not executed)
- [ ] 5.35 ARQ job runs → `generated_at` set → `GET /api/v1/reports/{id}` shows `status: complete`
- [ ] 5.36 `reports.source_snapshot` contains credibility scores AT generation time, not current scores
- [ ] 5.37 Second `generate_report(same_report_id)` call → does nothing (idempotent, `generated_at IS NOT NULL` guard)
- [ ] 5.38 Report content references sources in `source_snapshot` (RAG grounded, no hallucinated sources)

---

## PHASE 6 — Frontend Analyst Workbench (Full Wiring)

**Goal:** Everything built in P1–P5 is accessible and usable in the browser.

**Services modified:** frontend
**No new DB tables**

### Exit Criteria

#### Authentication

- [ ] 6.1 Login page → POST `/api/v1/auth/login` → JWT stored in `httpOnly` cookie or localStorage
- [ ] 6.2 401 on any protected route → redirect to login
- [ ] 6.3 JWT expiry (default: 8h) → graceful re-login prompt

#### Topics Dashboard

- [ ] 6.4 Create topic form: name, keywords (tag input), signal_threshold, languages, CLIP categories
- [ ] 6.5 Topic list shows: name, content count, active signal count, last activity
- [ ] 6.6 Topic status (active/paused) toggleable
- [ ] 6.7 Click topic → navigates to topic detail view

#### Content Feed (per topic)

- [ ] 6.8 Infinite-scroll list of content_items, newest first
- [ ] 6.9 Each card shows: source name, platform badge, credibility score, truncated text, timestamp
- [ ] 6.10 Credibility score badge colour: green ≥70, amber 40–69, red <40
- [ ] 6.11 Language badge (EN/RU/ZH/etc)
- [ ] 6.12 Click card → full content item detail with extracted entities highlighted
- [ ] 6.13 Filter bar: platform, language, credibility min, date range, has_media
- [ ] 6.14 Cluster view toggle: groups items by narrative_cluster

#### Signals Inbox

- [ ] 6.15 New signals show as unread (highlighted)
- [ ] 6.16 Signal card shows: topic, cluster label, independent_source_count, severity, timestamp
- [ ] 6.17 Acknowledge / Dismiss buttons visible, update status immediately (optimistic UI)
- [ ] 6.18 WebSocket: new signal pushes appear in real-time without page refresh
- [ ] 6.19 Signal click → navigates to relevant cluster/content

#### Image Analysis

- [ ] 6.20 Drag-and-drop image upload → dispatches vision job → shows progress
- [ ] 6.21 Results panel: deepfake probability gauge (0–100%), YOLO bounding box overlay, EXIF table
- [ ] 6.22 Deepfake score colour: green <0.3, amber 0.3–0.7, red >0.7
- [ ] 6.23 Reverse image search: upload image → find near-duplicates in corpus (pHash)
- [ ] 6.24 EXIF anomaly flags highlighted (GPS stripped, AI software tags)

#### Report Builder

- [ ] 6.25 Select topic, report type, time window, credibility filter
- [ ] 6.26 "Generate" button → creates report → shows spinner ("Generating…")
- [ ] 6.27 Polls `GET /api/v1/reports/{id}` every 5s until `status=complete`
- [ ] 6.28 Report view: markdown rendered, source citations linked, confidence badge
- [ ] 6.29 Source warnings banner if any `report_source_warnings` exist
- [ ] 6.30 "Download PDF" button
- [ ] 6.31 GIS tab: MapLibre map showing mentioned locations as markers
- [ ] 6.32 Report history: list of all generated reports for topic

#### Source Manager

- [ ] 6.33 Source list: name, platform, credibility score, last checked, active toggle
- [ ] 6.34 Add source form: name, URL/handle, platform selector
- [ ] 6.35 Credibility score bar chart (visual)
- [ ] 6.36 Audit log tab: full `credibility_audit_log` for source, newest first
- [ ] 6.37 Report warnings count badge on sources that appear in `report_source_warnings`

### NFR

- [ ] 6.38 All UI components must be responsive and work on mobile devices
- [ ] 6.39 All UI components must be accessible and follow WCAG 2.1 AA standards
- [ ] 6.40 All UI components must be performant and have a fast initial load time thinsk deeply baput FCP, TCP
- [ ] 6.41 All UI components must be secure and have a strong security posture
- [ ] 6.42 All UI components must be maintainable and have a clear codebase
- [ ] 6.43 All UI components must be scalable and have a clear architecture wherever mixins etc can be used
- [ ] 6.44 All UI components must be testable and have a strong test coverage
- [ ] 6.45 All UI components must be styled as per standard of 2026 it shuld ffel like a production grade system you can follow drishti ui guidelines
- [ ] 6.46 Make sure to have both dark and light theme feature default to dark mode and have a toggle button to switch between them use modern methods to build such functionality like css variables

---

## PHASE 7 — Source Credibility Hardening (M1 Complete)

**Goal:** M1 fully implemented — auto-scoring, cross-verification, feedback loop closed.

**Services modified:** analyst
**New DB rows:** credibility_audit_log (on every change)

### Exit Criteria

- [ ] 7.1 Cross-verification score: content item confirmed by ≥2 high-credibility sources → boosts both sources
- [ ] 7.2 Contradiction score: content item contradicted by ≥2 high-credibility sources → reduces source score
- [ ] 7.3 Deepfake amplification penalty: source shared item with deepfake_score > 0.8 → score reduced by configurable amount
- [ ] 7.4 Minimum auto-change threshold: `settings.credibility_min_auto_drop` (default: 10.0) — small fluctuations don't generate audit log noise
- [ ] 7.5 `credibility_score` bounded to 0.0–100.0 at all times
- [ ] 7.6 `report_source_warnings` written whenever a report's source score drops below its `source_snapshot` value
- [ ] 7.7 New source starts at 50.0 — never assumes high credibility on creation
- [ ] 7.8 Manual override by analyst persists in audit log with `changed_by = analyst_username`
- [ ] 7.9 `GET /api/v1/sources?credibility_below=40` returns sources below threshold
- [ ] 7.10 `GET /api/v1/topics/{id}/sources` returns sources that have contributed to this topic

---

## PHASE 8 — Production Hardening

**Goal:** Platform is demo-ready and defensible to a security auditor.

**Services modified:** all
**No new DB tables**

### Exit Criteria

#### Security

- [ ] 8.1 All API endpoints require JWT (no unauthenticated access except `/health` and `/metrics`)
- [ ] 8.2 Rate limiting on auth endpoints: max 10 login attempts per IP per 10 minutes
- [ ] 8.3 LLM prompt injection mitigation: user input wrapped in `<user_input>...</user_input>` boundary markers
- [ ] 8.4 No raw scraped content in any log line — only `content_hash` and `url`
- [ ] 8.5 `bandit -r services/ sdk/` passes with no HIGH severity findings
- [ ] 8.6 All secrets loaded from environment — `grep -r "password\|secret\|token" --include="*.py" | grep -v "settings\|env\|os.getenv"` returns nothing

#### Observability

- [ ] 8.7 Prometheus metrics on all services: `requests_total`, `request_duration_seconds`, `arq_jobs_total`, `arq_job_duration_seconds`
- [ ] 8.8 `analyst` service emits: `nlp_items_processed_total`, `embeddings_generated_total`, `clusters_updated_total`, `signals_fired_total`
- [ ] 8.9 `vision` service emits: `images_analysed_total`, `deepfake_detections_total` (score > 0.5)
- [ ] 8.10 structlog structured JSON logging on all services
- [ ] 8.11 Grafana dashboard exists with: service health, ARQ queue depth, signal rate, deepfake detection rate

#### Performance (CPU hardware)

- [ ] 8.12 `POST /api/v1/topics` → 200 in <100ms
- [ ] 8.13 `GET /api/v1/topics/{id}/content` (100 items) → 200 in <500ms
- [ ] 8.14 pgvector cosine similarity search (1000 rows) → <1s
- [ ] 8.15 Report generation completes within 5 minutes on CPU (mistral:7b)
- [ ] 8.16 Vision analysis completes within 15s per image on CPU

#### Reliability

- [ ] 8.17 Service restarts cleanly after DB connection loss (asyncpg reconnect)
- [ ] 8.18 ARQ job retries on transient failure (max 3 retries, exponential backoff)
- [ ] 8.19 Ollama unavailable → ARQ jobs queued and retried, API returns 503 with `retry_after`
- [ ] 8.20 Scraper handles 5xx, timeout, connection refused — logs, does not crash

#### Hardware independence final check

- [ ] 8.21 `grep -r "\"cpu\"\|\"cuda\"\|\"nano\"\|\"xlarge\"\|\"mistral\"\|\"llama\"\|\"en_core_web\"" services/ sdk/` — matches ONLY in `settings.py` files
- [ ] 8.22 `uv run python scripts/verify_labels.py` → PASSED
- [ ] 8.23 `uv run python scripts/verify_reports_immutable.py` → PASSED
- [ ] 8.24 All tests pass with CPU default settings: `make test`

---

## DEMO READINESS CHECKLIST

Run `make demo-check` before every demo. All must pass.

- [ ] All 6 services healthy (HTTP 200 on /health)
- [ ] Ollama has both models loaded (`mistral:7b`, `llama3.2:3b`)
- [ ] Demo user can log in: `demo@anveshak.local`
- [ ] 3 demo topics exist with content
- [ ] ≥1 unacknowledged signal in Signals Inbox
- [ ] ≥1 completed report viewable
- [ ] ≥1 vision analysis result with deepfake score
- [ ] WebSocket push works (browser receives live signal)
- [ ] PDF download works
- [ ] Map loads on report GIS tab

---

## PHASE SUMMARY

| Phase | Capability | PS-18 Module |
|-------|-----------|-------------|
| 0 | Scaffold — all files, docker, migrations | — |
| 1 | Content ingestion: scraper + NLP + embeddings | M2 |
| 2 | Clustering + signal engine + WebSocket | M1 partial + M2 |
| 3 | Social adapters: Telegram, Reddit, Bluesky, X | M3 |
| 4 | Vision: YOLO, deepfake, EXIF, pHash, CLIP | M4 |
| 5 | LLM reports: RAG, PDF, GIS | M5 |
| 6 | Frontend fully wired | UI |
| 7 | Source credibility hardening | M1 complete |
| 8 | Production hardening, security, observability | Cross-cutting |

**Current state: Phase 0 complete. Begin Phase 1.**
