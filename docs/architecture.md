# Anveshak — Architecture Reference

## What Anveshak Is

Anveshak (Sanskrit: investigator, seeker) is a standalone, sovereign AI-OSINT analysis and monitoring platform. It is purpose-built for iDEX ADITI 4.0 PS-18 (IAF).

**Product strategy:** Sell Anveshak first. Drishti is the upsell.

Anveshak runs on a single machine. No Kafka, no Vault, no AGE graph database required.

---

## System Context

```
╔══════════════════════════════════════════════════════════════╗
║                        INTERNET                              ║
║  Web sources  Telegram  Reddit  Bluesky  X/Twitter           ║
╚══════════╤══════════════════════════════════╤════════════════╝
           │                                  │
     ┌─────▼─────┐                    ┌───────▼──────┐
     │  scraper  │                    │    social    │
     │ (Crawl4AI)│                    │  (adapters)  │
     └─────┬─────┘                    └───────┬──────┘
           │         content_items            │
           └──────────────┬───────────────────┘
                          │
                   ┌──────▼──────┐
                   │  PostgreSQL │ ← pgvector (embeddings)
                   │  + pgvector │ ← credibility_audit_log
                   └──────┬──────┘
                          │
           ┌──────────────┼───────────────────┐
           │              │                   │
     ┌─────▼─────┐  ┌─────▼──────┐   ┌───────▼──────┐
     │  analyst  │  │   vision   │   │   reporter   │
     │ NLP+embed │  │ YOLO+deep  │   │  LLM+RAG+PDF │
     │ cluster   │  │ fake+EXIF  │   │              │
     └─────┬─────┘  └────────────┘   └───────┬──────┘
           │                                  │
           │      signals / clusters          │
           └──────────────┬───────────────────┘
                          │
                   ┌──────▼──────┐
                   │     API     │ ← FastAPI + ARQ jobs
                   │  (gateway)  │ ← WebSocket push
                   └──────┬──────┘
                          │
                   ┌──────▼──────┐
                   │  frontend   │
                   │  (analyst   │
                   │  workbench) │
                   └─────────────┘

                   ┌─────────────┐
                   │   Ollama    │ ← local LLM (no cloud)
                   │ mistral:7b  │
                   │ llama3.2:3b │
                   └─────────────┘

                   ┌─────────────┐    (optional)
                   │  Drishti    │ ←─ one-way emit only
                   │  Platform   │    source.envelopes.v1
                   └─────────────┘    ANVESHAK_DRISHTI_BRIDGE=true
```

---

## Services

| Service | Port | Purpose |
|---------|------|---------|
| `api` | 8000 | FastAPI gateway, JWT auth, WebSocket, ARQ job dispatch |
| `scraper` | 8001 | Open-web crawling via Crawl4AI + trafilatura |
| `social` | 8002 | Platform adapters: Telegram, Reddit, Bluesky, X |
| `vision` | 8003 | YOLO, CLIP, deepfake (image+video), EXIF, pHash |
| `analyst` | 8004 | NLP, embeddings, clustering, credibility, signals |
| `reporter` | 8005 | LLM report generation (RAG), GIS output, PDF export |
| `postgres` | 5432 | PostgreSQL 16 + pgvector |
| `redis` | 6379 | Task queue (ARQ), caching |
| `ollama` | 11434 | Local LLM inference (sovereign — no cloud) |
| `prometheus` | 9090 | Metrics |
| `grafana` | 3001 | Dashboards |
| `frontend` | 3000 | React analyst workbench |

---

## Five Modules (PS-18 Scope)

### M1 — Source Credibility (`analyst`)

- Every source has a `credibility_score` (0–100)
- Score changes are immutably audit-logged in `credibility_audit_log`
- Auto-feedback loop: sources amplifying confirmed deepfakes are auto-downgraded
- Retroactive report flagging: when a source degrades, `report_source_warnings` is written; the report itself is NOT modified

### M2 — Open-Web Analysis (`scraper` + `analyst`)

- Crawl4AI fetches clean text from arbitrary URLs (handles JS, paywalls with config)
- trafilatura as fallback for content extraction
- langdetect routes to spaCy en/ru/zh NLP pipeline
- sentence-transformers generates embeddings for clustering and search
- HDBSCAN clusters related content into `narrative_clusters`
- Historical backfill: on new topic creation, pgvector cosine search over existing corpus

### M3 — Social Media Monitoring (`social`)

- Telegram: Telethon (requires session string bootstrap — see Vault or env)
- Reddit: PRAW (script app credentials)
- Bluesky: atproto
- X/Twitter: tweepy + Bearer Token (pay-per-use, $0.005/read, hard cap enforced)
- All adapters implement `SourceAdapterBase` — polling or stream mode, configurable

### M4 — Image / Video Analysis (`vision`)

- Object detection: YOLOv8n (80 COCO classes — weapons, vehicles, aircraft, persons)
- Face deepfake: Facetorch ONNX (CPU) — ~91% AUC on FaceForensics++
- Non-face/video deepfake: EfficientNet-B0 proxy (CPU) — upgrades to DIRE on GPU
- CLIP: semantic image search and classification
- EXIF: metadata extraction and anomaly detection (GPS stripped, AI software tags)
- pHash: perceptual hash for reverse image lookup across corpus
- All scores are float 0.0–1.0 (never boolean) — analyst decides threshold

### M5 — LLM Reports (`reporter`)

- Types: `intelligence_brief`, `research_summary`, `weekly_digest`
- RAG: top-k cosine search over pgvector corpus → grounded LLM prompt
- LLM: Ollama `mistral:7b` (local, sovereign — intelligence data never leaves deployment)
- All jobs run as ARQ background tasks — API returns job_id immediately
- Reports are **immutable**: `generated_at` set once, `source_snapshot` captures credibility at generation time

---

## Data Flow

```
1. Topic created by analyst (keywords + signal_threshold)
           │
2. scraper + social collect matching content
           │
3. ContentItem stored with SHA-256 content_hash
   ON CONFLICT(content_hash) DO NOTHING  ← dedup
           │
4. ARQ job: analyst processes text
   - langdetect → spaCy NLP (NER, POS)
   - sentence-transformers → embedding vector stored in pgvector
   - HDBSCAN clustering → narrative_cluster updated
           │
5. Signal engine checks:
   cluster.independent_source_count >= topic.signal_threshold?
   → YES: INSERT into signals, push via WebSocket to analyst session
           │
6. Analyst reviews signals, requests report
           │
7. ARQ job: reporter generates LLM brief
   - pgvector cosine search → top-k context chunks
   - Ollama RAG prompt → structured output
   - Pydantic validation before storage
   - generated_at set ONCE (immutable)
```

---

## Key Invariants

| Rule | Enforcement |
|------|-------------|
| Labels are never Optional | `verify_labels.py`, unit tests |
| Reports are immutable | `verify_reports_immutable.py`, no UPDATE on `generated_at` |
| Content is deduplicated | `UNIQUE(content_hash)`, ON CONFLICT DO NOTHING |
| Deepfake scores are float | Type system, never `bool` |
| All LLM calls are async | ARQ jobs only — routes never call Ollama directly |
| No cloud LLM | Ollama localhost/container only |
| Credibility changes are audit-logged | Transaction wraps UPDATE + INSERT together |
| X spend is capped | `X_MONTHLY_READ_CAP` checked before every API call |
| Drishti bridge is one-directional | Emit only, never read |
| Hardware config comes from env | All model names, devices in `settings.py` only |

---

## Hardware Independence

All hardware-sensitive settings come from environment variables. The code never has a hardcoded model name, device string, or batch size. See `hardware.md` for the full upgrade matrix — when production hardware is available, update `.env` only. Zero code changes required.

Current defaults (CPU-safe, 16GB RAM laptop):
- NLP: `en_core_web_md` / `ru_core_news_md` / `zh_core_web_md`
- LLM: `mistral:7b` (report), `llama3.2:3b` (cluster)
- YOLO: nano
- Deepfake: Facetorch CPU, EfficientNet CPU
- Embeddings: `all-MiniLM-L6-v2` (384 dims)
- pgvector: IVFFlat index

---

## Drishti Bridge

When `ANVESHAK_DRISHTI_BRIDGE=true`, the analyst service emits extracted named entities (persons, organisations, locations) as `source.envelopes.v1` Redpanda messages to the Drishti fusion platform.

Rules:
- Anveshak only emits TO Drishti — never reads FROM Drishti
- Bridge uses a separate Docker Compose overlay (`compose.bridge.yml`)
- Source ID on emitted envelopes: `anveshak-v1`
- Topics produced: `source.envelopes.v1`

---

## Deployment

### Development (Docker Compose)
```bash
cp .env.example .env
# edit .env: set POSTGRES_PASSWORD, API_SECRET_KEY, GRAFANA_ADMIN_PASSWORD
make up
make init
make seed-demo
```

### Production (k3s)
See `infra/k3s/` — single-node k3s with persistent volumes for PostgreSQL and Ollama models.

Demo hardware recommendation: RTX 3080 (10GB VRAM), 32GB RAM, NVMe SSD 1TB, 8-core CPU.
This eliminates all hardware risks and enables all GPU-tier model upgrades.
Cost: ~₹1.5–2L. Negligible for a ₹25Cr grant application.
