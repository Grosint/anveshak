# Anveshak Codebase — Complete Deep-Dive Reference

Everything about how Anveshak works, how it's connected, why each choice was made,
where data lives, and how to debug problems. Written during the April 2026 onboarding.

---

# TOPIC 1: FOUNDATION LAYER

## What Anveshak Is

Anveshak is a standalone AI-powered OSINT (Open Source Intelligence) analysis and
monitoring platform. Originally developed under iDEX ADITI 4.0 PS-18, funded by
the Indian Air Force through the Defence Innovation Organisation.

**Nothing in the code restricts it to IAF.** The platform is completely generic OSINT.
Any defence agency, law enforcement, think tank, or corporate security team can use it.
The IAF reference is about the funding source and deployment constraint (single-machine,
sovereign, no cloud), not the user base.

**Product strategy:** Anveshak sells standalone. Drishti (a separate entity resolution
platform) is the upsell. Anveshak NEVER depends on Drishti.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ SCRAPER  │  │  SOCIAL  │  │  VISION  │  │ REPORTER │       │
│  │ M2: Web  │  │ M3: Tele │  │ M4: YOLO │  │ M5: LLM  │       │
│  │ + RSS    │  │ Reddit   │  │ CLIP     │  │ RAG+PDF  │       │
│  │          │  │ Bluesky  │  │ Deepfake │  │ GeoJSON  │       │
│  │          │  │ X/Twitter│  │ EXIF     │  │          │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       └──────────────┴──────┬───────┴──────────────┘             │
│              ┌──────────────▼──────────────┐                     │
│              │ ANALYST-SCHEDULER (512 MB)  │                     │
│              │ Clustering + Signals +      │                     │
│              │ Convergence + Orphan Sweep  │                     │
│              └──────────────┬──────────────┘                     │
│                      enqueues to ARQ                             │
│              ┌──────────────▼──────────────┐                     │
│              │ ANALYST-WORKER (6 GB, ×N)   │                     │
│              │ NLP + Embedding + Labels +  │                     │
│              │ Credibility + Backfill      │                     │
│              └──────────────┬──────────────┘                     │
│       ┌─────────────────────┼─────────────────────┐             │
│  ┌────▼─────┐      ┌───────▼───────┐     ┌───────▼──────┐     │
│  │PostgreSQL│      │    Redis      │     │   Ollama     │     │
│  │+pgvector │      │  (ARQ queues) │     │  (Local LLM) │     │
│  └──────────┘      └───────────────┘     └──────────────┘     │
│  ┌──────────────────┐         ┌──────────────────────────┐     │
│  │   FastAPI (API)  │◄────────│  React Frontend          │     │
│  │   + WebSocket    │         │  (Analyst Workbench)     │     │
│  └──────────────────┘         └──────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

5 modules map to PS-18 requirements: M1 (credibility), M2 (web crawling + NLP),
M3 (social adapters), M4 (image/video analysis), M5 (LLM reports).

## The 12 Rules and Why They Exist

| # | Rule | Why |
|---|------|-----|
| 1 | Standalone-first | Must run on one machine. No Drishti dependency. |
| 2 | Labels mandatory (never Optional) | Classification (OPEN/RESTRICTED/SECRET) for security clearance. |
| 3 | Content dedup (SHA-256 content_hash) | Multiple sources report same event. Without dedup, clusters inflate. |
| 4 | Reports immutable (generated_at set ONCE) | Reports are evidence. Editing breaks the evidence chain. |
| 5 | LLM calls async via ARQ (NEVER in routes) | Ollama takes 2-5 min on CPU. Sync call blocks HTTP thread. |
| 6 | Hardware independence (ML params from env vars) | Same code runs on laptop (CPU) and GPU server (RTX 4090). |
| 7 | Deepfake = float 0.0-1.0 (NEVER bool) | Analyst decides the threshold, not the code. |
| 8 | Credibility changes audit-logged | Analyst needs to know what changed and when. |
| 9 | Validate LLM output via Pydantic | LLMs hallucinate. Bad output = failed job, not corrupted data. |
| 10 | No cloud LLM (Ollama localhost only) | Intelligence data never leaves deployment boundary. |
| 11 | X/Twitter spend guard (atomic Redis INCR) | Without atomic counter, two workers could overspend budget. |
| 12 | Drishti bridge one-way (Anveshak → Drishti) | Reading from Drishti would create circular dependency. |

**Common rule violations to watch for:**
- Rule 2: `labels: Optional[Labels] = None` — Labels must NEVER be Optional
- Rule 5: Calling Ollama directly in a FastAPI route — always enqueue ARQ job
- Rule 7: `deepfake_detected: bool` — must be `deepfake_score: float`

## Technology Choices

| Choice | Why NOT the alternative |
|--------|------------------------|
| PostgreSQL (not MongoDB) | Relational data, pgvector for embeddings, ACID for audit, SQL JOINs |
| Raw SQL (not SQLAlchemy ORM) | Greppable, testable. Military auditors read SQL. pgvector has limited ORM support. |
| ARQ (not Celery) | Pure async Python, lightweight, Redis-native. No RabbitMQ dependency. |
| Ollama (not OpenAI) | Sovereign requirement — data never leaves the machine. |
| Crawl4AI (not Scrapy) | Async-native, headless Chromium, stealth mode for anti-bot bypass. |
| structlog (not stdlib) | JSON output for Loki/Grafana. Machine-parseable key-value pairs. |
| Pydantic v2 strict (not dataclasses) | Runtime type validation. Strict mode prevents silent coercion. |

---

# TOPIC 2: DATA MODEL & DATABASE

## Every Table in the Schema

15 tables across 7 Alembic migrations. Flat PostgreSQL — no graph DB.
Extensions: `vector` (pgvector) and `pg_trgm` (trigram text search).

### Core Entities

**users** — Authentication. id, username (UNIQUE), password_hash (bcrypt), role.

**topics** — What you're monitoring. name, keywords[], languages[], credibility_min (default 30.0),
signal_threshold (default 3, counts distinct PLATFORMS not sources), status (active/paused/archived),
clip_categories[] (for CLIP zero-shot image classification), scheduled_report_cron, scheduled_report_type.

**sources** — Where content comes from. name, url_or_handle, platform (web/rss/telegram/reddit/bluesky/twitter),
credibility_score (0-100, starts at 50), health_status (unverified/healthy/degraded/down),
consecutive_failures (circuit breaker: 3+ = down), auto_score_enabled, is_active.

### The Critical Join Table

**topic_sources** — Links topics to sources. PK: (topic_id, source_id). Created by migration 007.
The scraper ONLY scrapes sources linked via this table. If a source exists but isn't linked
to any topic, it will NEVER be scraped. When creating a source via the API, passing optional
`topic_id` auto-links it; creating from the Sources page without topic context creates an
orphaned source with no warning (see suggestion #1 in learning_suggestions.md).

### Ingested Content

**content_items** — Every scraped/collected piece of text. The central table.
- content_hash (UNIQUE) — SHA-256 of normalised text, the dedup key
- embedding vector(384) — NULL initially, filled by sentence-transformer
- translated_text — NULL initially, filled by NLLB-200 if non-English
- translation_model — audit trail for which model translated
- narrative_cluster_id — NULL initially, filled by HDBSCAN clustering
- credibility_score_at_capture — snapshot from source at insert time (not a live FK)
- topic_id is NULLABLE (backfilled content may not have a topic)

A freshly inserted content_item has these NULLs: embedding, translated_text,
translation_model, narrative_cluster_id. The analyst pipeline fills them over time.

**extracted_entities** — NER results in a SEPARATE table (not JSON inside content_items).
One article can have 5, 10, or 50 entities. A separate table enables efficient SQL:
"which people are mentioned most?", "find all articles mentioning Xi Jinping",
entity co-occurrence graphs. A JSON column would be unindexable.

**media_assets** — Downloaded images/videos. content_hash (UNIQUE, media dedup),
storage_path, exif_data (JSONB), phash (BIGINT for perceptual hash).
When the same image appears on multiple websites: the HTTP download happens every time
(no pre-check), the file overwrites itself (same hash = same filename, harmless),
but the DB row is inserted only once (ON CONFLICT DO NOTHING). Vision analysis runs
effectively once (UNIQUE on media_asset_id).

**vision_results** — ML inference on media. UNIQUE on media_asset_id (one result per asset).
yolo_detections (JSONB), clip_labels (JSONB), deepfake_score (float 0-1, NEVER bool),
deepfake_model, synthetic_probability.

**topic_content_items** — Backfill join table for associating old content with new topics.

### Analysis Results

**narrative_clusters** — Groups of semantically similar content. id is UUID v5
(deterministic from topic_id:hdbscan_label, making UPSERT idempotent).
independent_source_count counts distinct PLATFORMS (not sources): BBC(web) + Reuters(web) +
Reddit + Telegram = ISC of 3, not 4. BBC and Reuters are both "web" so count as 1.
embedding_centroid (L2-normalized mean of all vectors), archived_at (temporal windowing),
label_item_hash (staleness detection for re-labeling).

**near_duplicates** — Pairs of nearly-identical content items. CHECK constraint: a_id < b_id
(prevents storing both (A,B) and (B,A)). Excluded from ISC calculation to prevent
paraphrased content from inflating signal counts.

**signals** — Intelligence alerts. signal_type (threshold_crossed/credibility_drop/new_cluster/
cross_topic_convergence), status (new/acknowledged/dismissed), delivered_at (NULL until
pushed via WebSocket by the API's signal_delivery_loop).

### Reports (Immutable)

**reports** — generated_at SET ONCE, NEVER UPDATED. source_snapshot (JSONB) freezes
credibility scores at generation time. content_md (markdown), geojson (GeoJSON
FeatureCollection of mentioned locations), pdf_path.

**report_source_warnings** — Retroactive warnings when cited sources are later downgraded.
The report itself is NEVER modified. UNIQUE on (report_id, source_id).

### Audit & Jobs

**credibility_audit_log** — Immutable, append-only (NO updated_at column).
changed_by: "user:{id}" or "analyst.auto_credibility".

**analysis_jobs** — ARQ job state tracking. job_type, status, arq_job_id, payload, result, error.

### Universal Columns

Every table (except near_duplicates and topic_content_items) has:
id TEXT PK (UUID), created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ, labels JSONB NOT NULL.

## The Three Critical Database Patterns

### Pattern 1: Content Deduplication (Rule 3)

Normalise text (lowercase + collapse whitespace) → SHA-256 → INSERT ON CONFLICT(content_hash) DO NOTHING.
First insert returns id; duplicate returns NULL. Same pattern for media_assets.
This is on content_hash (text dedup). Do NOT confuse with generated_at (report immutability).

### Pattern 2: Report Immutability (Rule 4)

Report created with generated_at = NULL. LLM generates content, then:
`UPDATE reports SET generated_at = NOW() WHERE id = $1 AND generated_at IS NULL`.
If already generated → 0 rows updated → no-op (safe for ARQ retry).
source_snapshot JSONB freezes credibility scores at generation time and never changes.
If a source is later downgraded → report_source_warnings row inserted, report untouched.

### Pattern 3: pgvector Similarity Search

Text → sentence-transformer → 384 floats → stored as vector(384).
Two operators: `<=>` (cosine distance, 0=identical, 2=opposite) for RAG search and semantic search;
`<->` (L2/Euclidean, 0=identical) for HDBSCAN clustering.
HNSW index (migration 003): self-tuning, no training phase, m=16, ef_construction=64.

**Why cosine similarity (not sine, tangent, Euclidean)?**
Cosine measures the ANGLE between vectors — meaning is in the direction, not magnitude.
Sine is backwards (identical=0, unrelated=1). Tangent is undefined at 90° and unbounded.
Euclidean is affected by text length. Cosine: bounded [-1,1], stable, and after L2
normalization equals a simple dot product (extremely fast).

## How Sentence Embeddings Work (all-MiniLM-L6-v2)

80MB, 6-layer transformer. NOT an LLM — cannot generate text, only encodes meaning.

1. TOKENIZE: text → subword tokens → token IDs ("Andaman" → "and" + "##aman")
2. TOKEN EMBEDDINGS: each token ID → 384-dim vector from lookup table
3. TRANSFORMER x6: 6 layers process all tokens together, each "looking at" every other
4. MEAN POOLING: average all token vectors → 1 sentence vector (384 floats)
5. L2 NORMALIZE: divide by length so total = 1.0 (cosine = dot product)
6. STORE: format as `"[0.028,-0.053,...]"` string → pgvector column

Training: 1 billion sentence pairs taught it that similar meanings → nearby vectors.

## Every Timer in the System

Every 5s: API signal_delivery_loop (WebSocket push).
Every 5min: analyst-scheduler cluster_loop + signal_check_loop + orphan_sweep.
Every 6h: analyst-worker backfill_all_topics (ARQ cron).
Every 15min: analyst-scheduler convergence_loop; scraper + social enqueue active topics; reporter check_scheduled_reports.
Every 6h: reporter check_source_warnings.
Daily 02:00 UTC: scraper check_all_source_health; analyst-worker contradiction_scoring (ARQ cron).
Daily 03:00 UTC: analyst-worker update_source_credibility (ARQ cron).
NLP jobs: analyst-worker processes analyse_content on-demand via ARQ (enqueued by scraper/social after insert; orphan_sweep catches misses).
All intervals configurable via env vars.

## How Keywords Are Used Per Platform

Scraper (web/RSS): keywords IGNORED — fetches everything from source URL.
Telegram: IGNORED — fetches all channel messages.
Reddit: IGNORED — fetches all subreddit posts.
X/Twitter: keywords ARE the search query (`"kw1" OR "kw2" -is:retweet lang:en`).
Bluesky: keywords ARE the search query (search_posts per keyword).
If NO keywords: scraper/Telegram/Reddit work fine; X/Twitter and Bluesky do NOTHING.
RAG (reports): topic name + keywords encoded as vector for similarity search.

Design philosophy: scraper/Telegram/Reddit collect broadly from specific sources.
X/Bluesky search narrowly across entire platforms using keywords. The analyst pipeline
sorts relevance after the fact using embeddings, not keywords.

---

# TOPIC 3: SDK & SHARED CODE

## Structure

```
sdk/anveshak/
├── models/           ← Pydantic models (data contract)
│   ├── base.py       ← Labels + AuditedModel
│   ├── topic.py, source.py, content.py, signal.py, report.py, job.py
├── jobs/__init__.py   ← ARQ job name constants + enqueue helper
├── media/downloader.py← Shared media downloader
├── drishti_bridge/    ← One-way entity emitter to Drishti
├── logging.py         ← structlog config (JSON prod, colored dev)
└── tracing.py         ← OpenTelemetry (opt-in, OTEL_ENABLED=true)
```

## Models: The Inheritance Chain

Labels(BaseModel): classification, domain, owner_org, source_id, topic_id. NEVER Optional.
AuditedModel(BaseModel): id (UUID), created_at, updated_at, labels: Labels. Every model inherits this.
`strict=True` on everything — no implicit type coercion (string "3" won't become int 3).

**Models ≠ database schema.** Some DB columns (embedding, health_status) aren't in models.
Some model fields (extracted_entities list) are separate tables. Models represent the API contract.

## ARQ Job Constants

7 constants in `jobs/__init__.py`: JOB_SCRAPE_TOPIC, JOB_BACKFILL_TOPIC, JOB_POLL_SOCIAL_TOPIC,
JOB_ANALYSE_CONTENT, JOB_GENERATE_CLUSTER_LABEL, JOB_RUN_VISION_ANALYSIS, JOB_GENERATE_REPORT.
Always import these instead of raw strings — prevents typos that cause silent job failures.

## Logging

`configure_logging("scraper")` called once at startup. ENVIRONMENT=production → JSON lines
(for Loki/Promtail/Grafana). ENVIRONMENT=development → colored console.
Chatty loggers silenced: httpx, httpcore, asyncio, arq, uvicorn.access, PIL.

## Drishti Bridge

Disabled by default (ANVESHAK_DRISHTI_BRIDGE=false). When enabled, emits extracted entities
to Redpanda topic "source.envelopes.v1". One-way only (Rule 12). Fire-and-forget — failure
never blocks content processing. aiokafka imported lazily only if enabled.

---

# TOPIC 4: API GATEWAY

The API service is the single entry point for the frontend. It NEVER runs NLP, scraping,
or LLM inference — it dispatches work via ARQ and reads results from PostgreSQL.

## Startup (Lifespan)

1. Create asyncpg pool (max 10 DB connections)
2. Create ARQ Redis pool (for dispatching jobs — single connection, not a pool like asyncpg)
3. Pre-warm Ollama (tiny 1-token prompt to prevent cold start)
4. Start signal_delivery_loop as background task

**Connection pooling explained:** Opening a PostgreSQL connection takes ~50ms (TCP + auth + memory).
With a pool of 10 pre-opened connections, requests borrow a connection (~0ms), run query (~5ms),
return it. The pool can handle ~2000 req/s. The ARQ Redis "pool" is misleadingly named — it's
just a single Redis client. Redis commands take <1ms, so multiple connections aren't needed.

## Middleware Stack (LIFO)

SecurityHeadersMiddleware (outermost) → RateLimitMiddleware → CORSMiddleware (innermost).
Rate limits: login 10/min per IP, vision 30/min per JWT, authenticated 120/min, anonymous 60/min.
Rate limiting is in-memory (dict of deques) — works for single-instance sovereign deployment.

## Authentication

POST /api/v1/auth/login → bcrypt verify → JWT (HS256, 8h TTL).
Every REST request: Authorization: Bearer header. WebSocket: ?token= query param
(browsers can't set custom headers on WS). Password hashing uses direct bcrypt wrapper,
not passlib (passlib 1.7 + bcrypt>=4 incompatibility).

## 42+ Endpoints

Topics (CRUD, content feed, entities, clusters, source linking), Sources (CRUD, health check,
credibility update with audit, delete), Signals (WebSocket + REST list/ack/dismiss),
Content (detail, semantic search via pgvector), Vision (upload, poll job, pHash reverse search),
Reports (create/enqueue, get with warnings, GeoJSON, topic report list),
Export (CSV/JSON for content/signals/entities), Intelligence (entity graph, topic similarity,
source discovery, cluster duplicates, merge), System (pipeline health, vector health),
Health (/health, /health/ready deep probe), Metrics (/metrics Prometheus).

## Signal Delivery Bridge

The analyst writes signals to DB → API's signal_delivery_loop polls every 5s
(SELECT WHERE delivered_at IS NULL) → pushes to WebSocket _sessions dict → marks delivered.
_sessions is in-memory (only in API process). If API restarts, connections lost — frontend
reconnects with ?since= parameter to replay missed signals from DB.

## How API Dispatches Work

POST /api/v1/reports → create empty row → enqueue "generate_report" → return {report_id} in <100ms.
POST /api/v1/vision/analyse → forward file → create media_asset → enqueue "run_vision_analysis".
POST /api/v1/topics → insert topic → enqueue "backfill_topic_job".

---

# TOPIC 5: INGESTION PIPELINE (SCRAPER + SOCIAL)

## Two Paths, Same Destination

Both scraper (web/RSS) and social (4 adapters) insert into the same content_items table
with the same SHA-256 dedup. The analyst doesn't know or care where content came from.

## Scraper: Two Containers

**scraper** (main.py) — scheduler. Every 15 min: queries active topics, enqueues
scrape_topic + poll_rss_sources to arq:scraper queue.
**scraper-worker** — ARQ worker. Picks up jobs and does actual scraping.

### Scraping a Web Source

1. Fetch linked sources via topic_sources JOIN (health_status != 'down' = circuit breaker)
2. Create ONE shared Chromium browser per job (not per URL)
3. For each source (parallel via Semaphore(5)):
   - Crawl4AI (headless Chrome, stealth mode) → fallback to trafilatura (HTTP + extract)
   - Per-URL timeout: 30s (one slow URL doesn't block others)
   - compute_content_hash → INSERT ON CONFLICT DO NOTHING
   - If new + media enabled: extract <img>/<video> URLs, download, INSERT media_assets, enqueue vision
   - If follow_links enabled: extract <a> tags (same-domain, max 5), fetch + insert each

### RSS Feeds

poll_rss_sources: fetch XML → feedparser → cap 20 entries per feed.
If summary < 200 chars → fetch full article via Crawl4AI/trafilatura. Never discard an entry.

### Social Service

Also uses ARQ correctly: main.py enqueues poll_social_topic → WorkerSettings picks up.
All 4 adapters (Telegram/Reddit/Bluesky/X) yield RawItem objects → ingest_raw_item()
normalises, dedupes, inserts into content_items, enqueues analyse_content to arq:analyst,
downloads media attachments.

**Enqueue flow:** Both scraper and social enqueue analyse_content to arq:analyst after insert.
The analyst-scheduler's orphan_sweep (every 5 min) catches any items where the enqueue failed.

### Source Health Circuit Breaker

Daily at 02:00: check_all_source_health pings every source. 0 failures → healthy,
1-2 → degraded, 3+ → down (excluded from scraping via SQL WHERE clause).
Can recover when health check succeeds again.

---

# TOPIC 6: ANALYSIS PIPELINE

## Scheduler/Worker Split (Current Architecture)

The analyst is split into two containers from the same Docker image:

**analyst-scheduler** (512 MB, single instance, port 8007):
Runs 4 async loops via asyncio.gather() — no ML models loaded:
- cluster_loop (5min) — HDBSCAN clustering, then enqueues label gen + cross-verification to ARQ
- signal_check_loop (5min) — threshold checks + sentiment shift detection
- convergence_loop (15min) — cross-topic centroid comparison
- orphan_sweep (5min) — re-enqueues content_items missed by scraper's enqueue

**analyst-worker** (6 GB, scalable via ANALYST_WORKER_REPLICAS):
ARQ worker processing all ML-heavy jobs on-demand:
- analyse_content — NLP pipeline (enqueued by scraper/social after insert)
- generate_cluster_label — Ollama call (enqueued by scheduler after clustering)
- run_cross_verification — credibility boost (enqueued by scheduler after clustering)
- backfill_all_topics — cron every 6h
- update_source_credibility — cron daily 03:00
- run_contradiction_scoring — cron daily 02:00

**Why the split:** NLP (~10s/item with translation) blocked clustering and signal checks.
Now the scheduler runs unblocked while N workers process NLP in parallel.

## NLP Pipeline (analyse_content)

1. langdetect → language code (min 30 chars, shorter defaults to "en")
2. NLLB-200 translation (only zh/hi/ar/ur/ru → English; "No Language Left Behind", Meta, 2.4GB)
3. spaCy NER → extracted entities (PERSON/ORG/GPE/LOC/FACILITY/DATE)
4. VADER sentiment → compound/positive/negative/neutral scores (rule-based dictionary, <1MB)
5. YAKE keywords → top 10 distinctive terms (statistical, <1MB)
6. sentence-transformer → 384-float embedding
7. UPDATE content_items (embedding, language, translated_text, labels with sentiment+keywords)
8. INSERT extracted_entities (one row per entity, in a transaction with step 7)

**Why translate before embedding?** All vectors must be in the same "English meaning space"
for cosine similarity to work. Chinese embedded directly would be in "Chinese space" —
mixing them breaks clustering and RAG.

**VADER and YAKE** are computed but currently NOT displayed in the frontend or exposed
by any API endpoint. They are stored in content_items.labels JSONB as dead data.
See suggestion #4 for plans to surface them (sentiment badges, trend charts, keyword widgets).

## HDBSCAN Clustering

Every 5 min: load ALL embeddings for each active topic → run HDBSCAN → find groups.
Unlike K-Means, HDBSCAN doesn't need number of clusters upfront. It discovers structure
based on density. min_cluster_size=3, min_samples=2. Noise items (label=-1) excluded.

For each cluster: compute centroid (mean of vectors, L2-normalized), count ISC
(distinct platforms MINUS near-duplicate items), generate deterministic UUID v5
(same input → same UUID → UPSERT idempotent), link content_items via narrative_cluster_id.

Post-clustering: enqueue label generation (Ollama) for stale clusters,
enqueue cross-verification boost.

**Clustering and RAG are completely independent.** Clustering groups ALL items to find
narratives → fire signals. RAG searches for specific content nearest to a query vector →
build report context. RAG doesn't care about clusters; a noise item could be included if
it's relevant to the query.

## Signal Engine

Every 5 min: SQL query finds clusters WHERE independent_source_count >= topic.signal_threshold
AND topic.status = 'active' AND archived_at IS NULL. For each breaching cluster:
dedup check (same cluster+type within 24h → skip), INSERT signal, broadcast (no-op in analyst,
API delivers via WebSocket). Severity: HIGH if ISC >= 3, MEDIUM otherwise.

**ISC (Independent Source Count)** answers: "How many different TYPES of platforms report
this story?" BBC(web) + Reuters(web) + Reddit + Telegram = ISC 3 (not 4 — BBC and Reuters
are both "web"). If ISC >= threshold → signal fires. High ISC = likely real event,
not one source echoing itself.

## Credibility Auto-Feedback (3 Passes)

**Pass 1: Deepfake amplification drop (24h).** Sources sharing content with deepfake_score > 0.8
in last 7 days → score reduced by min_auto_drop × count. 4-table JOIN: sources → content_items
→ media_assets → vision_results.

**Pass 2: Cross-verification boost (post-clustering).** Sources in multi-platform clusters
(ISC >= 2) with score >= 60 → boosted by 5 points. Not a timer — enqueued by run_clustering.

**Pass 3: Contradiction drop (daily 02:00).** Sources with high ratio of unclustered items
on topics that have real clusters → score reduced. noise_ratio >= 0.6 = contradiction signal.

All changes atomic (score update + audit log in same transaction), clamped to [0, 100].

---

# TOPIC 7: VISION PIPELINE

## Triggers

Three entry points → same pipeline: scraper downloads image → enqueue; social adapter
finds media → enqueue; analyst uploads via API → enqueue. All go to arq:vision queue.

## The 8-Step Pipeline (run_vision_analysis)

**What an image is to a computer:** a grid of pixels, each with 3 numbers (R, G, B, 0-255).
A 224×224 image = 150,528 numbers. All vision AI operates on these numbers.

### Step 3: EXIF (NOT AI — just file metadata parsing)

Cameras embed hidden metadata in image files: GPS coordinates, device make/model,
software used, timestamps. Anveshak reads this via Pillow and scans the Software field
for AI tool signatures ("stable diffusion", "midjourney", "dall-e", etc.).

EXIF and deepfake detection are COMPLETELY INDEPENDENT. EXIF reads file metadata
(easy to strip/fake). Deepfake models analyze actual pixels (much harder to fool).
Both results stored separately, both shown to analyst. A smart propagandist strips EXIF
but the deepfake model still catches pixel-level AI fingerprints.

### Step 3 continued: pHash (perceptual hash)

Unlike SHA-256 (changes if one pixel changes), pHash captures visual structure:
shrink to 32×32 → grayscale → DCT (frequency transform) → keep top 64 values →
each value > average = 1 bit → 64-bit integer. Similar images = similar hashes.
Hamming distance (XOR + bit count) ≤ 8 = near-duplicate. Stored as BIGINT.
API: GET /api/v1/vision/reverse-search?phash=XXX finds near-duplicates across DB.

### Step 4: YOLO ("What objects are in this image?")

YOLOv8 neural network trained on COCO dataset (80 classes). Divides image into grid,
each cell predicts: is there an object? what class? bounding box coordinates.
Filtered by confidence threshold (0.25), non-maximum suppression removes duplicates.
High-interest labels (person, airplane, boat, gun, etc.) tagged into content_items.labels.

YOLO knows only 80 generic classes. It CANNOT distinguish "fighter jet" from "commercial
airplane" or "military vehicle" from "delivery truck" — that's CLIP's job.

### Step 5: Deepfake Detection

**Two models, routed by face presence:**
- has_faces() (OpenCV Haar cascade, fast, non-AI) → YES: FacetorchDetector (face_deepfake.onnx,
  ~50MB, trained on FaceForensics++) → NO: EfficientNetDetector (deepfake_b0.onnx, ~20MB,
  trained on GenImage). Both are ONNX format, pre-downloaded in Docker volume.

**For videos:** ffmpeg extracts keyframes every 5 seconds. Each frame scored individually.
Final score = MAX(all frame scores) — worst case. Conservative: if one frame looks fake,
entire video flagged.

**Image preprocessing:** resize to 224×224, normalize to [0,1], ImageNet mean/std normalization,
reshape to [1,3,224,224] float32 tensor. Both models expect this exact format.

**Ollama is NOT used here.** Ollama (qwen2:7b) is the LLM that generates text for reports
and cluster labels. Ollama is the SERVER (like Docker hosts containers); qwen2 is the MODEL
(like your app runs inside Docker). Vision uses separate ONNX models, not Ollama.

### Step 6: CLIP ("Does this match analyst-defined categories?")

OpenAI CLIP trained on 400M image-text pairs. Encodes BOTH images and text into the same
vector space. If image and text describe the same thing → vectors are close.

Analyst defines clip_categories on the topic (e.g., ["military vehicle", "naval vessel",
"satellite image"]). CLIP encodes image + each category → cosine similarity → softmax → scores.
If no categories defined → CLIP skipped entirely.

**CLIP's limitations:** Works well for BROAD categories ("military vehicle" vs "civilian car",
>0.85 confidence). Poor for SPECIFIC identification ("Sukhoi Su-30" vs "Rafale", 0.5-0.7).
Fails for variants ("Su-30MKI" vs "Su-30SM", <0.4). CLIP learned from internet captions,
not military expert knowledge. Most captions say "fighter jet" not "Sukhoi Su-30MKI with
thrust-vectoring nozzles." See discussion D2 in learning_suggestions.md.

### Steps 7-8: Persist + Tag

INSERT vision_results ON CONFLICT(media_asset_id) DO UPDATE (idempotent).
Tag content_items.labels with high-interest YOLO detections.
Log warning if deepfake_score > 0.8 (credibility downgrade handled by analyst, not vision).

## All ML Models in Anveshak

**Pip packages (no download):** langdetect, VADER, YAKE, imagehash, geonamescache, OpenCV Haar.
**HuggingFace downloads:** NLLB-200 (2.4GB), spaCy x3 (~130MB), sentence-transformers (80MB),
CLIP (600MB), YOLOv8 nano (6MB).
**Pre-downloaded ONNX:** Facetorch (50MB), EfficientNet (20MB).
**Ollama model:** qwen2:7b (4.4GB Q4_0) — ONLY model that generates text.

Worker constraints: vision max_jobs=2 (CPU-heavy, avoids OOM in 6GB container).
Model singletons loaded once per worker process, reused across all jobs.

---

# TOPIC 8: REPORT GENERATION

## The Flow

Analyst clicks "Generate Report" → POST /api/v1/reports → create empty row (generated_at=NULL)
→ enqueue to arq:reporter → return {report_id} in <100ms → frontend polls every 5s.

## The 9 Steps

1. **LOAD** report + topic from DB
2. **QUERY EMBEDDING** — encode "topic_name keyword1 keyword2" via sentence-transformer
3. **RAG RETRIEVAL** — pgvector: ORDER BY embedding <-> query_vector LIMIT 10,
   filtered by credibility_min. No chunks = report FAILS with helpful error.
4. **ASSEMBLE CONTEXT** — format each chunk as `[Source: url | Credibility: score | date]\ntext`.
   Add chunks until token budget (4000) reached. Token estimate: len(text)//4.
5. **RENDER PROMPT** — Jinja2 template with role, grounding rules, JSON schema, few-shot example.
   User input wrapped in XML markers (`<topic>`, `<context>`) to prevent prompt injection.
6. **CALL LLM** — Ollama (qwen2:7b) via HTTP, 300s timeout. Output parsed through Pydantic
   ReportContent. On failure → retry with stricter prompt ("ONLY the JSON"). All retries
   exhausted → report marked failed. NEVER store raw LLM output (Rule 9).
7. **SOURCE SNAPSHOT** — fetch current credibility for every cited source, freeze as JSONB.
8. **GEOCODE** — extract location names from LLM output (regex + geonamescache lookup),
   convert to lat/lon, build GeoJSON FeatureCollection. geonamescache is a pip package (~32MB)
   with ~24K cities bundled — no API calls (sovereign). Limitations: misses regions,
   provinces, military bases (see suggestion #3).
9. **STORE** — UPDATE WHERE generated_at IS NULL (immutability guard, idempotent for retry).

**Why 4000 token budget?** qwen2:7b has ~8192 context window. System prompt ~1500 tokens,
RAG context ~4000, LLM output ~2000, buffer ~700. Total ~8200 ≈ 8192. Configurable via
RAG_MAX_CONTEXT_TOKENS env var. Upgrade to qwen2.5:72b (128K context) → set to 16000+.

## Three Report Types

intelligence_brief: tactical, 4-sentence max summary, prioritize by urgency.
research_summary: analytical, 3+ findings, 2+ recommendations, distinguish confirmed vs single-source.
weekly_digest: patterns and trends from past week, group by theme.

## Anti-Hallucination Layers

1. RAG (only real scraped content in prompt). 2. Grounding rules ("ONLY use facts in CONTEXT").
3. Source citations (verifiable URLs). 4. Confidence score (fraction backed by 2+ sources).
5. Pydantic validation (structural correctness). LLM can still misattribute within context,
but can't invent events or cite nonexistent URLs.

## Scheduled Reports

Topic has scheduled_report_cron (e.g., "0 6 * * 1" = Monday 6 AM) and scheduled_report_type.
check_scheduled_reports cron runs every 15 min: uses croniter to check if cron fired since
last report → if yes, create row + enqueue. Analyst comes in Monday morning → report already waiting.

## Source Warnings

check_source_warnings runs every 6h: compares current source credibility against source_snapshot
in recent reports. If downgraded → INSERT report_source_warnings. Report untouched (Rule 4).

---

# TOPIC 9: FRONTEND

## Stack

React 18 + TypeScript + Vite + Tailwind CSS. Served via Nginx (port 3000).
Server state: @tanstack/react-query (caching, polling, retry). UI state: useState (local per page).
Global state: React Context (Auth, Theme, WebSocket).

## Provider Stack

ThemeProvider → QueryClientProvider (30s staleTime, 2 retries, refetchOnWindowFocus) →
BrowserRouter → AuthProvider → App → ErrorBoundary → ProtectedRoute → WSProvider → Layout → Pages.

## 7 Pages

Login (/login), TopicsDashboard (/topics), ContentFeed (/topics/:id/feed with infinite scroll),
SignalsInbox (/signals with WebSocket live counter), ReportBuilder (/reports with lazy-loaded
MapLibre GL), ImageAnalysis (/vision with YOLO canvas overlay), SourceManager (/sources with
credibility bars and audit log).

## Authentication (AuthContext)

JWT stored in localStorage('anveshak_token'). Decoded client-side (base64, no crypto).
Expiry countdown ticks every second — warns 5 min before expiry. Auto-logout at 0.
Axios interceptor attaches Authorization: Bearer header to every request.
Global 401 handler clears token and redirects to /login.

## WebSocket (WSContext)

Singleton connection: ws://host/api/v1/signals/ws/{session_id}?token=JWT&since=ISO.
Session ID persisted in localStorage (crypto.randomUUID). On message: ignore pings,
invalidate React Query ['signals'] cache (auto-refetch), notify subscribers.
On close: record disconnectedAt, exponential backoff reconnect (1s→2s→4s→8s cap).
On reconnect: sends since= to replay missed signals.

## API Client Pattern

Axios instance with JWT interceptor. One file per domain (topics.ts, signals.ts, etc.).
Each exports functions that chain axios calls: `api.get<T>(url).then(r => r.data)`.
Used in components via React Query useQuery/useMutation.

## Key Frontend Patterns

Optimistic updates in SignalsInbox — card removed before API confirms, rollback on error.
MapLibre GL lazy-loaded (~700KB) via React.lazy() — only imported when GIS tab clicked.
Infinite scroll via useInfiniteContent hook + Intersection Observer sentinel.

---

# TOPIC 10: INFRASTRUCTURE & DEVOPS

## 19 Containers

Data stores (3): postgres (pgvector:pg16, :5433, 1GB), redis (7-alpine, :6379, 256MB),
ollama (latest, :11434, 8GB).

Application (12): api (:8000, 512MB), scraper (:8001, 768MB), scraper-worker (1GB),
social (:8002, 512MB), analyst-scheduler (:8007, 512MB), analyst-worker (6GB),
reporter (:8005, 512MB), reporter-worker (:8006, 1GB), vision (:8003, 4GB),
vision-worker (6GB), frontend (:3000, 256MB).

Observability (5+): prometheus (:9090, 512MB), grafana (:3001, 256MB), loki (:3100, 512MB),
promtail (128MB), postgres-exporter (:9187, 64MB), redis-exporter (:9121, 64MB),
jaeger optional (:16686, 512MB, --profile tracing only).

Total RAM: ~26GB all running. Minimum usable: ~16GB without vision.

## Port Confusions

PostgreSQL is **5433** (not 5432). Grafana is **3001** (not 3000, that's frontend).
Jaeger only with --profile tracing.

## Shared Volumes

vision_media is shared between scraper, social, vision, vision-worker. Scraper writes,
vision reads. Without this volume → FileNotFoundError on every vision job.
analyst_models persists HuggingFace model downloads across restarts. Mounted by analyst-worker
(scheduler does not need ML models).

## Observability Stack

Logs: all services → JSON stdout → Docker captures → Promtail reads Docker socket →
ships to Loki → queryable in Grafana.
Metrics: each service /metrics endpoint → Prometheus scrapes every 15s → 15-day retention →
Grafana dashboards (8 pre-provisioned, read-only from JSON files).
Traces: optional via OTEL_ENABLED=true → OpenTelemetry → Jaeger.

## Makefile

Daily: make up/down/restart/ps/logs/logs-SERVICE/shell-SERVICE/health.
Database: make migrate/migrate-status/seed-demo.
Testing: make test/test-unit/test-integration/test-e2e.
Validation: make syscheck/validate/validate-vision/validate-all/demo-check.
Cleanup (increasingly destructive): make clean → clean-containers → clean-volumes → purge → nuke.

## Compose Overlays

compose.vision.yml: adds NVIDIA GPU reservation to vision containers.
compose.bridge.yml: enables Drishti entity emission (Redpanda + mTLS).

## Environment (.env)

Must exist (copy from .env.example). Must set: POSTGRES_PASSWORD, API_SECRET_KEY,
GRAFANA_ADMIN_PASSWORD. All other vars have sensible defaults.

---

# TOPIC 11: DEBUGGING & TROUBLESHOOTING

## Step Zero: Always Start Here

`make ps` (are containers running?), `make health` (quick health check),
`make logs-SERVICE` (check specific service).

## Scenario 1: Content Not Appearing

1. Check scraper-worker logs for errors
2. Check topic_sources table — source linked? (#1 cause)
3. Check source health_status — circuit breaker tripped (3+ failures)?
4. Check for dedup hits in logs
5. Query content_items directly (count + max created_at)

## Scenario 2: Embeddings Are NULL

1. Count unprocessed: SELECT count(*) WHERE embedding IS NULL
2. Check analyst logs for model loading errors
3. Check if spaCy models downloaded
4. Check if NLLB is downloading (2.4GB first time)
5. Check Prometheus rate: analyst_nlp_jobs_total

## Scenario 3: Signals Not Firing

1. Check clusters exist (narrative_clusters table)
2. Compare ISC vs topic threshold
3. Check signal_engine logs
4. Check 24h dedup window (same cluster won't fire twice)
5. Check delivered_at — NULL means API delivery loop not running

## Scenario 4: Reports Failing

1. Check generation_error column in reports table
2. Check reporter-worker logs
3. Test Ollama directly: curl localhost:11434/api/tags
4. Check ARQ queue depth: LLEN arq:reporter:queue
5. Check timeout (job_timeout=600, Ollama can take 5+ min on CPU)

## Scenario 5: Vision Always Returns 0.0

99% of the time: ONNX model files not downloaded. Check /app/models/ in vision container.
Fix: make download-models.

## Scenario 6: WebSocket Disconnects

Check API signal_delivery logs, check browser DevTools WS tab, check API container health.

## Reading Logs

Production JSON: pipe through `python3 -m json.tool` or `jq`. Development: colored, human-readable.
`make logs-analyst 2>&1 | jq 'select(.level=="error")'` — errors only.

## Checking Redis/ARQ

`redis-cli` inside container. KEYS arq:*, LLEN arq:SERVICE:queue, KEYS arq:result:*,
GET anveshak:x:monthly_reads:YYYY-MM. GUI: RedisInsight (free, like DBeaver for Redis).

## Prometheus

Direct: curl localhost:8000/metrics. PromQL: curl localhost:9090/api/v1/query?query=...
Key queries: rate(scraper_items_fetched_total[5m]), analyst_nlp_jobs_total{status='failed'},
arq_jobs_failed_total.

## Grafana

localhost:3001, admin/<GRAFANA_ADMIN_PASSWORD>. 8 dashboards: Overview, Ingestion, Signals,
Vision, Reporter, Credibility, Infrastructure, Logs. Loki queries in Explore tab:
`{container_name=~"anveshak-analyst.*"} |= "error"`.

## Quick Reference

| Problem | First Check | Then Check |
|---------|-------------|------------|
| Container won't start | make logs-SERVICE | Docker RAM limits |
| Content not appearing | topic_sources table | scraper-worker logs |
| Embeddings NULL | analyst logs | model download status |
| No clusters | embedding count >= 3? | hdbscan_min_cluster_size |
| Signals not firing | ISC vs threshold | signal dedup (24h) |
| Signals not in frontend | delivered_at IS NULL? | WebSocket connection |
| Reports failing | generation_error column | Ollama status |
| Vision always 0.0 | /app/models/ files exist? | vision-worker logs |

## Ultimate Sanity Check

`make validate` — runs full pipeline validation. If it passes, everything works end-to-end.
