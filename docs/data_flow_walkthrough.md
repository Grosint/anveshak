# Data Flow Walkthrough — "China UAV" Topic Example

This document explains the complete end-to-end flow through all Anveshak pillars using
a concrete example: creating a topic called **"China UAV"**.

---

## The Big Picture

There are **5 modules + 1 cross-cutting layer**. Every piece of content flows through a
chain: ingest → NLP → vision → clustering → signals → report. Redis is the glue that
connects all services asynchronously.

---

## Step 1 — Topic Creation

```
POST /api/v1/topics
{
  "name": "China UAV",
  "keywords": ["China", "UAV", "drone", "PLA"],
  "languages": ["en", "zh"],
  "signal_threshold": 3,
  "clip_categories": ["drone", "aircraft", "military vehicle"]
}
```

**PostgreSQL — `topics` table:**

| Column | Value |
|--------|-------|
| `id` | UUID |
| `name` | "China UAV" |
| `keywords` | `["China", "UAV", "drone", "PLA"]` |
| `languages` | `["en", "zh"]` |
| `signal_threshold` | 3 (signal fires when 3 independent sources agree) |
| `clip_categories` | `["drone", "aircraft", "military vehicle"]` |
| `status` | `active` |
| `labels` | `{}` (mandatory, never null) |

**Redis — immediately after insert:**

The API enqueues an ARQ job:
```
ARQ → backfill_topic_job(topic_id)
```
This job searches ALL existing content using pgvector cosine similarity — if content
about drones already existed, it gets linked to this topic instantly.

---

## Step 2 — Web Scraping (M2)

```
ARQ job: scrape_topic(topic_id)
```

1. Fetches each active `sources` row where `platform = 'web'`
2. **Crawl4AI** (headless browser, renders JavaScript) fetches the page
3. Falls back to **trafilatura** if Crawl4AI returns < 50 chars
4. Normalises text: `lowercase + collapse whitespace`
5. Computes `content_hash = SHA-256(normalised_text)`
6. Inserts into **`content_items`**:

```sql
INSERT INTO content_items (id, topic_id, source_id, raw_text, clean_text,
  content_hash, url, captured_at, credibility_score_at_capture, labels)
VALUES (...)
ON CONFLICT(content_hash) DO NOTHING  -- hard deduplication rule
```

7. Downloads images/videos to `media/china-uav-uuid/2026/04/15/{hash}.jpg`
8. Inserts row into **`media_assets`**
9. Enqueues two more ARQ jobs into Redis:
   - `analyse_content(content_item_id)` → analyst service
   - `run_vision_analysis(media_asset_id)` → vision service

---

## Step 3 — Social Collection (M3)

```
ARQ job: poll_social_topic(topic_id, include_x=True)
```

Four adapters run for each topic:

| Adapter | Library | Source Format | What it does |
|---------|---------|--------------|--------------|
| **Telegram** | Telethon | `t.me/channelname` | Reads last 50 messages per channel |
| **Reddit** | PRAW | `r/subreddit` | Polls `new` + `hot` feeds |
| **Bluesky** | atproto | network-wide | Searches posts for each keyword |
| **X/Twitter** | tweepy v2 | `@handle` / hashtag | `recent_search` API |

**X spend guard (Redis):**
```
Key: anveshak:x:monthly_reads:2026-04
INCR → if count > cap → hard stop, API call is blocked
Auto-expires at month end via TTL
```
This prevents silent overrun of the monthly X API budget.

Each adapter yields `RawItem` objects. Each is normalised, hash-computed, and inserted
into `content_items` via `ON CONFLICT DO NOTHING`. Then `analyse_content` is enqueued.

---

## Step 4 — NLP Pipeline (M1+M2, spaCy)

```
ARQ job: analyse_content(content_item_id)
```

1. **Language detection** — `langdetect` on `clean_text`
2. **spaCy NER** — model selected by language:
   - English → `en_core_web_sm`
   - Russian → `ru_core_news_sm`
   - Chinese → `zh_core_web_sm`
3. Extracted entities inserted into **`extracted_entities`**:

| `entity_type` | Example for "China UAV" content |
|--------------|----------------------------------|
| `ORG` | "PLA Air Force", "DJI" |
| `LOCATION` | "South China Sea", "Taiwan" |
| `PERSON` | general names mentioned |
| `FACILITY` | airbase names |
| `DATE` | "April 2026" |

4. **sentence-transformers** encodes `clean_text` → 384-dim vector
5. Stored: `UPDATE content_items SET embedding = $1::vector, language = $2`

This embedding powers semantic search and clustering downstream.

---

## Step 5 — Vision / Deepfake Pipeline (M4)

```
ARQ job: run_vision_analysis(media_asset_id)
```

Every image and video passes through this pipeline:

```
Image/Video
  ↓
EXIF extraction          → GPS coords, camera model, timestamps → media_assets.exif_data
pHash computation        → BIGINT stored for reverse lookup
  ↓
YOLO object detection    → [{label: "drone", confidence: 0.94, bbox: [x,y,w,h]}, ...]
  ↓
Has faces?
  ├── YES → FacetorchDetector → deepfake_score: 0.87  (float 0.0–1.0, never bool)
  └── NO  → Generic deepfake model → deepfake_score: 0.12
  ↓
topic.clip_categories defined?
  └── YES → CLIP zero-shot: [{label: "drone", score: 0.91}, {label: "aircraft", score: 0.65}]
  ↓
INSERT INTO vision_results (media_asset_id, yolo_detections, clip_labels,
  deepfake_score, deepfake_model, synthetic_probability, processed_at, labels)
```

**Videos:** FFmpeg extracts keyframes, each frame is scored, worst-case deepfake score
propagates to the whole video.

**Credibility feedback loop:** If `deepfake_score > 0.8` for a source's content, the
`update_source_credibility` ARQ job automatically downgrades that source's
`credibility_score` — and writes an immutable row to **`credibility_audit_log`**.

---

## Step 6 — Clustering (M2, pgvector)

```
ARQ job: run_clustering(topic_id)
```

1. Fetches all 384-dim embeddings for the topic from `content_items`
2. Groups semantically similar items via pgvector cosine similarity
3. Upserts into **`narrative_clusters`**:

| Column | Value |
|--------|-------|
| `label` | (generated by LLM, see below) |
| `item_count` | 17 |
| `independent_source_count` | 4 (Telegram + Reddit + web + Bluesky) |
| `embedding_centroid` | vector(384) |

4. Enqueues `generate_cluster_label(cluster_id)` — calls **Ollama** (mistral:7b)
   asynchronously to produce a label like _"PLA drone incursions near Taiwan Strait"_

---

## Step 7 — Signals Engine (cross-cutting)

After clustering, the signal engine checks:

```sql
SELECT nc.independent_source_count, t.signal_threshold
FROM narrative_clusters nc JOIN topics t ON t.id = nc.topic_id
WHERE nc.independent_source_count >= t.signal_threshold  -- 4 >= 3 → FIRE
```

A row is inserted into **`signals`**:

```
signal_type:  threshold_crossed
status:       new
description:  "Cluster 'PLA drone...' confirmed by 4 independent platforms"
evidence:     {cluster_id, sources: [...]}
```

**WebSocket delivery:** The API polls `signals WHERE delivered_at IS NULL` every 5 seconds
and pushes the payload to every connected analyst browser over WebSocket — no page refresh
needed.

Signal lifecycle: `new → acknowledged → dismissed`

---

## Step 8 — Report Generation (M5)

```
POST /api/v1/reports
{topic_id, report_type: "intelligence_brief", credibility_min: 50}
  ↓
INSERT INTO reports (generated_at=NULL, ...)   ← placeholder row
  ↓
ARQ job: generate_report(report_id)
```

Inside the ARQ worker:

1. **RAG** — pgvector cosine search selects the most relevant `content_items`,
   filtered by `credibility_score_at_capture >= 50`
2. Context assembled and truncated to `rag_max_context_tokens`
3. Prompt rendered via Jinja2 with anti-hallucination rules:
   - "Only use facts from the provided context"
   - "Every claim must cite [Source: name]"
4. **Ollama** (`mistral:7b`) generates the report — fully local, no cloud
5. LLM output validated through a **Pydantic model** before storage
6. spaCy NER extracts locations → geocoded → stored as **GeoJSON** for the map view
7. `source_snapshot` captures credibility scores at this exact moment
8. Report finalised:

```sql
UPDATE reports
SET generated_at=NOW(), content_md=$1, geojson=$2, source_snapshot=$3
WHERE generated_at IS NULL  -- idempotent guard; set ONCE, never again
```

The report is **immutable forever**. If a cited source is later downgraded, a
`report_source_warnings` row is inserted — the report itself is never modified.

---

## Complete Data Flow

```
You: "China UAV" topic created
         │
         ▼
    [PostgreSQL: topics]
         │
         ├──▶ ARQ(Redis): backfill_topic_job ──▶ pgvector search existing content
         │
         ├──▶ Scraper polls web sources
         │         │ Crawl4AI / trafilatura
         │         ▼
         │    [PostgreSQL: content_items]  ← ON CONFLICT content_hash DO NOTHING
         │         │                │
         │         │                └──▶ ARQ: run_vision_analysis
         │         │                          │ YOLO + deepfake + CLIP
         │         │                          ▼
         │         │                    [PostgreSQL: vision_results]
         │         │                          │ deepfake_score > 0.8?
         │         │                          └──▶ downgrade source credibility
         │         │                               [PostgreSQL: credibility_audit_log]
         │         │
         │         └──▶ ARQ: analyse_content
         │                   │ langdetect + spaCy NER + sentence-transformers
         │                   ▼
         │              [PostgreSQL: extracted_entities]
         │              [UPDATE content_items SET embedding=vector(384)]
         │
         ├──▶ Social adapters (Telegram / Reddit / Bluesky / X)
         │         │ X: Redis spend guard (atomic INCR, monthly TTL)
         │         ▼
         │    [PostgreSQL: content_items] → same NLP + Vision chain above
         │
         ├──▶ ARQ: run_clustering
         │         │ pgvector cosine grouping
         │         ▼
         │    [PostgreSQL: narrative_clusters]
         │         │
         │         └──▶ ARQ: generate_cluster_label (Ollama, async)
         │                   │
         │                   ▼
         │    Signal engine: independent_source_count >= signal_threshold?
         │         │
         │         ▼
         │    [PostgreSQL: signals]
         │         │
         │         └──▶ WebSocket push → analyst browser (5s polling loop)
         │
         └──▶ ARQ: generate_report
                   │ RAG (pgvector) → Ollama mistral:7b → Pydantic validate
                   ▼
              [PostgreSQL: reports]  ← generated_at set ONCE, immutable forever
              + GeoJSON (map data)
```

---

## Technology Reference

| Technology | Where / Why |
|-----------|-------------|
| **PostgreSQL 16** | All persistent state: topics, content, entities, clusters, signals, reports |
| **pgvector** | Semantic search + clustering (384-dim embeddings, IVFFlat index) |
| **Redis** | ARQ job queues between all services + X API spend guard |
| **ARQ** | Async job runner — every heavy task is a background job, never blocks a route |
| **spaCy** | NER (persons, orgs, locations) + language detection in analyst service |
| **sentence-transformers** | Text → 384-dim vector for semantic search and clustering |
| **Crawl4AI** | JS-rendering web scraper (primary) |
| **trafilatura** | HTML extraction fallback |
| **Telethon** | Telegram collection |
| **PRAW** | Reddit collection |
| **atproto** | Bluesky collection |
| **tweepy v2** | X/Twitter collection (spend-guarded) |
| **YOLOv8** | Object detection on images (drone, person, weapon, vehicle) |
| **CLIP** | Zero-shot image classification against topic-defined categories |
| **Facetorch / DIRE** | Face-based deepfake detection (probability 0.0–1.0, never boolean) |
| **Ollama** | Local LLM inference (mistral:7b) — cluster labelling + report generation |
| **LiteLLM** | Abstraction layer over Ollama so models are swappable via env var |
| **Prometheus + structlog** | Observability — metrics per job, logs with content_hash (never raw text) |
| **WebSocket** | Real-time signal push to analyst browser |
| **React + MapLibre GL** | Frontend workbench + GeoJSON map for report locations |

---

## Database Tables Quick Reference

```
users                  — authentication
topics                 — monitoring subjects
sources                — OSINT sources (web, telegram, twitter, reddit, bluesky, rss)
credibility_audit_log  — immutable audit trail for every credibility change
content_items          — all scraped/ingested content (embedding vector(384))
extracted_entities     — NER results per content item
media_assets           — images/videos (exif_data, phash)
vision_results         — YOLO detections, CLIP labels, deepfake_score
narrative_clusters     — grouped content (embedding_centroid vector(384))
signals                — intelligence alerts (new → acknowledged → dismissed)
analysis_jobs          — async job tracking (status: queued/running/done/failed)
reports                — immutable LLM reports (generated_at set ONCE)
report_source_warnings — retroactive alerts when cited sources are downgraded
```

## ARQ Job Functions Quick Reference

```
scrape_topic                — web scraping (scraper service)
analyse_content             — NLP + embedding (analyst service)
run_clustering              — pgvector cluster grouping (analyst service)
generate_cluster_label      — Ollama LLM label for a cluster (analyst service)
backfill_topic_job          — link existing content to new topic (analyst service)
update_source_credibility   — deepfake-driven credibility downgrade (analyst service)
run_cross_verification      — boost credibility for multi-platform clusters (analyst)
run_contradiction_scoring   — daily cron: downgrade high-noise sources (analyst)
run_vision_analysis         — YOLO + deepfake + CLIP (vision service)
poll_social_topic           — all social adapters (social service)
generate_report             — RAG + Ollama report generation (reporter service)
check_scheduled_reports     — cron: enqueue scheduled reports (reporter service)
check_source_warnings       — cron: retroactive warning scan (reporter service)
```
