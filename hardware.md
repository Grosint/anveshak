# ANVESHAK — HARDWARE UPGRADE MATRIX

This file documents every hardware-constrained decision in the codebase.
Before adding any ML component, add its entry here.
The AGENTS.md hardware independence rule requires all settings to be env-var driven.

**Production hardware tiers:**

| Tier | Hardware | Cost | Throughput |
|------|----------|------|------------|
| CPU-only (dev/testing) | 16-core, 32GB RAM, 512GB NVMe | ~₹80K | ~50 articles/day translated, 5min/report |
| Demo/eval (recommended) | RTX 3080 (10GB), 32GB RAM, 1TB NVMe | ~₹1.5–2L | ~2K articles/day, 30s/report |
| IAF production | RTX 4090 (24GB), 64GB RAM, 2TB NVMe | ~₹3–4L | ~10K articles/day, 10s/report, 72b LLM |

**Critical CPU-only constraints (measured 2026-04-17):**
- Analyst worker needs **6GB RAM** (3 spaCy models + sentence-transformers + NLLB-200)
- Analyst scheduler needs only **512MB RAM** (no ML models — just asyncpg + numpy + hdbscan)
- NLLB translation: **~4 min per article on CPU** — production bottleneck for >50 articles/day
- NLLB model cold-load: ~25s on CPU (cached in Docker volume after first load)
- `TRANSLATION_MAX_CHARS=1500` required on CPU (Chinese chars ≈ 1 token, NLLB max 1024)
- GPU eliminates all above constraints; `TRANSLATION_MAX_CHARS=5000` safe on GPU

---

## Analyst Service — Scheduler/Worker Split (2026-04-29)

The analyst service is split into two containers from the same Docker image:

| Container | Role | Memory | Scaling |
|-----------|------|--------|---------|
| `analyst-scheduler` | Clustering, signals, convergence, orphan sweep | 124 MiB (limit: 512m) | Always 1 instance |
| `analyst-worker` | NLP, embedding, label gen, credibility, backfill | 1.5 GiB idle / 5.6 GiB with NLLB (limit: 6g) | `ANALYST_WORKER_REPLICAS` (default: 1) |

**Scaling guide:**

| Tier | Worker Replicas | Total Worker RAM | Throughput |
|------|----------------|-----------------|------------|
| CPU-only (dev) | 1 | 6 GB | ~50 articles/day |
| Demo/eval | 2 | 12 GB | ~100 articles/day |
| IAF production | 4 | 24 GB | ~400 articles/day |

**Config change:**
```
ANALYST_WORKER_REPLICAS=1  →  ANALYST_WORKER_REPLICAS=4
```

**Code change:** Zero. ARQ Redis BLPOP guarantees each job goes to exactly one worker.

---

## Clustering — `analyst-scheduler` service (2026-05-06)

**Current implementation:**
- Mode: Incremental assignment + HDBSCAN fallback
- Distance: 70% cosine + 30% entity MinHash (precomputed, `metric="precomputed"`)
- Adaptive min_cluster_size: `max(2, min(default, N//5))`
- Entity fingerprint: datasketch MinHash (128 permutations, BIGINT[] in PostgreSQL)
- Cost per cycle: O(new_items × existing_clusters) — not O(N²)
- Full HDBSCAN only runs on truly unassigned items or fresh topics

**Scaling bottleneck:** At 1000+ topics × 500+ items, even incremental clustering adds up. The scheduler runs clustering sequentially per topic.

**Upgrade path:**
- Parallelize clustering across topics (asyncio.gather or thread pool)
- GPU-accelerated HDBSCAN via cuML (RAPIDS) for full re-cluster cycles
- Hardware needed: NVIDIA GPU with RAPIDS support (RTX 3080+ for cuML)

**Config change:**
```
HDBSCAN_MIN_CLUSTER_SIZE=3           # production default
HDBSCAN_MIN_SAMPLES=2                # density core point definition
CLUSTER_ASSIGN_THRESHOLD=0.75        # cosine sim for incremental assignment
ENTITY_BLEND_WEIGHT=0.3              # 0=embedding only, 1=entity only
TOPIC_RELEVANCE_THRESHOLD=0.35       # pre-clustering filter
```

**Code change:** Zero for config tuning. GPU acceleration requires cuML dependency swap.

---

## NLP Models — `analyst-worker` service

**Current implementation:**
- English: `en_core_web_md` (43MB, ~85-90% NER F1)
- Russian: `ru_core_news_md` (91MB, ~82% NER F1)
- Chinese: `zh_core_web_md` (74MB, ~80% NER F1)
- Lazy-loaded per language (langdetect routes first)
- Total RAM: ~210MB for all three models

**Upgrade when available:**
- English: `en_core_web_trf` (438MB, ~94% NER F1) — transformer-based
- Russian: `ru_core_news_lg` (545MB, ~90% NER F1)
- Chinese: `zh_core_web_trf` (416MB, ~93% NER F1)

**Hardware needed:** 32GB RAM (no GPU required for NLP)

**Config change:**
```
SPACY_EN_MODEL=en_core_web_md  →  SPACY_EN_MODEL=en_core_web_trf
SPACY_RU_MODEL=ru_core_news_md →  SPACY_RU_MODEL=ru_core_news_lg
SPACY_ZH_MODEL=zh_core_web_md  →  SPACY_ZH_MODEL=zh_core_web_trf
```

**Code change:** Zero. `analyst/settings.py` maps env vars to model names.
Service loads model by config value, never hardcoded.

---

## LLM — Unified Model (cluster labels + reports) — `analyst` + `reporter` services

**Current implementation:**
- Model: `qwen2:7b` (4.4GB, single model for both cluster labelling and report generation)
- Replaced: `llama3.2:3b` (labels) + `mistral:7b` (reports) — net saving 2GB disk
- Speed: ~10-15s per label, ~3-5min per report on CPU
- All input text is English (post-translation) — no multilingual LLM needed
- Env var: `OLLAMA_MODEL=qwen2:7b` (shared by analyst and reporter)

**Upgrade when available:**
- Model: `qwen2.5:72b` (~40GB VRAM, ~2s/label, ~45s/report)
- Or split: `llama3.1:8b` for labels + `llama3.1:70b` for reports

**Hardware needed:** RTX 4090 (24GB VRAM) for 72b — or dual A100

**Config change:**
```
OLLAMA_MODEL=qwen2:7b  →  OLLAMA_MODEL=qwen2.5:72b
```

**Code change:** Zero. Both analyst and reporter read `settings.ollama_model`.

---

## Ollama Model Keep-Alive — all services using LLM

**Current implementation:**
- `OLLAMA_KEEP_ALIVE=5m` — model evicted from RAM after 5 minutes idle
- Saves RAM on constrained hardware (16GB laptop)
- Cold-start on first inference: 25-40s (qwen2:7b from SSD)
- Mitigation: pre-warm via dummy inference call in FastAPI lifespan startup

**Upgrade when available:**
- `OLLAMA_KEEP_ALIVE=-1` — model stays in VRAM permanently, zero cold-start

**Hardware needed:** GPU with sufficient VRAM (8GB for qwen2:7b, 40GB for 72b)

**Config change:**
```
OLLAMA_KEEP_ALIVE=5m  →  OLLAMA_KEEP_ALIVE=-1
```

**Code change:** Zero. Env var passed directly to Ollama container in compose.yml.

---

## Deepfake Detection — Image/Face — `vision` service

**Current implementation:**
- Model: `dima806/deepfake_vs_real_faces` (ConvNeXt-Tiny, HuggingFace → ONNX)
- ONNX size: ~110MB | Inference RAM: ~300MB
- Speed: ~8-12s per image on CPU
- Accuracy: ~96% on FaceForensics++/DFDC/GAN faces
- Detects: face manipulation, face swap, neural rendering artifacts
- License: Apache 2.0

**Upgrade when available:**
- Same Facetorch model with CUDA execution provider
- Speed: ~0.3s per image on GPU

**Hardware needed:** Any CUDA GPU (GTX 1080+)

**Config change:**
```
VISION_DEVICE=cpu  →  VISION_DEVICE=cuda
```

**Code change:** Zero. Vision service passes device to ONNX `ExecutionProvider`:
`CPUExecutionProvider` → `CUDAExecutionProvider`. Abstract `DeepfakeDetector` base class
handles the switch transparently.

---

## Deepfake Detection — Non-Face/Video/Landscape — `vision` service

**Current implementation:**
- Model: EfficientNet-B0 proxy classifier (CPU, ONNX)
- Speed: ~2s per frame on CPU
- Accuracy: ~85% on GenImage synthetic detection benchmark
- Limitation: less accurate than DIRE on landscape/construction content
- Pre-caches demo video results for live demo scenario

**Upgrade when available:**
- Model: DIRE (Detecting AI-Generated Images via Reconstruction Error)
- Speed: ~2s per frame on GPU (vs 90s on CPU — impractical without GPU)
- Accuracy: ~94% on GenImage benchmark

**Hardware needed:** RTX 3080+ (8GB VRAM — DIRE needs diffusion model in VRAM)

**Config change:**
```
VISION_DEEPFAKE_VIDEO_MODEL=efficientnet  →  VISION_DEEPFAKE_VIDEO_MODEL=dire
```

**Code change:** Zero. Both implement `DeepfakeDetector` ABC with `.score(image_bytes) -> float`.
Vision service instantiates by `settings.VISION_DEEPFAKE_VIDEO_MODEL`. No other changes.

---

## Object Detection — `vision` service

**Current implementation:**
- Model: YOLOv8n (nano, 6MB, CPU)
- Speed: ~200ms per image on CPU
- mAP50: 37.3 (good enough for prototype demo)
- Detects: 80 COCO classes — weapons, vehicles, aircraft, persons, etc.

**Upgrade when available:**
- Model: YOLOv8x (extra-large, 131MB, GPU)
- Speed: ~15ms per image on GPU
- mAP50: 53.9 — significantly better recall on small objects and cluttered scenes

**Hardware needed:** RTX 3080+ for meaningful speed improvement

**Config change:**
```
YOLO_MODEL_SIZE=nano  →  YOLO_MODEL_SIZE=xlarge
```

**Code change:** Zero. `MODEL_MAP` in vision/settings.py maps size string to model file.

---

## Sentence Embeddings — `analyst` service

**Current implementation:**
- Model: `all-MiniLM-L6-v2` (22MB, 384 dimensions)
- Speed: ~14ms per sentence on CPU
- Quality: Good for semantic similarity; adequate for OSINT clustering

**Upgrade when available:**
- Model: `BAAI/bge-large-en-v1.5` (1.3GB, 1024 dimensions)
- Speed: ~5ms per sentence on GPU
- Quality: Significantly better semantic precision on technical/intelligence content
- NOTE: Requires re-embedding entire corpus (migration V3 handles this)
- NOTE: pgvector column dimension changes from 384 → 1024 (migration required)

**Hardware needed:** 16GB RAM minimum; GPU for speed

**Config change:**
```
EMBEDDING_MODEL=all-MiniLM-L6-v2       →  EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
EMBEDDING_DIMENSIONS=384               →  EMBEDDING_DIMENSIONS=1024
```

**Code change:** Run migration V3 to re-embed corpus and change vector column dimension.
Application code reads dimension from settings — zero other changes.

---

## pgvector Index — PostgreSQL

**Current implementation (migration 003):**
- Index type: HNSW (Hierarchical Navigable Small World)
- Params: m=16, ef_construction=64 (env: HNSW_M, HNSW_EF_CONSTRUCTION)
- Performance: Self-tuning recall regardless of corpus size
- Build time: <60s for <100K vectors, ~5 minutes at 1M vectors
- Query latency: ~50ms at 1M vectors

**Upgrade for production (RTX 4090 tier):**
- Params: m=32, ef_construction=128 (higher recall, more RAM)
- Hardware needed: 32GB RAM (HNSW graph lives in memory)

**Config change:**
```
HNSW_M=32
HNSW_EF_CONSTRUCTION=128
```

**Code change:** Zero in application code. The `<=>` operator works identically.
Re-run migration 003 with new params if upgrading.

---

## X/Twitter Adapter — `social` service

**Current implementation:**
- Mode: Pay-per-use polling (tweepy + Bearer Token)
- Access: 7-day recent search only, polling every 15 minutes per topic
- Cost: $0.005/read — budget cap enforced via X_MONTHLY_READ_CAP env var
- Default cap: $200/month (40,000 reads) — adjustable
- No filtered stream (real-time push not available on pay-per-use)

**Upgrade when available:**
- Mode: Filtered stream (real-time push — posts arrive instantly)
- Access: Full-archive search (back to 2006) + real-time stream
- Requirement: X Enterprise API — negotiate contract with X Corp post-award

**Hardware needed:** None — contractual/budget requirement

**Config change:**
```
X_ADAPTER_MODE=polling          →  X_ADAPTER_MODE=stream
X_MONTHLY_READ_CAP=40000        →  X_MONTHLY_READ_CAP=unlimited
X_BEARER_TOKEN=<same key>       →  X_BEARER_TOKEN=<enterprise token>
```

**Code change:** Zero. `XPollingAdapter` and `XStreamAdapter` both implement
`SourceAdapterBase`. Social service loads by `settings.X_ADAPTER_MODE`.

---

## X/Twitter API Application — Approved Use Case

See `docs/x_api_application.md` for the exact use case description to submit
to developer.x.com when applying for API access.

Steps to activate X adapter:
1. Create X account with any email
2. Go to developer.x.com → sign up → fill use case form (use docs/x_api_application.md)
3. Instant approval for pay-per-use
4. Set X_ADAPTER_ENABLED=true and X_BEARER_TOKEN in .env
5. Set X_MONTHLY_READ_CAP to desired budget limit

---

## CLIP Semantic Classification — `vision` service

**Current implementation:**
- Model: `openai/clip-vit-base-patch32` (CPU, ~1.5GB RAM, ~800ms/image)
- Used for: analyst-defined category classification of ingested images
- Categories: user-defined at topic creation (`topic.clip_categories`)

**Upgrade when available:**
- Model: `openai/clip-vit-large-patch14` (GPU, ~6GB VRAM, ~50ms/image)
- Significantly better zero-shot accuracy on domain-specific categories

**Hardware needed:** Any CUDA GPU (GTX 1080+) for meaningful speed improvement

**Config change:**
```
CLIP_MODEL_NAME=openai/clip-vit-base-patch32  →  CLIP_MODEL_NAME=openai/clip-vit-large-patch14
```

**Code change:** Zero. `CLIPClassifier` reads `settings.clip_model_name`. No other changes.

---

## EfficientNet-B0 Deepfake (non-face/video) — `vision` service

**Current implementation:**
- Model: `umm-maybe/AI-image-detector` (EfficientNet-B0, HuggingFace → ONNX)
- ONNX size: ~20MB | Inference RAM: ~100MB
- Speed: ~2s per frame on CPU
- Accuracy: ~87% on CIFAKE, ~80-85% on out-of-distribution GenImage
- Used for: landscape, architecture, and non-face AI-generation detection
- License: Apache 2.0

**Upgrade when available:**
- Model: DIRE (Detecting AI-Generated Images via Reconstruction Error)
- Set `VISION_DEEPFAKE_VIDEO_MODEL=dire` and `VISION_DEVICE=cuda`
- Speed: ~2s per frame on GPU (vs 90s on CPU — impractical without GPU)
- Accuracy: ~94% on GenImage benchmark

**Hardware needed:** RTX 3080+ (8GB VRAM — DIRE uses diffusion model in VRAM)

**Config change:**
```
VISION_DEEPFAKE_VIDEO_MODEL=efficientnet  →  VISION_DEEPFAKE_VIDEO_MODEL=dire
VISION_DEVICE=cpu                         →  VISION_DEVICE=cuda
```

**Code change:** Zero. Both implement `DeepfakeDetector` ABC. Factory function in
`detectors/__init__.py` instantiates by `settings.vision_deepfake_video_model`.

---

## pHash Perceptual Hashing — `vision` service

**Current implementation:**
- Library: `imagehash` (pure Python, <1ms/image)
- Hash: 64-bit integer stored as BIGINT in `media_assets.phash`
- Lookup: SQL `BIT_COUNT(phash # query_phash) <= threshold` (Hamming distance)
- Default threshold: `PHASH_DUPLICATE_THRESHOLD=8` (near-duplicate)

**Upgrade path:** None required — pHash is CPU-native, no GPU benefit.

**Config change:**
```
PHASH_DUPLICATE_THRESHOLD=8  →  adjust threshold for precision/recall trade-off
```

**Code change:** Zero. Threshold read from `settings.phash_duplicate_threshold`.

---

## Offline Geocoding — `reporter` service

**Current implementation:**
- Library: `geonamescache` (bundled offline city/country data — ~5MB)
- No network calls, no API key required
- Coverage: ~50,000+ cities + all countries
- Speed: <1ms per lookup (in-memory dict)

**Upgrade path:** None required — geonamescache is hardware-agnostic.
For higher-precision geocoding (street-level), switch to Nominatim (self-hosted
OSM) by replacing `geocoder.py` logic. No settings.py change required.

**Config change:** None required.

**Code change:** Replace `geocoder.py` lookup logic only.

---

## PDF Text Extraction — `scraper` service

**Current implementation:**
- Library: PyMuPDF (`pymupdf>=1.24`, ~15MB)
- Type: CPU-only text extraction from PDF pages
- Speed: ~50ms per page on CPU (negligible)
- Memory: ~50MB per open document (released after extraction)
- Optional dependency: if not installed, feature silently disabled with INFO log

**Upgrade path:** None required — PyMuPDF is CPU-native, no GPU benefit.
For OCR on scanned PDFs (image-only pages), add Tesseract + pytesseract.

**Config change:** None. Install dependency: `pip install pymupdf`

**Code change:** None. `pdf_extract.py` handles missing import gracefully.

---

## PDF Rendering — `reporter` service

**Current implementation:**
- Library: WeasyPrint (HTML → PDF via Cairo + Pango rendering stack)
- No hardware dependency — CPU-only, ~500ms per report PDF
- Requires system libs: libcairo2, libpango, libgdk-pixbuf (in Dockerfile)

**Upgrade path:** None required — WeasyPrint is hardware-agnostic.

**Config change:** None required.

**Code change:** None.

---

## Translation — `analyst` service

**Current implementation:**
- Model: `facebook/nllb-200-distilled-600M` (~2.4GB, CPU-capable)
- Languages: 200+ — zh, hi, ar, ur, ru all handled by single model
- Speed: **~4 min per article on CPU** (measured: 1500 Chinese chars → 1065 English chars)
- Model cold-load: ~25s on CPU from HF cache volume
- Max input: `TRANSLATION_MAX_CHARS=1500` (Chinese chars ≈ 1 token each, NLLB max 1024 tokens)
- Translates non-English `clean_text` → English `translated_text` before NLP/embedding
- All downstream NLP, clustering, RAG, and reports operate on English text
- **Memory:** analyst container needs **6GB RAM** minimum (3 spaCy + embeddings + NLLB)
- **Bottleneck:** CPU translation is the slowest step; >50 articles/day requires GPU

**Upgrade when available:**
- Model: `facebook/nllb-200-1.3B` (~5.2GB, ~3s/article on GPU)
- Model: `facebook/nllb-200-3.3B` (~13GB, ~1s/article on GPU) — best quality for Arabic/Urdu
- With GPU: `TRANSLATION_MAX_CHARS=5000` is safe (GPU handles longer sequences fast)

**Hardware needed:** RTX 3080+ (8GB VRAM for 1.3B, 16GB for 3.3B)

**Config change:**
```
TRANSLATION_MODEL=facebook/nllb-200-distilled-600M  →  TRANSLATION_MODEL=facebook/nllb-200-1.3B
TRANSLATION_MAX_CHARS=1500                          →  TRANSLATION_MAX_CHARS=5000
```

**Code change:** Zero. `analyst/translation.py` reads `settings.translation_model`.

---

## Sentiment Analysis — `analyst` service

**Current implementation:**
- Library: VADER (Valence Aware Dictionary and sEntiment Reasoner)
- Type: Rule-based, pure Python, ~1MB memory
- Speed: <1ms per article (negligible)
- Output: compound score [-1.0, 1.0] stored in `content_items.labels.sentiment`

**Upgrade path:** None required — VADER is CPU-native, no GPU benefit.
For domain-specific sentiment (military/intelligence language), consider fine-tuning
a DistilBERT classifier on labelled OSINT data when GPU available.

**Config change:** None required.
**Code change:** None.

---

## Keyword Extraction — `analyst` service

**Current implementation:**
- Library: YAKE (Yet Another Keyword Extractor)
- Type: Unsupervised, statistical, pure Python
- Speed: <10ms per article (negligible)
- Output: top-10 key phrases stored in `content_items.labels.keywords`

**Upgrade path:** None required — YAKE is CPU-native, no GPU benefit.

**Config change:** None required.
**Code change:** None.

---

## Summary Upgrade Checklist

When production hardware (RTX 3080+, 32GB RAM) is available, update these env vars in .env:

```bash
# NLP — upgrade to transformer models
SPACY_EN_MODEL=en_core_web_trf
SPACY_RU_MODEL=ru_core_news_lg
SPACY_ZH_MODEL=zh_core_web_trf

# LLM — upgrade to larger model (single model handles labels + reports)
OLLAMA_MODEL=qwen2.5:72b
OLLAMA_KEEP_ALIVE=-1

# Translation — upgrade to higher-quality model
TRANSLATION_MODEL=facebook/nllb-200-1.3B

# Vision — enable GPU + better models
VISION_DEVICE=cuda
YOLO_MODEL_SIZE=xlarge
VISION_DEEPFAKE_VIDEO_MODEL=dire
CLIP_MODEL_NAME=openai/clip-vit-large-patch14

# Embeddings — upgrade (requires re-embedding migration)
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
EMBEDDING_DIMENSIONS=1024

# pgvector — upgrade index (run: make migrate-hnsw)
# No env var — run migration V2b
```

Pull Ollama model after hardware upgrade:
```bash
ollama pull qwen2.5:72b
ollama rm qwen2:7b
```

Zero application code changes required for any of the above.

---

## YouTube Adapter — `social` service (2026-06-21)

**Current implementation:**
- YouTube Data API v3 for video metadata + comments (API key, free tier)
- `youtube-transcript-api` for caption extraction (zero API quota cost)
- On-demand video download via `yt-dlp` → existing vision pipeline
- No ML models — purely API-driven text extraction

**Hardware impact:**
- Caption extraction: ~0 CPU (text download, <1KB per video)
- Comment ingestion: ~0 CPU (API response parsing)
- On-demand video deepfake analysis: uses existing EfficientNet keyframe pipeline
  - 10-min video at 5s intervals = ~120 frames × ~200ms/frame = ~24s on CPU
  - Per-video only, analyst-triggered, not bulk
- Storage: video files 100MB-1GB each — `YOUTUBE_MAX_VIDEO_SIZE_MB=500` default

**Quota constraints (not hardware):**
- YouTube Data API v3: 10,000 units/day (free tier)
- `playlistItems.list` = 1 unit, `videos.list` = 1 unit, `commentThreads.list` = 1 unit
- `YouTubeQuotaGuard` enforces daily cap via Redis atomic counter (same pattern as `XSpendGuard`)
- `YOUTUBE_DAILY_QUOTA_CAP=9000` (reserve 1K headroom)

**Upgrade path:** Apply for elevated API quota through Google Cloud console for government use.

**Config change:**
```
YOUTUBE_API_KEY=<key>
YOUTUBE_ADAPTER_ENABLED=true
YOUTUBE_DAILY_QUOTA_CAP=9000
YOUTUBE_FETCH_COMMENTS=true
```

**Code change:** None required for hardware upgrades. GPU improves video deepfake speed only.
