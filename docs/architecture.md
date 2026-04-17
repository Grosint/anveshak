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
11. [Signal Engine](#signal-engine)
12. [Report Generation Pipeline](#report-generation-pipeline)
13. [Security Model](#security-model)
14. [Hardware Independence](#hardware-independence)
15. [Deployment](#deployment)
16. [Key Invariants](#key-invariants)

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
   ┌─────▼──────┐    ┌─────▼──────┐       ┌───────▼────────┐
   │  analyst   │    │  vision    │       │   reporter     │
   │            │    │            │       │   + worker     │
   │ spaCy NLP  │    │ YOLOv8    │       │ RAG + Ollama   │
   │ NLLB trans │    │ deepfake  │       │ PDF export     │
   │ HDBSCAN    │    │ CLIP      │       │ GeoJSON        │
   │ sentiment  │    │ EXIF/pHash│       │ scheduled cron │
   │ YAKE keys  │    └────────────┘       └───────┬────────┘
   │ signals    │                                 │
   └─────┬──────┘                                 │
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
  │  Prometheus → Grafana (8 dashboards)         │
  │  Loki ← Promtail (structured logs)          │
  │  Jaeger (opt-in distributed tracing)         │
  │  postgres-exporter, redis-exporter           │
  └─────────────────────────────────────────────┘

  ┌─────────────┐    (optional, one-way only)
  │   Drishti   │ ←── Anveshak emits entities
  │  Platform   │     via source.envelopes.v1
  └─────────────┘     ANVESHAK_DRISHTI_BRIDGE=true
```

---

## Container Map

Anveshak runs as **17 containers** (+ 1 optional) on a single Docker network (`anveshak-net`). Here is every container, what it does, why it exists, and how it connects to the rest of the system.

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
| `analyst` | anveshak-analyst | 8004 | 6 GB | NLP + clustering + signals |
| `reporter` | anveshak-reporter | 8005 | 512 MB | Report API |
| `reporter-worker` | anveshak-reporter | 8006 | 1 GB | LLM report generator |
| `frontend` | anveshak-frontend | 3000 | 256 MB | Analyst workbench UI |
| `prometheus` | prom/prometheus | 9090 | 512 MB | Metrics collection |
| `grafana` | grafana/grafana | 3001 | 256 MB | Dashboards |
| `loki` | grafana/loki:3.0.0 | 3100 | 512 MB | Log aggregation |
| `promtail` | grafana/promtail:3.0.0 | — | 128 MB | Log shipping |
| `postgres-exporter` | postgres-exporter | 9187 | 64 MB | DB metrics |
| `redis-exporter` | redis_exporter | 9121 | 64 MB | Cache metrics |
| `jaeger` | jaeger-all-in-one | 16686 | 512 MB | Tracing (opt-in) |

**Total baseline memory:** ~21 GB (without vision overlay)

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
- Persistence: RDB snapshot every 60 seconds
- Data persisted to `redis_data` volume

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
- **JWT authentication** — login endpoint issues tokens, all other routes require valid JWT
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
1. CORS (configurable origins)
2. Rate limiting
3. Security headers (X-Content-Type-Options, X-Frame-Options, etc.)

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

### Analyst (`analyst`)

**What it does:** The intelligence processing engine. Runs four concurrent async loops that transform raw content into structured intelligence:

1. **NLP Loop** (every 30s) — picks up content items without embeddings, runs:
   - Language detection
   - spaCy NLP pipeline (NER, POS tagging) — separate models for English, Russian, Chinese
   - NLLB-200 machine translation (non-English → English)
   - Sentence-transformer embedding generation (384 dimensions)
   - VADER sentiment analysis (compound/positive/negative/neutral scores)
   - YAKE keyword extraction (unsupervised, statistical)
   - Results stored in `content_items.embedding`, `content_items.labels`, `extracted_entities`

2. **Clustering Loop** (every 5 min) — runs HDBSCAN clustering on embeddings per topic, creates/updates `narrative_clusters` with item counts and source diversity metrics

3. **Signal Check Loop** — monitors clusters for corroboration threshold: when `independent_source_count >= topic.signal_threshold`, fires a signal (inserts into `signals` table)

4. **Credibility Update Loop** — auto-downgrades source credibility when a source consistently amplifies content flagged as deepfake

**Why it's needed:** This is the core intelligence value-add. Raw scraped text is useless to an analyst — they need entities, clusters, trends, and alerts. The analyst service transforms raw data into actionable intelligence.

**Key details:**
- Memory limit: 6 GB (3 spaCy models + NLLB translation model + embedding model)
- Models cached in `analyst_models` volume
- Cluster labels generated via Ollama (qwen2:7b)
- All NLP model names come from environment variables (hardware independence)

**Connects to:**
- `postgres` — reads content items, writes embeddings/entities/clusters/signals
- `redis` — ARQ job coordination
- `ollama` — cluster label generation

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

**Connects to:**
- `postgres` — reads content for RAG, writes completed reports
- `redis` — receives jobs from ARQ queue
- `ollama` — LLM inference (the only container that does heavy Ollama work)

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
- Built into a static bundle, served by Nginx inside the container
- Depends on `api` being healthy before starting

**Connects to:**
- `api` — REST API + WebSocket (the only backend it talks to)

---

## Observability Stack

### Prometheus (`prometheus`)

**What it does:** Scrapes metrics from all services every 15 seconds and stores time-series data. Evaluates alerting rules.

**Why it's needed:** Without metrics, you can't know if the system is healthy. Prometheus collects request rates, latencies, job success/failure counts, queue depths, and ML inference times from every service.

**Scrape targets:** api (8000), scraper (8001), social (8002), vision (8003), analyst (8004), reporter (8005), reporter-worker (8006), ollama (11434), postgres-exporter (9187), redis-exporter (9121), loki (3100)

**Alerting rules (13 rules):**
- `AnveshakServiceDown` — any service unreachable for 1+ min
- `ScraperIngestionStopped` — zero items fetched in 10 min
- `ReportGenerationSlow` — p95 latency > 270s
- `ArqJobFailureSpike` — job failures > 5/min for 5 min
- `NlpLatencyHigh` — analyst NLP p95 > 10s
- `DeepfakeVolumeSpike` — > 50 high-confidence detections in 1 hour
- `SignalEngineSilent` — no signals in 30 min while content is being ingested
- And more (credibility loop, Loki ingestion, Ollama model status)

**Connects to:**
- All services — scrapes `/metrics` endpoints
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
  analyst clustering loop runs HDBSCAN on topic embeddings
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

12 core tables, all following conventions: `snake_case` names, `created_at`/`updated_at` timestamps, `labels JSONB` field (never Optional).

### Entity Relationship Overview

```
topics ─────────────┬───────────── narrative_clusters
  │                 │                    │
  │            topic_content_items       │
  │                 │                    │
  └── sources ──── content_items ────────┘
        │              │
        │         extracted_entities
        │              │
   credibility    media_assets
   _audit_log         │
                 vision_results

  signals ── (references topic + cluster)
  reports ── (references topic, immutable once generated)
  report_source_warnings ── (links report ↔ source degradation)
  analysis_jobs ── (ARQ job tracking)
  users ── (JWT authentication)
```

### Table Details

| Table | Rows (typical) | Purpose |
|-------|----------------|---------|
| `users` | ~10 | Analyst accounts (username + bcrypt hash) |
| `topics` | ~20 | Monitored subjects (keywords, thresholds, languages) |
| `sources` | ~100 | OSINT sources (URLs, platforms, credibility scores, health) |
| `content_items` | ~100K+ | Scraped/collected text with embeddings (SHA-256 deduplicated) |
| `extracted_entities` | ~500K+ | NER results (PERSON, ORG, GPE, DATE) linked to content |
| `narrative_clusters` | ~1K | HDBSCAN clusters with centroids and source diversity counts |
| `signals` | ~500 | Threshold-based alerts (new → acknowledged → dismissed) |
| `reports` | ~200 | LLM-generated intelligence reports (immutable after generation) |
| `media_assets` | ~50K | Images/videos with pHash for reverse lookup |
| `vision_results` | ~50K | YOLO detections, deepfake scores, CLIP labels |
| `credibility_audit_log` | ~1K | Immutable log of every credibility score change |
| `report_source_warnings` | ~50 | Post-generation credibility downgrade alerts |
| `topic_content_items` | ~100K | Many-to-many join (content can appear in multiple topics) |
| `analysis_jobs` | ~10K | ARQ job tracking (status, payload, result, error) |

---

## Signal Engine

Signals are Anveshak's real-time alerting mechanism. They fire when enough independent sources corroborate a narrative cluster.

**How it works:**
1. Content items are clustered by semantic similarity (HDBSCAN on pgvector embeddings)
2. Each cluster tracks `independent_source_count` — the number of distinct `source.platform` values contributing to that cluster
3. When `independent_source_count >= topic.signal_threshold`, a signal is created
4. The API's background loop delivers signals to connected analyst sessions via WebSocket within ~10 seconds
5. Optionally, a webhook POST is fired to a configured URL

**Signal lifecycle:**
```
new → acknowledged → dismissed
                  → escalated
```

**Why independent sources matter:** A single Telegram channel posting the same thing 50 times is noise. But when Telegram, Reddit, and a news website all report the same narrative — that's a signal worth investigating.

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
- **JWT authentication:** Tokens issued on login, checked on every request. Expiry countdown shown in UI.
- **No hardcoded secrets:** All credentials come from environment variables (`.env` file, never committed).
- **Content hash logging only:** Raw scraped content is never logged — only `content_hash` and URL appear in logs.
- **LLM output validation:** Every LLM response is parsed through a Pydantic model before storage. Raw LLM strings are never trusted.
- **Prompt injection protection:** User input is sanitized and wrapped in boundary markers before inclusion in LLM prompts.
- **X/Twitter spend guard:** Monthly read count checked against `X_MONTHLY_READ_CAP` before every API call.
- **Rate limiting:** API gateway enforces per-IP request limits.
- **Security headers:** X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security on all responses.

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
| Deepfake | Facetorch CPU, EfficientNet | DIRE full model on GPU |
| Translation | NLLB-200 distilled 600M | NLLB-200 1.3B on GPU |
| Sentiment | VADER (rule-based, ~1 MB) | No GPU benefit |
| Keywords | YAKE (statistical, pure Python) | No GPU benefit |
| pgvector index | IVFFlat | HNSW on larger corpus |

See `hardware.md` for the complete upgrade matrix with memory requirements and expected performance gains.

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

Single-node Kubernetes deployment using Kustomize:

```bash
make k3s-deploy                # Apply all manifests to k3s
make k3s-teardown              # Remove namespace
```

Manifests in `infra/k3s/`: namespace, secrets, postgres (20 Gi PVC), redis, api, analyst (6 Gi memory limit).

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
| Deepfake scores are float 0.0-1.0 | Type system, never `bool` — analyst decides threshold |
| All LLM calls are async | ARQ jobs only — API routes never call Ollama directly |
| No cloud LLM with real data | Ollama localhost/container only, sovereign requirement |
| Credibility changes are audit-logged | DB transaction wraps UPDATE + INSERT together |
| X/Twitter spend is capped | `X_MONTHLY_READ_CAP` checked before every API call |
| Drishti bridge is one-directional | Emit only, never read from Drishti |
| Hardware config comes from env vars | All model names, device strings, batch sizes in `settings.py` |
| LLM output is Pydantic-validated | Raw LLM strings never stored or displayed |
| Standalone-first | `ANVESHAK_DRISHTI_BRIDGE=false` by default, no external dependencies |

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
| `media_store` | scraper-worker | Downloaded images and videos |
| `prometheus_data` | prometheus | Time-series metrics (15-day retention) |
| `grafana_data` | grafana | Dashboard state, user prefs |
| `loki_data` | loki | Log chunks and TSDB index (7-day retention) |
| `promtail_positions` | promtail | Log scrape offset positions |
