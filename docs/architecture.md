# Anveshak — System Architecture

Anveshak (Sanskrit: investigator, seeker) is a standalone, sovereign AI-OSINT analysis and monitoring platform built for iDEX ADITI 4.0 PS-18 (Indian Air Force). It runs entirely on a single machine — no cloud dependencies, no Kafka, no Vault, no graph database required.

**Product strategy:** Sell Anveshak first. Drishti (entity resolution platform) is the upsell.

---

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Container Map](#container-map)
3. [Data Stores](#data-stores)
4. [Application Services](#application-services)
5. [Background Workers](#background-workers)
6. [Frontend](#frontend)
7. [Observability Stack](#observability-stack)
8. [Inter-Service Communication](#inter-service-communication)
9. [Data Flow — End to End](#data-flow--end-to-end)
10. [Database Schema](#database-schema)
11. [Vector Similarity Pipeline](#vector-similarity-pipeline)
12. [Signal Engine](#signal-engine)
13. [Report Generation Pipeline](#report-generation-pipeline)
14. [Security Model](#security-model)
15. [Hardware Independence](#hardware-independence)
16. [Validation Suite](#validation-suite)
17. [Deployment](#deployment)
18. [Key Invariants](#key-invariants)

---

## High-Level Architecture

```
╔══════════════════════════════════════════════════════════════════════╗
║                           INTERNET                                  ║
║    Websites   RSS Feeds   Telegram   Reddit   Bluesky   X/Twitter   ║
╚═══════╤═══════════════════════════════════════╤══════════════════════╝
        │                                       │
  ┌─────▼──────┐                         ┌──────▼───────┐
  │  scraper   │  Crawl4AI + trafilatura │   social     │  Telethon, PRAW,
  │  + worker  │  web pages + RSS feeds  │              │  atproto, tweepy
  └─────┬──────┘                         └──────┬───────┘
        │            content_items               │
        └───────────────────┬────────────────────┘
                            │ INSERT ... ON CONFLICT(content_hash) DO NOTHING
                     ┌──────▼──────┐
                     │ PostgreSQL  │  pgvector (384-dim embeddings)
                     │  + pgvector │  12 tables, SHA-256 dedup
                     └──────┬──────┘
                            │
         ┌──────────────────┼──────────────────────┐
         │                  │                      │
   ┌──────▼───────┐   ┌─────▼──────┐       ┌───────▼────────┐
   │  analyst-    │   │  vision    │       │   reporter     │
   │  scheduler   │   │            │       │   + worker     │
   │  (512 MB)    │   │ YOLOv8    │       │ RAG + Ollama   │
   │ Leiden clust │   │ deepfake  │       │ PDF export     │
   │ signals      │   │ CLIP      │       │ GeoJSON        │
   │ convergence  │   │ EXIF/pHash│       │ scheduled cron │
   │ orphan sweep │   └────────────┘       └───────┬────────┘
   └──────┬───────┘                                │
          │ enqueues to ARQ                        │
   ┌──────▼───────┐                                │
   │  analyst-    │                                │
   │  worker (×N) │                                │
   │  (6 GB)      │                                │
   │ spaCy NLP    │                                │
   │ NLLB trans   │                                │
   │ embeddings   │                                │
   │ sentiment    │                                │
   │ labels       │                                │
   └──────┬───────┘                                │
         │          signals + reports              │
         └──────────────────┬──────────────────────┘
                            │
                     ┌──────▼──────┐
                     │    API      │  FastAPI gateway
                     │  (gateway)  │  JWT auth, WebSocket push
                     │             │  ARQ job dispatch
                     └──────┬──────┘
                            │
                     ┌──────▼──────┐
                     │  frontend   │  React + Vite + MapLibre
                     │  (analyst   │  analyst workbench UI
                     │  workbench) │
                     └─────────────┘

  ┌─────────────┐    ┌─────────────┐
  │   Ollama    │    │   Redis     │  ARQ task queue
  │  qwen2:7b   │    │             │  rate limiting
  │ (local LLM) │    │             │  caching
  └─────────────┘    └─────────────┘

  ┌─────────────────────────────────────────────┐
  │           Observability Stack                │
  │  Prometheus → Alertmanager → webhook        │
  │  Prometheus → Grafana (8 dashboards)         │
  │  Loki ← Promtail (structured logs)          │
  │  Jaeger (opt-in distributed tracing)         │
  │  cAdvisor, postgres-exporter, redis-exporter │
  └─────────────────────────────────────────────┘

  ┌─────────────┐    (optional, one-way only)
  │   Drishti   │ ←── Anveshak emits entities
  │  Platform   │     via source.envelopes.v1
  └─────────────┘     ANVESHAK_DRISHTI_BRIDGE=true
```

---

## Container Map

Anveshak runs as **23 containers** (+ 1 optional) on a single Docker network (`anveshak-net`). Here is every container, what it does, why it exists, and how it connects to the rest of the system.

### At a Glance

| Container | Image | Port | Memory | Role |
|-----------|-------|------|--------|------|
| `postgres` | pgvector/pgvector:pg16 | 5433→5432 | 1 GB | Primary database |
| `redis` | redis:7-alpine | 6379 | 256 MB | Task queue + cache |
| `ollama` | ollama/ollama | 11434 | 8 GB | Local LLM inference |
| `api` | anveshak-api | 8000 | 512 MB | API gateway |
| `scraper` | anveshak-scraper | 8001 | 768 MB | Web crawl scheduler |
| `scraper-worker` | anveshak-scraper | — | 1 GB | Web crawl job executor |
| `social` | anveshak-social | 8002 | 512 MB | Social media poller |
| `analyst-scheduler` | anveshak-analyst | 8007 | 512 MB | Clustering + signals + convergence |
| `analyst-worker` | anveshak-analyst | — | 6 GB | NLP + embedding + labelling (ARQ) |
| `reporter` | anveshak-reporter | 8005 | 512 MB | Report API |
| `reporter-worker` | anveshak-reporter | 8006 | 1 GB | LLM report generator |
| `vision-init` | anveshak-vision | — | 2 GB | Downloads ML models on first startup (runs once) |
| `vision` | anveshak-vision | 8003 | 512 MB | Vision API (file storage + hashing) |
| `vision-worker` | anveshak-vision | — | 6 GB | YOLO + CLIP + deepfake (ARQ) |
| `frontend` | anveshak-frontend | 3000 | 256 MB | Analyst workbench UI |
| `prometheus` | prom/prometheus | 9090 | 512 MB | Metrics collection |
| `grafana` | grafana/grafana | 3001 | 256 MB | Dashboards |
| `loki` | grafana/loki:3.0.0 | 3100 | 512 MB | Log aggregation |
| `promtail` | grafana/promtail:3.0.0 | — | 128 MB | Log shipping |
| `postgres-exporter` | postgres-exporter | 9187 | 64 MB | DB metrics |
| `redis-exporter` | redis_exporter | 9121 | 64 MB | Cache metrics |
| `alertmanager` | prom/alertmanager | 9093 | 128 MB | Alert delivery (webhook) |
| `cadvisor` | cadvisor:v0.49.1 | 8080 | 256 MB | Container resource monitoring |
| `jaeger` | jaeger-all-in-one | 16686 | 512 MB | Tracing (opt-in) |

**Total baseline memory:** ~22 GB (without vision overlay)

---

## Data Stores

### PostgreSQL (`postgres`)

**What it does:** Stores all application data — topics, sources, content items, extracted entities, narrative clusters, signals, reports, vision results, and audit logs.

**Why it's needed:** Single source of truth for the entire platform. Uses the `pgvector` extension (384-dimensional vectors) for semantic similarity search, which powers content clustering, topic backfilling, and RAG retrieval for report generation. Also uses `pg_trgm` for fuzzy text search on entity names.

**Key details:**

- Image: `pgvector/pgvector:pg16` (PostgreSQL 16 with vector extension pre-installed)
- Data persisted to `postgres_data` volume
- Extensions loaded on init: `vector`, `uuid-ossp`, `pg_trgm`, `btree_gin`
- Host port 5433 (avoids conflict with any local PostgreSQL on 5432)
- 12 core tables (see [Database Schema](#database-schema))

**Connects to:**

- Every application service reads/writes via `asyncpg` connection pool
- `postgres-exporter` scrapes internal stats for Prometheus

---

### Redis (`redis`)

**What it does:** Serves as the task queue backend for ARQ (Async Redis Queue) and provides rate limiting and ephemeral caching.

**Why it's needed:** All heavy work (web scraping, NLP processing, LLM report generation) runs as background jobs, not in HTTP request handlers. Redis + ARQ provides reliable job dispatch with retry logic, timeout enforcement, and queue isolation. This keeps the API responsive (sub-100ms responses) while heavy ML tasks run asynchronously.

**Key details:**

- Image: `redis:7-alpine`
- Max memory: 200 MB with LRU eviction
- Persistence: RDB snapshot every 60 seconds + AOF (`appendonly yes`, `appendfsync everysec`)
- Data persisted to `redis_data` volume
- AOF ensures ARQ job queues survive Redis crashes (RDB-only had a 60s data-loss window)

**ARQ queues:**

- `arq:queue` — default queue (scraper jobs, report generation)
- Jobs include: `scrape_topic`, `poll_rss_sources`, `check_all_source_health`, `generate_report`, `check_scheduled_reports`, `check_source_warnings`

**Connects to:**

- `scraper` / `scraper-worker` — enqueue and execute scraping jobs
- `reporter` / `reporter-worker` — enqueue and execute report generation
- `api` — enqueues vision analysis jobs
- `analyst` — polls for NLP work (uses direct DB polling, not ARQ)
- `redis-exporter` — scrapes metrics for Prometheus

---

### Ollama (`ollama`)

**What it does:** Runs large language models locally for report generation and cluster labelling. Currently runs `qwen2:7b` (Q4_0 quantized, ~4.4 GB).

**Why it's needed:** Sovereign requirement — intelligence data must never leave the deployment boundary. No cloud LLM APIs (OpenAI, Anthropic, etc.) are permitted with real data. Ollama provides a local inference API compatible with the OpenAI chat format, accessible via LiteLLM abstraction layer.

**Key details:**

- Image: `ollama/ollama:latest`
- Memory limit: 8 GB (model weights + KV cache)
- Model stored in `ollama_models` volume (survives container restarts)
- `OLLAMA_NUM_PARALLEL=2` — allows concurrent inference requests
- `OLLAMA_KEEP_ALIVE=5m` — keeps model loaded in memory between requests

**Used by:**

- `reporter-worker` — RAG-grounded report generation (intelligence briefs, summaries, digests)
- `analyst` — cluster label generation (short descriptive labels for narrative clusters)
- `api` — pre-warms model on startup to avoid cold-start latency

**Not used by:** scraper, social, vision (these don't need LLM inference)

---

## Application Services

### API Gateway (`api`)

**What it does:** The single entry point for all client requests. Handles authentication, routes requests to the database, dispatches background jobs, and pushes real-time signals to connected analyst sessions via WebSocket.

**Why it's needed:** Centralises access control, rate limiting, and request routing. No other service exposes HTTP endpoints to the frontend — everything goes through the API.

**Key responsibilities:**

- **JWT authentication + RBAC** — login issues JWT with `role` and `jti` fields. Three roles enforced on every route: `admin` (full access + user management), `analyst` (read + write), `viewer` (read-only). `require_role()` dependency on all route handlers.
- **Token revocation** — `POST /auth/logout` revokes current token by storing `jti` in Redis blocklist with TTL. `GET /auth/me` returns current user info.
- **JWT startup guard** — API refuses to start if `JWT_SECRET_KEY` is the insecure default `"change-me-in-production"`.
- **Audit trail** — every mutating API operation (14 actions across topics, sources, signals, reports, users, clusters) is logged to `audit_trail` table with user_id, IP address, action, and details. Admin-only query via `GET /system/audit-trail`.
- **Dead-letter queue** — failed ARQ jobs are persisted to `failed_jobs` table for admin review via `GET /system/failed-jobs`.
- **Topic management** — CRUD for topics (keywords, signal thresholds, languages)
- **Source management** — CRUD for OSINT sources (URLs, platforms, credibility scores)
- **Content search** — pgvector cosine similarity search across the corpus
- **Signal delivery** — background loop polls DB every 5s for new signals, pushes via WebSocket
- **Vision dispatch** — accepts image/video uploads, enqueues ARQ jobs for vision service
- **Report proxy** — forwards report requests to the reporter service
- **Export** — streaming CSV/JSON export of content items, signals, entity lists
- **Intelligence endpoints** — entity co-occurrence graphs, topic similarity, source discovery, cluster duplicate detection, cluster merging
- **Webhook notifications** — fires HTTP POST to configured webhook URL on new signals

**Middleware (applied in order):**

1. CORS (configurable origins via `ALLOWED_ORIGINS`, explicit method list — no wildcard)
2. Rate limiting (4-tier sliding window: login 10/min, vision 30/min, auth 120/min, anon 60/min)
3. Security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Content-Security-Policy, Strict-Transport-Security when `HSTS_ENABLED=true`)
4. RBAC enforcement (`require_role()` dependency on every route handler)

**Connects to:**

- `postgres` — direct DB access via asyncpg pool
- `redis` — ARQ job dispatch + rate limit state
- `ollama` — pre-warm on startup
- `frontend` — serves REST API + WebSocket
- `reporter` — proxies report download requests
- `scraper`, `social`, `analyst` — service URL config for health checks

---

### Scraper (`scraper`)

**What it does:** Schedules web content collection. Polls active topics on a configurable interval and enqueues scraping jobs into the ARQ queue.

**Why it's needed:** Separates the scheduling concern from the actual crawling work. The scraper process is lightweight — it just reads topics from the DB and enqueues jobs. The heavy HTTP fetching and content extraction happens in the `scraper-worker`.

**Key details:**

- Polls every `SCRAPER_POLL_INTERVAL_S` (default: 30 seconds)
- For each active topic, enqueues two jobs: `scrape_topic` (web sources) and `poll_rss_sources` (RSS feeds)
- Prometheus metrics on port 8001
- Includes Playwright browsers for JavaScript-rendered pages

**Connects to:**

- `postgres` — reads active topics and sources
- `redis` — enqueues ARQ jobs

---

### Social Media Monitor (`social`)

**What it does:** Polls social media platforms for content matching active topics. Supports Telegram (Telethon), Reddit (PRAW), Bluesky (atproto), and X/Twitter (tweepy).

**Why it's needed:** Social media is a primary OSINT source. Each platform has its own API, rate limits, and authentication requirements. The social service abstracts these behind a common `SourceAdapterBase` interface.

**Key details:**

- Each adapter is independently toggleable via environment variables
- X/Twitter has a separate poll interval and hard monthly read cap (`X_MONTHLY_READ_CAP`) to control API costs ($0.005/read)
- Rate limited at `SOCIAL_RATE_LIMIT_RPM` (default: 60 requests/minute)
- All adapters produce `content_items` with the same schema as web-scraped content

**Connects to:**

- `postgres` — reads topics/sources, writes content items
- `redis` — enqueues social polling jobs
- External APIs — Telegram, Reddit, Bluesky, X/Twitter (outbound only)

---

### Analyst Scheduler (`analyst-scheduler`)

**What it does:** Lightweight coordination service that runs batch operations needing global state. Does NOT load ML models (spaCy, NLLB, sentence-transformers). Memory: ~124 MiB.

Runs four concurrent async loops:

1. **Clustering Loop** (every 5 min) — runs near-duplicate detection, then **incremental clustering** per topic. New items are assigned to nearest existing cluster centroid (cosine similarity ≥ 0.75); only truly unassigned items go through **Leiden community detection** on a blended similarity graph (70% cosine + 30% entity MinHash). Articles sharing named entities cluster together even with distant embeddings. Creates/updates `narrative_clusters` with item counts and source diversity metrics. Excludes near-duplicate items from `independent_source_count` to prevent false signals. Archives stale clusters older than `cluster_archive_after_days`. After clustering, **enqueues** `generate_cluster_label` and `run_cross_verification` to the analyst-worker via ARQ (never calls Ollama directly). Label staleness tracked via `label_item_hash` — re-enqueues label generation when cluster composition changes by >30%. See `docs/narrative_clustering_algorithm.md` for the full algorithm explanation.

2. **Signal Check Loop** (every 5 min) — monitors clusters for corroboration threshold: when `independent_source_count >= topic.signal_threshold`, fires a signal (inserts into `signals` table). Also checks for sentiment shifts (compound score drops >0.3 over 24h baseline).

3. **Convergence Loop** (every 15 min) — detects when two different topics surface the same narrative by comparing cluster centroids across topics. Fires `cross_topic_convergence` signals when centroid similarity exceeds threshold.

4. **Orphan Sweep** (every 5 min) — safety net for content items where the scraper/social enqueue to ARQ failed after DB insert. Finds `content_items WHERE embedding IS NULL AND created_at > NOW() - 1 hour` and re-enqueues them to the analyst-worker.

**Key details:**

- Memory limit: 512 MB (no ML models — just asyncpg, numpy, leidenalg, arq)
- Port 8007 for Prometheus metrics
- Does NOT depend on Ollama
- Always runs as a single instance (clustering needs global state)

**Connects to:**

- `postgres` — reads embeddings/clusters, writes cluster results and signals
- `redis` — enqueues jobs to `arq:analyst` queue for the worker

---

### Analyst Worker (`analyst-worker`)

**What it does:** ARQ-based ML inference worker that processes per-item NLP jobs. Loads all ML models once at startup. Horizontally scalable via `ANALYST_WORKER_REPLICAS`.

Registered ARQ jobs:

1. **`analyse_content`** — full NLP pipeline per content item:
   - Language detection (langdetect)
   - NLLB-200 translation (non-English → English)
   - spaCy NER (English, Russian, Chinese models)
   - Sentence-transformer embedding (384 dimensions, all-MiniLM-L6-v2)
   - Entity MinHash fingerprint (128-permutation signature from extracted entities)
   - VADER sentiment analysis + YAKE keyword extraction
   - Topic relevance scoring (cosine similarity vs topic query embedding)
   - Results stored in `content_items.embedding`, `content_items.entity_minhash`, `content_items.labels`, `extracted_entities`

2. **`generate_cluster_label`** — Ollama LLM call to generate human-readable cluster labels

3. **`run_cross_verification`** — boosts credibility of sources confirmed by multi-platform clusters

4. **`backfill_all_topics`** (cron, every 6h) — pgvector cosine similarity search to discover historical content matching active topic keywords

5. **`update_source_credibility`** (cron, daily 03:00) — auto-downgrades source credibility for deepfake amplification

6. **`run_contradiction_scoring`** (cron, daily 02:00) — reduces credibility for sources with high noise-item ratio

**Why the split:** The old monolithic analyst ran NLP inline in an asyncio loop, blocking clustering and signal checks during CPU-heavy work (~10s/item with translation). The split allows the scheduler to run clustering/signals unblocked while workers process NLP in parallel. Scaling from 1 to 4 workers multiplies NLP throughput without duplicating scheduler work.

**Key details:**

- Memory limit: 6 GB per replica (3 spaCy models + NLLB + embedding model)
- Models cached in `analyst_models` volume (shared across restarts)
- Scalable: `ANALYST_WORKER_REPLICAS=1` (laptop) to `4` (production)
- ARQ Redis BLPOP guarantees exactly-once job delivery across replicas

**Connects to:**

- `postgres` — reads content items, writes embeddings/entities/clusters/signals
- `redis` — picks up jobs from `arq:analyst` queue
- `ollama` — cluster label generation (qwen2:7b)

---

### Reporter (`reporter`)

**What it does:** Provides the report management API — creating report stubs, listing reports, and serving generated PDFs and GeoJSON.

**Why it's needed:** Separates the lightweight API (create report request, check status, download PDF) from the heavy LLM generation work that runs in the worker. The API returns immediately with a job ID; the frontend polls until generation completes.

**Key details:**

- FastAPI app on port 8005
- Report types: `intelligence_brief`, `research_summary`, `weekly_digest`
- Cron-based scheduled reports evaluated every 15 minutes
- Generated PDFs stored in `reporter_output` volume

**Connects to:**

- `postgres` — report CRUD, source snapshot storage
- `redis` — enqueues `generate_report` ARQ jobs
- `ollama` — health check only (actual inference in worker)

---

## Background Workers

Workers are separate container processes that execute heavy background jobs dispatched via ARQ (Redis queue). They use the **same Docker image** as their parent service but run a different entrypoint command.

### Scraper Worker (`scraper-worker`)

**What it does:** Executes the actual web crawling and content extraction.

**Jobs:**

- `scrape_topic` — fetches all active web sources for a topic using Crawl4AI + trafilatura. Concurrent fetching with configurable semaphore. Circuit breaker skips sources with `health_status='down'`.
- `poll_rss_sources` — parses RSS/Atom feeds, extracts articles
- `check_all_source_health` — daily cron (02:00 UTC) checks all source URLs are reachable

**Key details:**

- Memory limit: 1 GB (Playwright browser instances)
- Includes Playwright for JavaScript-rendered pages
- Content deduplication: SHA-256 hash, `ON CONFLICT(content_hash) DO NOTHING`
- Extracts media assets (images) and dispatches vision analysis jobs
- Media files stored in `media_store` volume

**Connects to:**

- `postgres` — writes content items, media assets
- `redis` — receives jobs from ARQ queue
- Internet — outbound HTTP to source URLs

---

### Reporter Worker (`reporter-worker`)

**What it does:** Executes the LLM report generation pipeline.

**Jobs:**

- `generate_report` — the full pipeline:
  1. RAG retrieval: pgvector cosine search over topic content → top-k context chunks
  2. Context enrichment: each chunk gets a header with source URL, credibility score, date
  3. Prompt rendering: few-shot template with grounding rules
  4. Ollama inference: qwen2:7b generates structured report (max timeout: 540s)
  5. Pydantic validation: LLM output parsed and validated before storage
  6. Geocoding: extract locations → GeoJSON for map display
  7. PDF generation: Markdown → HTML → PDF
  8. `generated_at` set ONCE (report becomes immutable)
- `check_scheduled_reports` — every 15 min, evaluates cron expressions on topics and auto-generates due reports
- `check_source_warnings` — every 6 hours, checks if any source cited in a report has been downgraded since generation, writes `report_source_warnings`

**Key details:**

- Memory limit: 1 GB
- Prometheus metrics on port 8006
- Idempotency guard: `WHERE generated_at IS NULL` prevents re-generation
- **Ollama circuit breaker** — Redis-backed 3-state machine (CLOSED → OPEN → HALF_OPEN). After 5 consecutive Ollama failures, all LLM calls are blocked immediately (no 300s timeout wait). After 120s cooldown, one probe call is allowed. Prevents thundering herd during Ollama outages. Configurable via `OLLAMA_CIRCUIT_BREAKER_THRESHOLD` and `OLLAMA_CIRCUIT_BREAKER_COOLDOWN_S`.

**Connects to:**

- `postgres` — reads content for RAG, writes completed reports
- `redis` — receives jobs from ARQ queue + circuit breaker state
- `ollama` — LLM inference (the only container that does heavy Ollama work)

---

### Vision Service (`vision`)

**What it does:** Accepts image/video uploads via `/analyse` endpoint. Computes SHA-256 content hash, stores media to disk, and returns storage path to the API gateway.

**Why it's needed:** Separates file handling (storage, hashing) from ML inference (which runs in the worker). The API gateway forwards uploads here, receives a content_hash and storage_path, then dispatches the ML job to the vision-worker via ARQ.

**Key details:**

- FastAPI app on port 8003
- Stores media at `/app/media/uploads/YYYY/MM/DD/{content_hash}.{ext}`
- No ML models loaded — lightweight file-handling service
- Memory limit: 512 MB

**Connects to:**

- `api` — receives file uploads (HTTP POST)
- Shared `vision_media` volume — writes media files for the worker to read

---

### Vision Worker (`vision-worker`)

**What it does:** ARQ-based ML inference worker that runs the full vision analysis pipeline on uploaded images and videos.

**Registered ARQ job:**

`run_vision_analysis(media_asset_id)` — the 6-step pipeline:

1. **Load bytes** — read image/video from shared media volume
2. **EXIF + pHash** (images only) — extract GPS/device metadata, compute 64-bit perceptual hash for reverse image search
3. **YOLO object detection** (images only) — YOLOv8 (nano on CPU, xlarge on GPU). Detects 80 COCO classes, tags high-interest labels (person, weapon, vehicle, aircraft) to `content_items.labels`
4. **Deepfake detection** — routing based on face presence:
   - Face detected (OpenCV Haar cascade) → **FacetorchDetector** (`prithivMLmods/Deep-Fake-Detector-v2-Model`, ViT-base, ~92% accuracy)
   - No face → **EfficientNetDetector** (`umm-maybe/AI-image-detector`, Swin-base, CIFAKE-trained)
   - Video → extract keyframes every 5s via ffmpeg → EfficientNet on each frame → worst-case (max) score
   - GPU upgrade: `VISION_DEEPFAKE_VIDEO_MODEL=dire` for DIRE diffusion-based detection (~94% accuracy, RTX 3080+ required)
   - All scores are **float 0.0–1.0, never bool** (CLAUDE.md rule 7)
5. **CLIP classification** (images only, if topic has `clip_categories`) — zero-shot image classification against analyst-defined categories (e.g., "military vehicle", "fighter aircraft", "tank")
6. **Persist results** — upsert `vision_results` (JSONB for detections/labels, float for scores)

**Model architecture:**

```
                      ┌──────────────┐
                      │  Image bytes │
                      └──────┬───────┘
                             │
                      ┌──────▼───────┐
                      │  Has faces?  │  OpenCV Haar cascade
                      └──┬───────┬───┘
                    Yes  │       │  No
                   ┌─────▼────┐  │
                   │Facetorch │  │  ┌───────────────┐
                   │ViT-base  │  └──▶ EfficientNet  │
                   │ONNX 327MB│     │ Swin-base     │
                   │FAKE_IDX=1│     │ ONNX 337MB    │
                   └─────┬────┘     │ FAKE_IDX=0    │
                         │          └───────┬───────┘
                         │                  │
                         └────────┬─────────┘
                                  │
                           float 0.0–1.0
                           (deepfake_score)
```

**Model sources (HuggingFace → ONNX):**

| Slot | Model | Architecture | Output | FAKE_INDEX | License |
|------|-------|-------------|--------|------------|---------|
| Face deepfake | `prithivMLmods/Deep-Fake-Detector-v2-Model` | ViT-base-patch16-224 | [1,2] logits | 1 (`{0:"Realism", 1:"Deepfake"}`) | Apache 2.0 |
| Non-face deepfake | `umm-maybe/AI-image-detector` | Swin-base (1024 hidden) | [1,2] logits | 0 (`{0:"artificial", 1:"human"}`) | CC-BY-4.0 |
| GPU upgrade | DIRE (`ZhendongWang6/DIRE`) | ADM diffusion | float | — | MIT |

**Critical design note — label ordering:** Different HuggingFace models use different `id2label` mappings. The `FAKE_INDEX` constant in each detector is verified against the model's `config.json`. Getting this wrong inverts predictions silently (scores look valid but mean the opposite).

**Model download:** The `vision-init` container runs `python -m anveshak.vision.download_models` on first startup, which uses `optimum[onnxruntime]` to download HF models and export to ONNX. Models are stored in the `vision_models` Docker volume. Idempotent — skips if files exist.

**Key details:**

- Memory limit: 6 GB (YOLO + CLIP + 2 deepfake ONNX models, ~2.1 GB total)
- Models lazy-loaded as module-level singletons (reused across ARQ jobs)
- All model names and device settings from env vars — zero code change for hardware upgrade
- Env vars: `VISION_DEVICE`, `YOLO_MODEL_SIZE`, `VISION_DEEPFAKE_IMAGE_MODEL`, `VISION_DEEPFAKE_VIDEO_MODEL`, `CLIP_MODEL_NAME`, `FACETORCH_HF_MODEL`, `EFFICIENTNET_HF_MODEL`

**Connects to:**

- `postgres` — reads media assets + topic CLIP categories, writes vision results
- `redis` — receives jobs from `arq:vision` queue
- Shared `vision_models` volume — pre-downloaded ML models
- Shared `vision_media` volume — reads uploaded media files

---

## Frontend

### Analyst Workbench (`frontend`)

**What it does:** React single-page application that provides the analyst's working interface — topic management, content browsing, signal inbox, report viewer, map visualization, and source credibility management.

**Why it's needed:** Analysts need a visual interface to monitor topics, review signals, read reports, and manage sources. The workbench is designed for intelligence officers who may not be technical users.

**Key details:**

- React + TypeScript + Vite (build) + Tailwind CSS
- MapLibre GL for geographic visualization (GeoJSON from reports)
- WebSocket connection for real-time signal notifications
- JWT authentication with expiry countdown and warning dialog
- Export buttons (CSV/JSON) on ContentFeed, wired to backend `/api/v1/export/*` endpoints via reusable `ExportButton` component
- Built into a static bundle, served by Nginx inside the container
- Depends on `api` being healthy before starting

**Connects to:**

- `api` — REST API + WebSocket (the only backend it talks to)

---

## Observability Stack

### Prometheus (`prometheus`)

**What it does:** Scrapes metrics from all services every 15 seconds and stores time-series data. Evaluates alerting rules.

**Why it's needed:** Without metrics, you can't know if the system is healthy. Prometheus collects request rates, latencies, job success/failure counts, queue depths, and ML inference times from every service.

**Scrape targets:** api (8000), scraper (8001), social (8002), vision (8003), analyst-scheduler (8007), reporter (8005), reporter-worker (8006), ollama (11434), postgres-exporter (9187), redis-exporter (9121), loki (3100)

**Alerting rules (13 rules):**

- `AnveshakServiceDown` — any service unreachable for 1+ min
- `ScraperIngestionStopped` — zero items fetched in 10 min
- `ReportGenerationSlow` — p95 latency > 270s
- `ArqJobFailureSpike` — job failures > 5/min for 5 min
- `NlpLatencyHigh` — analyst NLP p95 > 10s
- `DeepfakeVolumeSpike` — > 50 high-confidence detections in 1 hour
- `SignalEngineSilent` — no signals in 30 min while content is being ingested
- And more (credibility loop, Loki ingestion, Ollama model status)

**Alert delivery:** Alerts are routed to **Alertmanager** (`prom/alertmanager:latest`, port 9093) which delivers via webhook to the API's alert endpoint. Suitable for air-gap sovereign deployment — no email/Slack cloud dependency required. Config: `infra/configs/alertmanager/alertmanager.yml`.

**Connects to:**

- All services — scrapes `/metrics` endpoints
- `alertmanager` — routes fired alerts for delivery
- `grafana` — serves as primary data source

---

### Grafana (`grafana`)

**What it does:** Provides 8 pre-configured dashboards for visual monitoring.

**Dashboards:**

1. **Overview** — system-wide health at a glance
2. **Pipeline** — end-to-end content flow metrics
3. **Ingestion** — scraper throughput, source health, RSS stats
4. **Vision** — deepfake detection rates, YOLO inference times
5. **Credibility** — M1 source scoring, audit log activity
6. **Signals** — signal fire rates, delivery latency, acknowledgment rates
7. **Reporter** — LLM generation times, RAG quality, PDF exports
8. **Infrastructure** — PostgreSQL connections, Redis memory, Ollama model status

**Connects to:**

- `prometheus` — time-series queries
- `loki` — log queries (live tail, search)

---

### Loki + Promtail (`loki`, `promtail`)

**What it does:** Centralized log aggregation. Promtail reads container logs from the Docker socket, parses structlog JSON, and ships to Loki. Loki indexes and stores logs with 7-day retention.

**Why it's needed:** With 17 containers, checking `docker logs` on each one is impractical. Loki provides searchable, correlated logs across all services via Grafana.

**Key details:**

- Promtail extracts low-cardinality labels: `service`, `level`, `container`
- High-cardinality fields (content_hash, URL) stay in the log body (not indexed)
- DEBUG logs are dropped in production
- TSDB index (schema v13) for best single-node performance
- Write-ahead log enabled for crash recovery

**Connects to:**

- `promtail` → reads Docker socket (read-only) → ships to `loki`
- `grafana` → queries `loki` for log panels

---

### Postgres Exporter + Redis Exporter

**What they do:** Lightweight sidecars that expose PostgreSQL and Redis internal metrics in Prometheus format.

**Why they're needed:** Prometheus can't scrape PostgreSQL/Redis natively. These exporters translate internal database stats (connection count, query duration, replication lag, memory usage, key count, etc.) into `/metrics` endpoints.

**Connects to:**

- `postgres-exporter` → `postgres` (SQL stats queries) → scraped by `prometheus`
- `redis-exporter` → `redis` (INFO command) → scraped by `prometheus`

---

### Jaeger (`jaeger`) — Optional

**What it does:** Distributed tracing. When enabled, services emit OpenTelemetry trace spans showing the full request lifecycle across service boundaries.

**Why it's needed:** When debugging slow requests or failures, traces show exactly which service/function took how long. Optional because it adds overhead and is primarily useful during development or incident investigation.

**Key details:**

- Only starts with `docker compose --profile tracing up`
- Services opt-in via `OTEL_ENABLED=true` environment variable
- OTLP HTTP receiver on port 4318, UI on port 16686
- Graceful degradation: if Jaeger is down or tracing disabled, services work normally

---

## Inter-Service Communication

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Communication Patterns                          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  frontend ──HTTP/WS──► api                                          │
│                                                                      │
│  api ──asyncpg──► postgres        (connection pool, direct SQL)     │
│  api ──aioredis──► redis          (ARQ job dispatch)                │
│  api ──HTTP──► ollama             (pre-warm only)                   │
│  api ──HTTP──► reporter           (report download proxy)           │
│                                                                      │
│  scraper ──asyncpg──► postgres    (read topics/sources)             │
│  scraper ──aioredis──► redis      (enqueue scrape jobs)             │
│                                                                      │
│  scraper-worker ──asyncpg──► postgres  (write content items)        │
│  scraper-worker ──aioredis──► redis    (receive/ack jobs)           │
│  scraper-worker ──HTTP──► internet     (fetch source URLs)          │
│                                                                      │
│  social ──asyncpg──► postgres     (read topics, write content)      │
│  social ──aioredis──► redis       (job coordination)                │
│  social ──HTTP/WS──► external APIs (Telegram, Reddit, etc.)        │
│                                                                      │
│  analyst ──asyncpg──► postgres    (read content, write NLP results) │
│  analyst ──aioredis──► redis      (ARQ coordination)                │
│  analyst ──HTTP──► ollama         (cluster label generation)        │
│                                                                      │
│  reporter ──asyncpg──► postgres   (report CRUD)                     │
│  reporter ──aioredis──► redis     (enqueue report jobs)             │
│                                                                      │
│  reporter-worker ──asyncpg──► postgres  (RAG + report writes)       │
│  reporter-worker ──aioredis──► redis    (receive/ack jobs)          │
│  reporter-worker ──HTTP──► ollama       (LLM inference)             │
│                                                                      │
│  All services ──HTTP──► prometheus      (metrics scraping)          │
│  All containers ──logs──► promtail ──► loki                        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Key design decisions:**

- **No service-to-service HTTP calls** (except api→reporter for PDF proxy). Services communicate through the database and Redis queue. This eliminates tight coupling and allows any service to restart independently.
- **All LLM calls go through ARQ.** The API never calls Ollama directly. This prevents slow LLM inference from blocking HTTP requests.
- **WebSocket is API-only.** The analyst service writes signals to the database. The API's background loop picks them up and pushes to connected clients. The analyst never talks to the frontend.

---

## Data Flow — End to End

Here's what happens from the moment an analyst creates a topic to when they receive a signal and read a report:

```
Step 1: Analyst creates topic
  frontend → POST /api/v1/topics → api → INSERT into topics
  Keywords: ["J-20", "stealth fighter"], signal_threshold: 3

Step 2: Scraper picks up topic (within 30 seconds)
  scraper reads active topics from postgres
  → enqueues scrape_topic job to Redis
  scraper-worker picks up job
  → fetches all active web sources matching topic
  → extracts clean text via Crawl4AI / trafilatura
  → computes SHA-256 content_hash
  → INSERT INTO content_items ... ON CONFLICT(content_hash) DO NOTHING
  → extracts media URLs → INSERT INTO media_assets

Step 3: Social adapters collect in parallel
  social reads active topics from postgres
  → polls Telegram channels, Reddit subreddits, etc.
  → same INSERT path with content_hash deduplication

Step 4: Analyst service processes content (within 30 seconds)
  analyst NLP loop picks up items where embedding IS NULL
  → langdetect → spaCy NLP (NER extracts: "J-20" → PRODUCT, "PLAAF" → ORG)
  → NLLB translation (Chinese → English if needed)
  → sentence-transformers → 384-dim embedding stored in pgvector
  → VADER sentiment → YAKE keywords → stored in labels JSONB
  → INSERT INTO extracted_entities

Step 5: Clustering (every 5 minutes)
  analyst clustering loop runs Leiden community detection on blended similarity graph
  → groups related content into narrative_clusters
  → counts independent_source_count (distinct platforms per cluster)
  → generates human-readable label via Ollama

Step 6: Signal fires
  analyst signal loop checks:
    cluster.independent_source_count >= topic.signal_threshold?
  If YES → INSERT INTO signals (type, severity, description)

Step 7: Signal delivered to analyst (within ~10 seconds)
  api signal_delivery loop polls: SELECT * FROM signals WHERE delivered_at IS NULL
  → pushes via WebSocket to connected analyst sessions
  → fires webhook if configured
  → UPDATE signals SET delivered_at = NOW()

Step 8: Analyst requests report
  frontend → POST /api/v1/reports → api → reporter
  → reporter creates report stub (generated_at = NULL)
  → enqueues generate_report ARQ job
  → returns report_id immediately

Step 9: Report generation (30-300 seconds)
  reporter-worker picks up job
  → pgvector cosine search: top-k content chunks for topic
  → enriches chunks with credibility scores and dates
  → renders prompt with few-shot example + grounding rules
  → Ollama qwen2:7b generates structured report
  → Pydantic validates LLM output
  → geocoding: extracts locations → GeoJSON
  → generates PDF
  → UPDATE reports SET content_md=..., generated_at=NOW(), source_snapshot=...
  → Report is now IMMUTABLE

Step 10: Analyst reads report
  frontend polls GET /api/v1/reports/{id}
  → once generated_at is set, displays report
  → map shows GeoJSON locations
  → PDF download available
```

---

## Database Schema

18 tables, all following conventions: `snake_case` names, `created_at`/`updated_at` timestamps, `labels JSONB` field (never Optional).

### Entity Relationship Overview

```
topics ─────────────┬───────────── narrative_clusters
  │                 │                    │
  │            topic_content_items       │ label_generated_at
  │                 │                    │ label_item_hash
  │                 │                    │ archived_at
  └── sources ──── content_items ────────┘
        │              │       │
        │         extracted    near_duplicates
        │         _entities    (a_id ↔ b_id, sim_score)
        │              │
   credibility    media_assets
   _audit_log         │
                 vision_results

  signals ── (references topic + cluster)
    ├── signal_type: multi_source_convergence
    └── signal_type: cross_topic_convergence   ← NEW
  reports ── (references topic, immutable once generated)
  report_source_warnings ── (links report ↔ source degradation)
  analysis_jobs ── (ARQ job tracking)
  users ── (JWT authentication, RBAC roles: admin/analyst/viewer)
    └── CHECK (role IN ('admin', 'analyst', 'viewer'))
  token_blocklist ── (revoked JWT IDs, Redis-backed with DB fallback)
  audit_trail ── (who did what when — 14 audited actions)
  failed_jobs ── (dead-letter queue for failed ARQ jobs)
```

### Table Details

| Table | Rows (typical) | Purpose |
|-------|----------------|---------|
| `users` | ~10 | Analyst accounts (username + bcrypt hash) |
| `topics` | ~20 | Monitored subjects (keywords, thresholds, languages) |
| `sources` | ~100 | OSINT sources (URLs, platforms, credibility scores, health) |
| `content_items` | ~100K+ | Scraped/collected text with embeddings (SHA-256 deduplicated) |
| `extracted_entities` | ~500K+ | NER results (PERSON, ORG, GPE, DATE) linked to content |
| `narrative_clusters` | ~1K | Leiden clusters with centroids, source diversity, archival status, label tracking |
| `near_duplicates` | ~5K | Semantically equivalent content pairs (cosine ≥0.95, canonical a<b ordering) |
| `signals` | ~500 | Threshold-based alerts including cross-topic convergence (new → acknowledged → dismissed) |
| `reports` | ~200 | LLM-generated intelligence reports (immutable after generation) |
| `media_assets` | ~50K | Images/videos with pHash for reverse lookup |
| `vision_results` | ~50K | YOLO detections, deepfake scores, CLIP labels |
| `credibility_audit_log` | ~1K | Immutable log of every credibility score change |
| `report_source_warnings` | ~50 | Post-generation credibility downgrade alerts |
| `topic_content_items` | ~100K | Many-to-many join (content can appear in multiple topics via backfill) |
| `analysis_jobs` | ~10K | ARQ job tracking (status, payload, result, error) |
| `token_blocklist` | ~100 | Revoked JWT IDs (jti) with TTL — logout support |
| `audit_trail` | ~10K+ | User action log: who, what, when, IP address, details JSONB |
| `failed_jobs` | ~100 | Dead-letter queue for ARQ jobs that fail after max retries |

---

## Vector Similarity Pipeline

The vector similarity pipeline is the intelligence backbone of Anveshak. It transforms raw text into embeddings, groups them into narrative clusters, detects duplicates, fires signals, and discovers cross-topic connections. Six interconnected subsystems work together.

### Architecture Overview

```
Content Items (raw text)
    │
    ▼
┌──────────────────┐     ┌──────────────────────┐
│  Embedding        │     │  Content Dedup        │
│  all-MiniLM-L6-v2 │     │  SHA-256 content_hash │
│  384-dim, L2-norm │     │  ON CONFLICT DO NOTH. │
└────────┬─────────┘     └──────────────────────┘
         │
    ┌────▼────────────────────┐
    │  pgvector (HNSW index)  │  ← Migration 003
    │  cosine distance <=>    │
    └────┬───────────┬────────┘
         │           │
    ┌────▼────┐ ┌────▼──────────────┐
    │ Backfill│ │ Near-Duplicate    │  ← Migration 002
    │ (1→many)│ │ Detection         │
    │ cosine  │ │ pairwise cosine   │
    │ ≥0.85   │ │ ≥0.95 threshold   │
    └─────────┘ └────┬──────────────┘
                     │
              ┌──────▼──────────────────┐
              │  Leiden Clustering      │
              │  per topic, windowed    │  ← Migration 004
              │  ISC excludes near-dups │
              │  centroids stored       │
              └──────┬──────────────────┘
                     │
         ┌───────────┼───────────────┐
         │           │               │
    ┌────▼────┐ ┌────▼────┐    ┌────▼──────────────┐
    │ Signal  │ │ Label   │    │ Cross-Topic       │
    │ Engine  │ │Staleness│    │ Convergence       │  ← Migration 006
    │ ISC ≥   │ │ hash    │    │ centroid cosine   │
    │threshold│ │ compare │    │ across topics     │
    └─────────┘ └─────────┘    └───────────────────┘
```

### 1. Near-Duplicate Detection (Semantic Dedup)

**Problem solved:** Two news articles paraphrasing the same event from different platforms both count toward `independent_source_count`. This inflates ISC and triggers false signals — a credibility failure for court-admissible output.

**How it works:**

- Before each clustering cycle, the analyst loads all embeddings for a topic
- Pairwise cosine similarity is computed via numpy dot product (O(N²), bounded by `near_duplicate_batch_size=200`)
- Pairs with cosine similarity ≥ `near_duplicate_similarity_threshold` (default 0.95) are stored in the `near_duplicates` table
- Canonical ordering constraint: `content_item_a_id < content_item_b_id` prevents duplicate pairs
- During clustering, the "b" side of each pair is excluded from `independent_source_count`
- `item_count` remains the total (for transparency), but ISC reflects only genuinely independent sources

**Why 0.95 threshold:** On all-MiniLM-L6-v2, cosine similarity ≥ 0.95 captures only near-paraphrases (same facts, different wording). Lower thresholds would conflate related-but-different articles.

**Key files:**

- `services/analyst/anveshak/analyst/dedup.py` — detection and upsert logic
- `services/api/migrations/versions/002_near_duplicates.py` — schema
- `services/analyst/anveshak/analyst/clustering.py` — ISC filtering in `upsert_cluster()`

**Configuration:** `NEAR_DUPLICATE_SIMILARITY_THRESHOLD` (0.95), `NEAR_DUPLICATE_BATCH_SIZE` (200)

---

### 2. HNSW Vector Index

**Problem solved:** The original IVFFlat index (`lists=100`) is tuned for ~10K vectors. As the corpus grows, recall degrades because IVFFlat requires pre-training on the data distribution. Queries slow down and miss relevant results.

**How it works:**

- Migration 003 replaces IVFFlat with HNSW (Hierarchical Navigable Small World)
- HNSW builds a multi-layered graph connecting similar vectors
- No training phase — self-tuning regardless of corpus size
- Same `<=>` cosine distance operator — zero application code changes

**Parameters:** `m=16` (connections per layer), `ef_construction=64` (build-time search width). Production upgrade: `m=32`, `ef_construction=128` for higher recall at scale.

**Performance:** ~50ms queries at 1M vectors (vs 8s with IVFFlat). Build time <60s for <100K vectors.

**Key files:**

- `services/api/migrations/versions/003_hnsw_index.py` — migration
- `hardware.md` — upgrade parameters

**Configuration:** `HNSW_M` (16), `HNSW_EF_CONSTRUCTION` (64)

---

### 3. Temporal Windowing for Clustering

**Problem solved:** The clustering algorithm treats a 6-month-old article identically to one from 10 minutes ago. For a real-time monitoring platform, fresh narratives drown in historical noise. An analyst watching for emerging threats doesn't want last year's articles dominating cluster composition.

**How it works:**

- `load_embeddings()` accepts a `window_days` parameter (default: `clustering_window_days=30`)
- Only content items with `captured_at` within the window are loaded for clustering
- Clusters older than `cluster_archive_after_days` (default: 90) are marked with `archived_at` timestamp
- Archived clusters are excluded from the signal engine — they won't trigger new signals
- The temporal filter uses `MAKE_INTERVAL(days => $2)` in PostgreSQL for timezone-safe comparison

**Key files:**

- `services/api/migrations/versions/004_cluster_temporal.py` — adds `archived_at` column
- `services/analyst/anveshak/analyst/clustering.py` — windowed SQL, `load_embeddings()` signature
- `services/analyst/anveshak/analyst/signal_engine.py` — `AND nc.archived_at IS NULL` filter
- `services/analyst/anveshak/analyst/main.py` — archival SQL in `cluster_loop()`

**Configuration:** `CLUSTERING_WINDOW_DAYS` (30), `CLUSTER_ARCHIVE_AFTER_DAYS` (90)

---

### 4. Continuous Backfill

**Problem solved:** Backfill originally ran only once — when a topic was created. Any content scraped later for a different topic, even if it matched the original topic's keywords, was never discovered. Topics became isolated silos.

**How it works:**

- A dedicated `backfill_loop` runs every `backfill_interval_s` seconds (default: 600 = 10 minutes)
- For each active topic, encodes topic keywords as a vector, runs pgvector cosine search across the entire corpus
- Items with similarity ≥ `backfill_similarity_threshold` (0.85) are linked via the `topic_content_items` join table
- Fully idempotent: `ON CONFLICT (topic_id, content_item_id) DO NOTHING` — safe to re-run indefinitely
- Runs as a separate async loop, independent of the clustering cycle

**Key files:**

- `services/analyst/anveshak/analyst/main.py` — `backfill_loop()` function
- `services/analyst/anveshak/analyst/backfill.py` — core logic (unchanged, already idempotent)

**Configuration:** `BACKFILL_INTERVAL_S` (600, 0 = disabled), `BACKFILL_SIMILARITY_THRESHOLD` (0.85)

---

### 5. Label Staleness Detection

**Problem solved:** Clustering re-runs every 5 minutes. Cluster composition may shift significantly — items join, leave, or swap clusters. But the Ollama-generated cluster label persists and may no longer describe what the cluster actually contains. An analyst sees "Chinese Military Exercises" on a cluster that is now about "South China Sea Shipping Lanes".

**How it works:**

- When a label is generated, `compute_item_hash()` creates a SHA-256 hash of the sorted, comma-joined content_item IDs in the cluster
- This hash and `label_generated_at` are stored on the `narrative_clusters` row
- On each clustering cycle, before enqueuing label generation, `check_label_staleness()` compares the stored hash against the current composition
- If the hash differs (any item added/removed/swapped), the label is re-enqueued for Ollama regeneration
- New clusters (NULL hash) are always labelled — backward compatible with existing data

**Key files:**

- `services/api/migrations/versions/005_label_staleness.py` — adds `label_generated_at`, `label_item_hash` columns
- `services/analyst/anveshak/analyst/labeller.py` — `compute_item_hash()`, `check_label_staleness()`, updated SQL
- `services/analyst/anveshak/analyst/jobs.py` — staleness check before enqueuing label jobs

**Configuration:** `LABEL_STALENESS_CHANGE_THRESHOLD` (0.30)

---

### 6. Cross-Topic Cluster Convergence

**Problem solved:** An analyst monitoring "Chinese Military" and "South China Sea" topics sees each topic's signals independently. But when both topics surface the same narrative — say, a specific naval exercise — there's no mechanism to alert the analyst that two separate intelligence streams have converged on the same story. This is exactly the kind of cross-correlation that intelligence analysis demands.

**How it works:**

- A dedicated `convergence_loop` runs every `cross_topic_check_interval_s` (default: 900 = 15 minutes)
- Compares cluster centroids across different topics using pgvector cosine distance
- SQL uses `nc1.topic_id < nc2.topic_id` to ensure cross-topic comparison only (canonical ordering)
- When centroid similarity ≥ `cross_topic_similarity_threshold` (0.85), fires a `cross_topic_convergence` signal
- Evidence JSONB contains both cluster IDs, both topic IDs, and the similarity score
- Severity is always HIGH — cross-topic convergence is a significant intelligence finding
- Deduplication: same 24h window as multi-source signals (per cluster_a + signal_type)
- Archived clusters are excluded from comparison

**Signal type:** `cross_topic_convergence` (vs existing `multi_source_convergence`)

**Key files:**

- `services/analyst/anveshak/analyst/convergence.py` — detection and signal firing
- `services/api/migrations/versions/006_cross_topic_signals.py` — partial index on signal_type
- `services/analyst/anveshak/analyst/main.py` — `convergence_loop()` function
- `services/analyst/anveshak/analyst/signal_engine.py` — `_SIGNAL_TYPE_CROSS_TOPIC` constant

**Configuration:** `CROSS_TOPIC_SIMILARITY_THRESHOLD` (0.85), `CROSS_TOPIC_CHECK_INTERVAL_S` (900, 0 = disabled), `CROSS_TOPIC_MAX_PAIRS` (50)

---

### 7. Incremental Clustering (2026-05-06)

**Problem solved:** Re-running clustering from scratch every 5 minutes on ALL items is O(N²) per topic. At 500 items, that's 250,000 distance computations every cycle. At 5,000 items it becomes 25 million — unsustainable for 1000+ topics.

**How it works:**

```
Every 5 min per topic:
  1. Load ONLY unclustered items (narrative_cluster_id IS NULL)
  2. Load existing cluster centroids
  3. For each new item:
     - Cosine similarity to each centroid
     - If sim ≥ 0.75 → assign to that cluster, update centroid + ISC
     - Else → add to unassigned buffer
  4. If buffer ≥ min_cluster_size → Leiden on buffer only → new clusters
  5. No existing clusters? → full Leiden on all unclustered (fresh topic)
```

**Performance:**

| Scale | Old (O(N²)) | Incremental (O(new × clusters)) |
|-------|-------------|--------------------------------|
| 500 items, 5 new | 250,000 ops | 50 ops |
| 5,000 items, 50 new | 25,000,000 ops | 1,000 ops |

**Signal stability:** Cluster IDs are preserved across cycles. New items are assigned TO existing clusters, not into newly created ones. Signals pointing to a cluster_id remain valid — no orphaning.

**Adaptive min_cluster_size:** Scales with item count — `max(2, min(default, N//5))`. Topics with <50 items use min_size=2; larger topics use the production default of 3.

**Key files:**

- `services/analyst/anveshak/analyst/clustering.py` — `assign_to_nearest_cluster()`, `update_cluster_with_assignments()`, modified `run_clustering()`

**Configuration:** `CLUSTER_ASSIGN_THRESHOLD` (0.75)

---

### 8. Entity MinHash Clustering Boost (2026-05-06)

**Problem solved:** A dark web post about "AIIMS data dump" and a CERT-In advisory about "AIIMS cyber incident" embed far apart (different vocabulary, different tone) but share the SAME entities: "AIIMS", "Delhi", "ransomware". Pure embedding distance fails to cluster them.

**How it works:**

At **ingestion time** (analyse_content job):
```
Article → NER → entities: {"AIIMS", "Delhi", "ransomware"}
                    ↓
              MinHash signature (128 integers, datasketch library)
                    ↓
              Stored in content_items.entity_minhash (BIGINT[])
```

At **clustering time** (every 5 min):
```
1. Build cosine similarity matrix (N×N) — embedding similarity
2. Build MinHash similarity matrix (N×N) — entity overlap (Jaccard estimate)
3. Blend: similarity = 0.7 × cosine_sim + 0.3 × entity_sim
4. Build similarity graph: edge if blended_sim >= 0.75
5. Run Leiden community detection on the graph
```

**NULL-safe blending:** Items without entity_minhash (no entities extracted, or pre-migration content) fall back to cosine-only distance. No penalty applied.

**Why MinHash, not raw Jaccard:** MinHash precomputes a 128-integer fingerprint once at ingestion. At clustering time, comparing two fingerprints is 128 integer comparisons (~100ns). Raw Jaccard requires full set intersection per pair — slower at scale.

**Performance:** 500 items × 128 permutations = ~3ms for the entity similarity matrix. Negligible compared to graph construction and Leiden itself.

**Key files:**

- `services/analyst/anveshak/analyst/entity_minhash.py` — `compute_entity_minhash()`, `minhash_similarity_matrix()`
- `services/analyst/anveshak/analyst/jobs.py` — computes and stores MinHash after NER
- `services/analyst/anveshak/analyst/clustering.py` — blends entity similarity into distance matrix
- `services/api/migrations/versions/010_entity_minhash.py` — adds `entity_minhash BIGINT[]` column

**Configuration:** `ENTITY_BLEND_WEIGHT` (0.3 — 0=embedding only, 1=entity only), `MINHASH_NUM_PERM` (128)

---

### 9. Accuracy Benchmark Framework (2026-05-06)

**Problem solved:** No way to measure Anveshak's detection accuracy against known events. MoD decision makers need proof the system works.

**How it works:**

- 100 real OSINT event definitions (YAML) with 858 fixture articles (JSON)
- Events span 5 categories: cross-border, info ops, deepfake, protest, critical infra
- 10 negative events (satire, recycled, commentary) measure false positive rate
- 6 languages: English, Hindi, Chinese, Urdu, Arabic, Russian
- Automated pipeline: inject → embed → cluster → signal → measure → report

**Results (v3.0):**

| Metric | Score |
|--------|-------|
| Precision | 90.7% |
| Recall | 43.3% |
| F1 | 58.6% |

**Key files:**

- `benchmark/` — complete framework (run.py, inject.py, metrics.py, report.py)
- `benchmark/corpus/events/` — 100 event YAML definitions
- `benchmark/corpus/fixtures/` — 858 article JSON files
- `docs/accuracy_benchmark.md` — full report with per-category/language breakdown

**Usage:** `make benchmark` (full run), `make benchmark-clean` (remove benchmark data)

---

### Cross-Dependencies Between Subsystems

These six improvements are not independent features — they form a reinforcing chain:

```
Near-Duplicate Detection ──► prevents false ISC inflation
         │
         ▼
Incremental Clustering ──► assigns new items to existing centroids
         │                   preserves cluster IDs (no orphaned signals)
         │                   falls back to Leiden for unassigned
         │
         ├──► Entity MinHash Boost ──► blends entity overlap into distance
         │                              dark web + CERT-In advisory cluster together
         │
         ├──► Adaptive min_cluster_size ──► small topics (N<50) use min_size=2
         │
         ├──► Signal Engine ──► fires on accurate ISC
         │                       excludes archived clusters
         │
         ├──► Label Staleness ──► detects composition drift
         │                         re-labels when needed
         │
         └──► Cross-Topic Convergence ──► compares centroids
                                           fires HIGH signals

Continuous Backfill ──► feeds content into multiple topics
                         enables cross-topic convergence

HNSW Index ──► accelerates all pgvector queries
               backfill, vector search, centroid comparison

Benchmark Framework ──► validates accuracy against 100 known events
                         reproducible via `make benchmark`
```

**Critical path for court-admissible output:**
`Content → Dedup → Accurate ISC → Accurate Signals → Trustworthy Reports`

Without near-duplicate detection, a single-source story paraphrased across 3 platforms would appear as "confirmed by 3 independent sources" in a generated report — a factual error in what is intended to be court-admissible evidence.

---

### Database Migrations (002–006)

| Migration | Table/Index | Change |
|-----------|------------|--------|
| 002 | `near_duplicates` | New table: semantic duplicate pairs with CHECK constraint (a < b) |
| 003 | `idx_content_items_embedding` | Replace IVFFlat with HNSW (m=16, ef_construction=64) |
| 004 | `narrative_clusters.archived_at` | New column for temporal cluster archival |
| 005 | `narrative_clusters.label_generated_at`, `label_item_hash` | New columns for label staleness tracking |
| 006 | `idx_signals_cross_topic` | Partial index for `cross_topic_convergence` signal type |
| 010 | `content_items.entity_minhash` | BIGINT[] column for MinHash fingerprint (128 permutations) |

**Production hardening migrations (Phase 1-2 audit, 2026-05-10):**

| Migration | Table/Index | Change |
|-----------|------------|--------|
| 004 | `token_blocklist`, `users.role` | Token revocation table + CHECK constraint (admin/analyst/viewer) |
| 005 | `audit_trail`, `failed_jobs` | User action audit log + dead-letter queue for failed ARQ jobs |

All migrations are additive — no columns dropped, no data modified, backward compatible with existing deployments.

---

## Signal Engine

Signals are Anveshak's real-time alerting mechanism. They fire when enough independent sources corroborate a narrative cluster.

**How it works:**

1. Content items are clustered by semantic similarity (Leiden community detection on blended similarity graph)
2. Near-duplicate items are excluded from source counting — prevents paraphrased content from inflating diversity
3. Each cluster tracks `independent_source_count` — the number of distinct `source.platform` values contributing unique content
4. When `independent_source_count >= topic.signal_threshold`, a `multi_source_convergence` signal is created
5. Archived clusters (older than `cluster_archive_after_days`) are excluded from signal checks
6. The API's background loop delivers signals to connected analyst sessions via WebSocket within ~10 seconds
7. Optionally, a webhook POST is fired to a configured URL

**Signal types:**

| Type | Trigger | Severity |
|------|---------|----------|
| `multi_source_convergence` | Cluster ISC ≥ topic threshold | HIGH if ISC ≥ 3, else MEDIUM |
| `cross_topic_convergence` | Two topics share a narrative (centroid similarity ≥ 0.85) | Always HIGH |

**Signal lifecycle:**

```
new → acknowledged → dismissed
                  → escalated
```

**Why independent sources matter:** A single Telegram channel posting the same thing 50 times is noise. But when Telegram, Reddit, and a news website all report the same narrative — that's a signal worth investigating. Near-duplicate detection ensures that paraphrased content from different platforms doesn't falsely inflate this count.

**Why cross-topic convergence matters:** When two independently monitored topics converge on the same narrative, it often indicates a significant real-world event that cuts across intelligence domains.

---

## Report Generation Pipeline

Reports are Anveshak's court-admissible output. They are **immutable** — once generated, they are never modified.

```
                    ┌─────────────────────────┐
                    │  1. RAG Retrieval        │
                    │  pgvector cosine search  │
                    │  top-k content chunks    │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │  2. Context Enrichment   │
                    │  + Source URL            │
                    │  + Credibility score     │
                    │  + Publication date      │
                    │  + Source count & range   │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │  3. Prompt Rendering     │
                    │  Few-shot example        │
                    │  7 grounding rules       │
                    │  Role-based instruction  │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │  4. LLM Inference        │
                    │  Ollama qwen2:7b         │
                    │  Timeout: 540s           │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │  5. Validation           │
                    │  Pydantic model parse    │
                    │  Reject malformed output │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │  6. Geocoding + GeoJSON  │
                    │  Extract locations       │
                    │  Build FeatureCollection │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │  7. PDF Generation       │
                    │  Markdown → HTML → PDF   │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │  8. Storage (immutable)   │
                    │  generated_at set ONCE   │
                    │  source_snapshot frozen   │
                    └──────────────────────────┘
```

**Immutability rules:**

- `generated_at` is set exactly once on first write — never updated
- `source_snapshot` captures source credibility scores at generation time
- If a source is later downgraded, a `report_source_warning` is inserted — the report itself is NOT modified
- To get updated content, the analyst generates a new report

---

## Security Model

- **No cloud LLM:** All inference runs on Ollama (localhost/container). Intelligence data never leaves the deployment boundary.
- **RBAC (3 roles):** `admin` (full access + user management + system endpoints), `analyst` (read + write on topics/sources/signals/reports), `viewer` (read-only). Every route handler enforced via `require_role()` dependency. Role stored in JWT payload and checked on every request.
- **JWT authentication + revocation:** Tokens include `jti` (unique ID) and `role`. `POST /auth/logout` revokes token by storing `jti` in Redis blocklist with TTL matching token expiry. API refuses to start if `JWT_SECRET_KEY` is the insecure default.
- **Audit trail:** Every mutating API operation (14 actions) is logged to `audit_trail` table with user_id, action, resource_type, resource_id, details JSONB, and IP address. Defence/LEA requirement — "who saw what when" is not optional.
- **No hardcoded secrets:** All credentials come from environment variables (`.env` file, never committed).
- **Content hash logging only:** Raw scraped content is never logged — only `content_hash` and URL appear in logs.
- **LLM output validation:** Every LLM response is parsed through a Pydantic model before storage. Raw LLM strings are never trusted.
- **Prompt injection protection:** User input is sanitized and wrapped in boundary markers before inclusion in LLM prompts.
- **X/Twitter spend guard:** Monthly read count checked against `X_MONTHLY_READ_CAP` before every API call.
- **Rate limiting:** 4-tier sliding window — login 10/min, vision 30/min, authenticated 120/min, anonymous 60/min.
- **Security headers:** X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Content-Security-Policy (`default-src 'self'`), Strict-Transport-Security (when `HSTS_ENABLED=true`).
- **CORS hardening:** Explicit method list (no wildcard), configurable origins via `ALLOWED_ORIGINS` env var.
- **Circuit breakers:** Ollama (reporter) and social adapters both have Redis-backed 3-state circuit breakers preventing cascading failures during outages.
- **DB connection resilience:** `create_pool_with_retry()` with exponential backoff prevents permanent failure when Postgres is slow to start.

---

## Hardware Independence

Every hardware-sensitive parameter comes from environment variables. When production hardware is available, update `.env` — zero code changes required.

**Current defaults (CPU, 16 GB laptop):**

| Component | Current (CPU) | GPU Upgrade |
|-----------|---------------|-------------|
| NLP | spaCy `*_core_web_md` models | Same (CPU-bound) |
| LLM | `qwen2:7b` Q4_0 | `qwen2:72b` or larger on GPU |
| Embeddings | `all-MiniLM-L6-v2` (384d) | `e5-large-v2` (1024d) |
| YOLO | nano | xlarge on GPU |
| Deepfake (face) | `prithivMLmods/Deep-Fake-Detector-v2-Model` (ViT, ~92%) | Same model, CUDA provider |
| Deepfake (non-face) | `umm-maybe/AI-image-detector` (Swin, CIFAKE) | DIRE on GPU (~94%) |
| Translation | NLLB-200 distilled 600M | NLLB-200 1.3B on GPU |
| Sentiment | VADER (rule-based, ~1 MB) | No GPU benefit |
| Keywords | YAKE (statistical, pure Python) | No GPU benefit |
| pgvector index | HNSW (m=16, ef=64) | HNSW (m=32, ef=128) on production |

See `hardware.md` for the complete upgrade matrix with memory requirements and expected performance gains.

---

## Validation Suite

Anveshak has a comprehensive validation framework that verifies the system at multiple levels — from unit tests to live pipeline health checks. All validation scripts use stdlib only (no external dependencies), are read-only (never mutate data), and return exit codes (0 = pass, 1 = fail).

### Test Tiers

| Command | Scope | Requires Stack | Tests |
|---------|-------|----------------|-------|
| `make test-unit` | Unit tests | No | 250+ tests, all markers `@pytest.mark.unit` |
| `make test-vector` | Vector pipeline units | No | 44 tests across dedup, temporal, staleness, convergence, backfill |
| `make test-integration` | Integration tests | Yes | Real PostgreSQL + Redis via Docker Compose |
| `make test-vector-integration` | Vector cross-deps | Yes | 5 tests: dedup→clustering→signal→convergence chain |
| `make test-e2e` | End-to-end | Yes + seeded data | Full demo arc with live API calls |

### Validation Suites

| Command | Script | Stages | What It Checks |
|---------|--------|--------|----------------|
| `make validate` | `validate_pipeline.py` | 7 | Infra, auth, corpus, intelligence, reports, sources, multilingual |
| `make validate-vision` | `validate_vision.py` | 10 | Deepfake detection, YOLO, pHash dedup, score ranges |
| `make validate-vision-full` | `validate_vision_full.py` | 6 | 4 deepfake categories (face/no-face × real/AI) + video + CLIP |
| `make validate-vector` | `validate_vector.py` | 8 | Migrations 002–006, HNSW, dedup, temporal, labels, convergence, backfill |
| `make validate-all` | All three | 25 | Complete system health |

### Invariant Checks

| Command | Script | What It Enforces |
|---------|--------|------------------|
| `make verify-labels` | `verify_labels.py` | All Pydantic models have non-Optional `labels` field |
| `make verify-reports` | `verify_reports_immutable.py` | `generated_at` set once, never updated |
| `make syscheck` | `syscheck.py` | System requirements (RAM, disk, Docker, ports, GPU) |
| `make health` | Makefile inline | Quick service health (all 5 services + ollama + frontend) |
| `make demo-check` | `demo_check.py` | 8-step demo readiness for iDEX ADITI review |

### Vector Pipeline Validation (`make validate-vector`)

The vector validation script queries the `/api/v1/system/vector-health` endpoint, which runs 12 read-only SQL queries against the live database:

1. **Migrations** — verifies `near_duplicates` table, `archived_at`/`label_item_hash` columns, HNSW index, convergence index all exist
2. **HNSW Index** — confirms `idx_content_items_embedding` uses `hnsw` (not `ivfflat`) in `pg_indexes`
3. **Near-Duplicate Detection** — checks pair count (WARN if 0 on fresh deploy)
4. **Dedup→ISC Integrity** — confirms near-duplicate pairs exist and ISC filtering is active
5. **Temporal Windowing** — checks for archived clusters (WARN if none)
6. **Label Staleness** — checks clusters with `label_generated_at IS NOT NULL`
7. **Cross-Topic Convergence** — checks index exists, convergence signals fired
8. **Continuous Backfill** — checks `topic_content_items` for backfilled entries

Data-dependent checks use WARN (not FAIL) on fresh deployments where no data has been processed yet.

---

## Deployment

### Development (Docker Compose)

```bash
cp .env.example .env          # Configure secrets and model settings
make up                        # Start all 17 containers
make migrate                   # Run Alembic migrations
make seed-demo                 # Load demo data (optional)
make ps                        # Check container health
```

### Production (k3s)

Single-node Kubernetes deployment using Kustomize. 13 manifests covering all services with production-grade hardening.

```bash
make k3s-deploy                # Apply all manifests to k3s
make k3s-teardown              # Remove namespace
```

Manifests in `infra/k3s/`:

| Manifest | Key Specs |
|----------|-----------|
| `namespace.yml` | `anveshak` namespace |
| `secrets-template.yml` | Manual secret injection via kubectl |
| `postgres.yml` | pgvector:pg16, 20Gi PVC |
| `redis.yml` | redis:7-alpine, 512Mi limit |
| `api.yml` | 512Mi, health probes, PodDisruptionBudget (minAvailable: 1) |
| `analyst.yml` | 6Gi limit (NLP + embedding models) |
| `ollama.yml` | 8Gi limit, 20Gi PVC for model weights |
| `scraper.yml` | 1Gi, shared media PVC |
| `reporter.yml` | 512Mi, Ollama + analyst service URLs |
| `vision.yml` | 4Gi, media + models PVCs |
| `frontend.yml` | 128Mi, readOnlyRootFilesystem |
| `ingress.yml` | Traefik IngressClass, `/api` → api, `/` → frontend |
| `networkpolicy.yml` | Default-deny + 5 allow rules (frontend→api, services→postgres, services→redis, analyst+reporter→ollama, ingress→frontend) |

**Security hardening on all pods:**
- `securityContext.runAsNonRoot: true` + `allowPrivilegeEscalation: false`
- `livenessProbe` on all service pods (catches hung processes, distinct from readinessProbe)
- `readOnlyRootFilesystem` where feasible (api, frontend)
- `POSTGRES_PASSWORD` env var ordered before `POSTGRES_URL` for `$(VAR)` substitution

### Backup / Restore

```bash
make backup                    # pg_dump + Redis RDB + media archive
make restore BACKUP_DIR=...    # Restore from backup directory
```

### Optional Overlays

```bash
# Vision service (YOLO + deepfake + CLIP)
docker compose -f infra/compose.yml -f infra/compose.vision.yml up

# Drishti bridge (one-way entity emit)
docker compose -f infra/compose.yml -f infra/compose.bridge.yml up

# Distributed tracing (Jaeger)
docker compose --profile tracing up
```

---

## Key Invariants

These rules are enforced by code, tests, and CI. They are non-negotiable.

| Rule | How It's Enforced |
|------|-------------------|
| Labels are never Optional | `verify_labels.py` script, unit tests on every Pydantic model |
| Reports are immutable | `generated_at` set once, `WHERE generated_at IS NULL` guard in worker |
| Content is deduplicated | `UNIQUE(content_hash)`, `ON CONFLICT DO NOTHING` on every insert |
| Near-duplicates excluded from ISC | `dedup.py` filters before `count_independent_sources()` in clustering |
| Deepfake scores are float 0.0-1.0 | Type system, never `bool` — analyst decides threshold |
| All LLM calls are async | ARQ jobs only — API routes never call Ollama directly |
| No cloud LLM with real data | Ollama localhost/container only, sovereign requirement |
| Credibility changes are audit-logged | DB transaction wraps UPDATE + INSERT together |
| X/Twitter spend is capped | `X_MONTHLY_READ_CAP` checked before every API call |
| Drishti bridge is one-directional | Emit only, never read from Drishti |
| Hardware config comes from env vars | All model names, device strings, batch sizes in `settings.py` |
| LLM output is Pydantic-validated | Raw LLM strings never stored or displayed |
| Standalone-first | `ANVESHAK_DRISHTI_BRIDGE=false` by default, no external dependencies |
| Cluster labels reflect composition | `label_item_hash` detects drift, triggers Ollama re-label |
| Archived clusters don't fire signals | `AND nc.archived_at IS NULL` in signal engine SQL |
| Cross-topic convergence detected | Centroid comparison across topics, HIGH severity signal |
| RBAC enforced on every route | `require_role()` dependency, 3 roles (admin/analyst/viewer), 403 on violation |
| Token revocation works | `jti` in JWT, Redis blocklist checked on verify, `POST /auth/logout` |
| User actions are audit-logged | 14 mutating actions → `audit_trail` table with user_id, IP, details |
| Failed jobs are preserved | ARQ failures → `failed_jobs` DLQ table, admin-queryable |
| Ollama circuit breaker prevents cascade | 5 failures → OPEN (block), 120s → HALF_OPEN (probe), success → CLOSED |
| Redis AOF prevents job loss | `appendonly yes` + `appendfsync everysec` — no 60s data-loss window |
| K3s pods run as non-root | `securityContext.runAsNonRoot: true` on all app pods |
| K3s network is zero-trust | Default-deny NetworkPolicy + explicit allow rules per service |

---

## Five Modules (PS-18 Scope)

| Module | Service(s) | What It Delivers |
|--------|-----------|------------------|
| **M1** | analyst | Source credibility scoring, auto-feedback loop, immutable audit log |
| **M2** | scraper + analyst | Open-web crawling, NLP, multilingual processing, clustering, backfill |
| **M3** | social | Platform adapters: Telegram, Reddit, Bluesky, X/Twitter |
| **M4** | vision | YOLO object detection, CLIP search, deepfake detection, EXIF, pHash |
| **M5** | reporter | LLM reports (RAG), GIS/GeoJSON output, PDF export, scheduled reports |
| **Cross-cutting** | api + analyst | Signals engine, real-time WebSocket push, webhook notifications |

---

## Docker Volumes

| Volume | Used By | Contains |
|--------|---------|----------|
| `postgres_data` | postgres | Database files |
| `redis_data` | redis | RDB snapshots |
| `ollama_models` | ollama | Downloaded LLM weights (~4.4 GB for qwen2:7b) |
| `analyst_models` | analyst | spaCy, NLLB, sentence-transformer models (~3 GB) |
| `reporter_output` | reporter, reporter-worker | Generated PDFs and report artifacts |
| `vision_models` | vision-init, vision, vision-worker | YOLO, CLIP, deepfake ONNX models (~700 MB) |
| `vision_media` | vision, vision-worker | Uploaded images and videos for analysis |
| `media_store` | scraper-worker | Downloaded images and videos |
| `prometheus_data` | prometheus | Time-series metrics (15-day retention) |
| `grafana_data` | grafana | Dashboard state, user prefs |
| `loki_data` | loki | Log chunks and TSDB index (7-day retention) |
| `promtail_positions` | promtail | Log scrape offset positions |
