# ANVESHAK — HARDWARE UPGRADE MATRIX

This file documents every hardware-constrained decision in the codebase.
Before adding any ML component, add its entry here.
The AGENTS.md hardware independence rule requires all settings to be env-var driven.

**Production hardware tiers:**

| Tier | Hardware | Cost | Throughput |
|------|----------|------|------------|
| CPU-only (dev/testing) | 16-core, 32GB RAM, 512GB NVMe | ~₹80K | ~1.5K articles/day at 50% non-English, 5min/report |
| Demo/eval (recommended) | RTX 3080 (10GB), 32GB RAM, 1TB NVMe | ~₹1.5–2L | ~2K articles/day, 30s/report |
| IAF production | RTX 4090 (24GB), 64GB RAM, 2TB NVMe | ~₹3–4L | ~10K articles/day, 10s/report, 72b LLM |

**Critical CPU-only constraints (measured 2026-04-17, two figures re-measured 2026-09-15):**
- Analyst worker needs **12GB RAM on CPU**, not 6GB. See the re-measurement below.
- Analyst scheduler needs only **512MB RAM** (no ML models, just asyncpg + numpy + hdbscan)
- NLLB translation: **45 to 70s per article on CPU**, not 4 minutes. See the re-measurement below.
- NLLB model cold-load: ~25s on CPU (cached in Docker volume after first load)
- `TRANSLATION_MAX_CHARS=1500` required on CPU (Chinese chars are about 1 token, NLLB max 1024)
- GPU eliminates all above constraints; `TRANSLATION_MAX_CHARS=5000` safe on GPU

### Re-measurement 2026-09-15

Two figures in this file were wrong in opposite directions, and both were found by triaging a stalled pipeline rather than by a benchmark.
Superseded values are kept here rather than deleted, because the original measurement was correct for the configuration it was taken on.

**Translation speed was pessimistic by roughly 4x.**
The 4-minute figure was measured before `TRANSLATION_MAX_CHARS=1500` and before the 480-token encoder clamp existed.
Both truncate the input, so the generation is far shorter than the one that was originally timed.
Measured on the development deployment, Hindi articles through the full `analyse_content` job:

```
45.23s ← a6b02913b46d4e43a04ceb473dbc6e59:analyse_content  (hi, translated=True)
69.83s ← 23c2a5b69f9e44a99d6bfd4307784536:analyse_content  (hi, translated=True)
 1.10s ← 82ffda528c6841dca2831bf44cc340f4:analyse_content  (en, 199 entities)
 0.18s ← 71c0989b616241df8364ea8d9de35a74:analyse_content  (en)
```

English is two orders of magnitude cheaper because it skips NLLB entirely.
`needs_translation()` tests membership in `_NLLB_SRC_CODES`, and `en` is not a key: English is the target language, never a source.
So the CPU throughput ceiling is set by the non-English fraction, not by total volume.

The practical consequence is that the "~50 articles/day" headline for the CPU tier is too low by about 4x.
A correctly configured CPU worker handles roughly **1,500 to 2,000 articles/day at a 50% non-English mix**.
That is still far below production volume, so the conclusion that production needs a GPU is unchanged.
Only the size of the gap was wrong.

**Analyst worker memory was optimistic, and the 6g limit does not hold.**
The original figure of `1.5 GiB idle / 5.6 GiB with NLLB` fits under `mem_limit: 6g` on paper.
In practice the worker was OOM-killed 12 times in 15 hours, each kill losing its in-flight jobs:

```
Memory cgroup out of memory: Killed process 67657 (python) anon-rss:6270008kB
oom-kill:constraint=CONSTRAINT_MEMCG,...,oom_memcg=/docker/85e664f389b7...  (anveshak-analyse-worker-1)
```

The missing term is allocator retention.
Torch and glibc do not return freed inference activations to the OS, so the idle baseline creeps upward over a worker's life rather than returning to 1.5 GiB.
Measured idle, queue empty, 0.37% CPU, on a worker that had been running for minutes:

```
anveshak-analyse-worker-1   2.994GiB / 6GiB   0.37%
```

Usable headroom on a worked worker is therefore about 3 GB, not the 4.5 GB the original figure implies, and `max_jobs=4` concurrent activations overrun it.

This failure is almost invisible from the outside, which is why it ran for 21 hours before anyone looked.
`docker inspect` reported `exit=0 OOM=false`, because Docker only sets its `OOMKilled` flag when PID 1 is the victim and here the kernel killed a worker process inside the container.
`restart: unless-stopped` then brought it straight back, the ARQ heartbeat resumed, and `failed_jobs` stayed empty because a `SIGKILL` cannot write a dead letter row.
The container read `healthy` throughout while 6,573 jobs went nowhere.

**Resolved 2026-09-15: `mem_limit` raised to `12g`.**
`infra/compose.yml` now reads `mem_limit: ${ANALYST_MEM_LIMIT:-12g}` on `analyse-worker`, which covers the 3.0 GiB baseline plus roughly 1.6 GiB per concurrent job at `ANALYST_MAX_JOBS=4`.

The alternative was to hold `6g` and drop `ANALYST_MAX_JOBS` to 1.
`ANALYST_MAX_JOBS=2` was rejected: it only clears `6g` if the worker is restarted at the same moment, because the restart is what resets the allocator baseline, and a correct setting that depends on an operator remembering to restart is not a correct setting.

`tests/unit/test_analyst_memory_invariant.py` now pins the two values against each other, so neither can be tuned back into the failing pair.
The formula it encodes is `3.0 + 1.6 x ANALYST_MAX_JOBS` GiB, both terms measured rather than estimated.

`ANALYST_MEM_LIMIT` exists because the limit must also stay **below the Docker VM's total RAM**.
A limit above it can never bind, and the host-wide OOM killer then fires first and picks a fatter victim, usually postgres or ollama, leaving the worker alive and the kill unattributed.
The development laptop's Colima VM has 11934 MB, so `12g` does not bind there and that host must set `ANALYST_MEM_LIMIT` lower **and** lower `ANALYST_MAX_JOBS` to match.
A production node built to the sizing below has 64 GB and needs no override.

On GPU the question disappears: the activations that overrun the cgroup move to VRAM, and `6g` becomes correct again.

---

## Analyst Service — Scheduler/Worker Split (2026-04-29)

The analyst service is split into two containers from the same Docker image:

| Container | Role | Memory | Scaling |
|-----------|------|--------|---------|
| `analyst-scheduler` | Clustering, signals, convergence, orphan sweep | 124 MiB (limit: 512m) | Always 1 instance |
| `analyst-worker` | NLP, embedding, label gen, credibility, backfill | 3.0 GiB idle after work / 6.3 GiB peak at `max_jobs=4` (limit: `${ANALYST_MEM_LIMIT:-12g}`, raised from 6g, see Re-measurement) | `ANALYST_WORKER_REPLICAS` (default: 1) |

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
- Speed: **45 to 70s per article on CPU** (measured 2026-09-15 on Hindi, end to end through `analyse_content`)
- Superseded: "~4 min per article", measured 2026-04-17 before the char and token clamps existed
- Model cold-load: ~25s on CPU from HF cache volume
- Max input: `TRANSLATION_MAX_CHARS=1500` (Chinese chars ≈ 1 token each, NLLB max 1024 tokens)
- Translates non-English `clean_text` → English `translated_text` before NLP/embedding
- All downstream NLP, clustering, RAG, and reports operate on English text
- **Memory:** analyst container needs **12GB RAM on CPU** at `ANALYST_MAX_JOBS=4`. The 6GB figure OOM-killed the worker 12 times in 15 hours. See Re-measurement 2026-09-15.
- **Bottleneck:** CPU translation is the slowest step, and it sits on the embedding critical path rather than beside it. `all-MiniLM-L6-v2` has an English WordPiece vocabulary, so a non-English item cannot be embedded until it has been translated, and clustering, signals, relevance and candidate promotion all wait behind that. See [ADR 0007](docs/adr/0007-language-packs.md).
- **Device:** `TRANSLATION_DEVICE` (added 2026-09-15). Was a hardcoded `device=-1` in both `translation.py` and `download_models.py`, which made this whole section unreachable by env var. Both sites now read the setting, and `analyse-init` is given the var alongside `STANCE_DEVICE` and `HOSTILITY_DEVICE`: pre-caching on a different device than the worker loads on raises nothing.

**Upgrade when available:**
- Model: `facebook/nllb-200-1.3B` (~5.2GB, ~3s/article on GPU)
- Model: `facebook/nllb-200-3.3B` (~13GB, ~1s/article on GPU) — best quality for Arabic/Urdu
- With GPU: `TRANSLATION_MAX_CHARS=5000` is safe (GPU handles longer sequences fast)

**Hardware needed:** RTX 3080+ (8GB VRAM for 1.3B, 16GB for 3.3B)

**Config change:**
```
TRANSLATION_MODEL=facebook/nllb-200-distilled-600M  →  TRANSLATION_MODEL=facebook/nllb-200-1.3B
TRANSLATION_MAX_CHARS=1500                          →  TRANSLATION_MAX_CHARS=5000
TRANSLATION_DEVICE=cpu                              →  TRANSLATION_DEVICE=cuda
```

`TRANSLATION_DEVICE` takes the transformers device strings, so `cuda:1` names a card on a multi-GPU host.

**Code change:** Zero. `analyst/translation.py` and `analyst/download_models.py` both read `settings.translation_device`.

Both images pin the CPU torch wheel, so `cuda` raises `Torch not compiled with CUDA enabled` until they are rebuilt against a CUDA index.
That error does not stop the worker.
`_get_pipeline()` is called inside the `try` in `translate_to_english`, so the item logs `translation.failed`, `jobs.py` logs `analyst.translation_failed_fallback`, and the pipeline continues with untranslated text.
Every subsequent item repeats the failed model load, because `_pipeline` stays `None` and nothing caches the failure.
So a device set ahead of the image rebuild degrades the corpus quietly rather than failing the deployment.
Verify a device change by reading `translation.failed`, not by watching for a crash.
A startup preflight that loads the pipeline once at worker start would make this loud, and is not implemented yet.
See Torch Wheel Variant.

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

## Stance and Hostility — `analyst-worker` service

Added for issue #28. Two models, because the measures are independent: stance is
direction toward a narrative, hostility is intensity, and neither predicts the
other. A furious post supporting a narrative and a calm post opposing it are
opposite in stance and indistinguishable to any single sentiment score.

Both are multilingual, so content is read in its own language rather than
through a translation. The existing VADER score stays as a content filter,
where a rough English-only value is acceptable because nothing alerts on it.

**Current implementation:**
- Stance: `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`, zero-shot NLI, ~560 MB, CPU
- Hostility: `textdetox/xlmr-large-toxicity-classifier`, text classification, ~2.2 GB, CPU
- Batch size: 8 each
- Speed on CPU: roughly 300 to 800ms per item for the pair
- Output: `content_items.stance` and `content_items.hostility` columns

Cost is bounded by `STANCE_MIN_CLUSTER_SIZE`: only clusters at or above it are
scored, because a timeline is only drawn where there is something to draw.
`STANCE_MIN_CLUSTER_SIZE` must stay at or below `PROMOTION_MIN_ITEM_COUNT`, or a
promoted Topic arrives with no stance data and its timeline renders empty. That
is an invariant test rather than a note.

**Upgrade path (GPU):**
- `STANCE_DEVICE=cuda`, `HOSTILITY_DEVICE=cuda`
- `STANCE_BATCH_SIZE=32`, `HOSTILITY_BATCH_SIZE=32`
- `STANCE_MODEL=MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` still
  fits comfortably; on a 24 GB card `joeddav/xlm-roberta-large-xnli` is the
  quality step up
- `STANCE_MIN_CLUSTER_SIZE` can drop to 2 once inference is cheap, which
  extends the timeline to smaller narratives

**Config change:** env vars only.
**Code change:** None.

---

## Torch Wheel Variant - `analyst` and `vision` services

Both services install torch from the PyTorch CPU index rather than from PyPI:

```dockerfile
RUN uv pip install --system torch --index-url https://download.pytorch.org/whl/cpu
```

The default PyPI torch wheel declares the CUDA runtime as hard dependencies.
That was once an x86_64-only problem, but current torch ships CUDA-enabled aarch64 wheels too, so an ARM CPU-only host pulls them as well.
Measured in this repo: `nvidia-cuda-runtime`, `nvidia-cudnn`, `nvidia-curand`, `nvidia-nvjitlink`, `nvidia-nvshmem-cu13` and `triton`, roughly 10 GB of wheels that cannot execute without a GPU.
The analyst image reached 9.93 GB, most of it dead weight, and two consecutive builds died with `No space left on device` after filling a 60 GB Docker VM disk.

This is a build-time packaging choice, not a runtime device string, so it does not weaken the hardware independence rule.
`STANCE_DEVICE`, `HOSTILITY_DEVICE` and `VISION_DEVICE` still come from env vars.
A CPU wheel raises `Torch not compiled with CUDA enabled` when one of them is set to `cuda`, which is the loud failure the rule wants, not a silent fallback to CPU.

**Upgrade path (GPU):**
- Change `--index-url` to the CUDA build matching the host driver, for example `https://download.pytorch.org/whl/cu124`, in `services/analyst/Dockerfile` and `services/vision/Dockerfile`
- Rebuild both images
- Then set the device env vars listed in the summary checklist below

**Config change:** None.
**Code change:** One line per Dockerfile, plus an image rebuild.

---

## Production Node Sizing (2026-09-15)

Derived from the re-measurement above rather than from the tier table at the top of this file.
The tier table sizes a class of machine; this section sizes the one node a deployment actually buys.

### Why the GPU decision is architectural, not a throughput preference

Translation is on the embedding critical path.
A non-English item cannot be embedded until NLLB has rendered it into English, because `all-MiniLM-L6-v2` reads an English WordPiece vocabulary, and NLLB generates autoregressively.
So the whole downstream pipeline, clustering through candidate promotion, waits on a 600M-parameter generation for every non-English item.

For an Indian-language OSINT deployment that is the majority of the corpus.
Measured on the development deployment's largest Topic: `hi=436, en=426`.
At that mix a CPU node tops out near 1,500 to 2,000 articles/day, against a production target of 10K.

This is the reason a GPU is mandatory rather than merely faster.
It is also the reason [ADR 0007](docs/adr/0007-language-packs.md) treats the embedding model and its calibrated thresholds as one versioned pack: a multilingual embedding model would take translation off the critical path entirely and change this sizing.

### Recommended node

Single node, on-premise.
Architectural rule 10 forbids a cloud LLM with real intel data, so this is an appliance rather than a cloud shape.

| | Spec | Reason |
|---|---|---|
| GPU | 1x L4 24GB (rack) or RTX 4090 24GB (appliance) | See VRAM budget below |
| CPU | 16 cores | Playwright, postgres, and the 90% of report generation that is SQL rather than LLM |
| RAM | 64 GB | Container limits already sum to ~27 GB, leaving nothing for postgres page cache on a 32 GB host |
| Storage | 2 TB NVMe, database on a volume separate from Docker | See storage budget below |

### VRAM budget, and why not to buy for a 72b model

`docs/gpu_reference.md` already contains the decision:

| GPU | Ollama model | Remaining for everything else |
|---|---|---|
| 24 GB | `qwen3:32b` (~22 GB) | ~2 GB, tight |
| 24 GB | `qwen3:14b` (~11 GB) | ~13 GB, comfortable |

Take the comfortable row.
`qwen3:72b` needs ~48 GB, which forces a dual-GPU or A100 build, and the LLM is not the quality bottleneck: report generation is roughly 90% SQL and 10% LLM.
Spending the VRAM on translation buys more than spending it on a larger language model.

The 13 GB that `qwen3:14b` leaves covers the analyst stack with room:

| Model | VRAM at fp16 |
|---|---|
| `facebook/nllb-200-1.3B` | ~2.6 GB |
| `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` (stance) | ~0.6 GB |
| `textdetox/xlmr-large-toxicity-classifier` (hostility) | ~2.2 GB |
| `BAAI/bge-large-en-v1.5` (embeddings) | ~1.3 GB |
| Total | ~7 GB |

Expected effect on the bottleneck: translation falls from 45 to 70s per article to roughly 3s, so the CPU ceiling of ~1,500/day becomes ~10,000/day, and `TRANSLATION_MAX_CHARS` can go from 1500 to 5000.
That last change matters for quality as well as speed: the 1500-char clamp currently truncates long articles, so part of the measured CPU speed is work not being done.

### Memory limits to change

Current `mem_limit` values in `infra/compose.yml` sum to ~23.9 GB for the application stack and ~26.7 GB with the observability profile.
Three are wrong, each with evidence from a real failure rather than from a model:

| Container | Now | Change to | Evidence |
|---|---|---|---|
| `analyse-worker` | ~~6g~~ 12g | done 2026-09-15; revert to 6g once on GPU | `anon-rss:6270008kB` at kill, 12 kills in 15 hours |
| `scrape-web-worker` | 3g | 6g | 2.469 GiB resident at 82% of limit, 6 `headless_shell` OOM kills |
| `postgres` | 1g | 8g | The HNSW graph is resident, and `HNSW_M=32` is the production target |

64 GB of host RAM also buys `ANALYST_WORKER_REPLICAS=2` to 4, which `compose.yml` already supports with zero code change.

### Storage budget

Measured on the development deployment:

| Item | Size |
|---|---|
| Docker images | 24.8 GB |
| `anveshak_analyst_models` volume | 6.75 GB |
| `anveshak_ollama_models` volume | 4.43 GB |
| `anveshak_vision_models` volume | 2.96 GB |
| Database | 153 MB at ~2,400 content items |

The database works out to about 64 KB per content item including the 384-dimension vector and its indexes.
Upgrading to `bge-large-en-v1.5` takes the vector from 384 to 1024 dimensions, so budget ~100 KB per item.
One million items is then ~100 GB before the HNSW graph.

2 TB, because the fixed costs are larger than the table suggests.
CUDA torch wheels take the images to roughly 40 GB, GPU models to roughly 20 GB (`qwen3:14b` at 9 GB, NLLB-1.3B at 5.2 GB), and on top of those sit the database, YouTube video at `YOUTUBE_MAX_VIDEO_SIZE_MB=500` per file, and the JSONL archives written before any retention purge.

Put the database on its own volume.
A Docker image pull must not be able to fill the disk postgres is writing to.
This has already happened once: two consecutive builds died with `No space left on device` after filling a 60 GB Docker VM disk. See Torch Wheel Variant.

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

# Translation — upgrade to higher-quality model, and move it off the CPU
TRANSLATION_MODEL=facebook/nllb-200-1.3B
TRANSLATION_DEVICE=cuda
TRANSLATION_MAX_CHARS=5000

# Vision — enable GPU + better models
VISION_DEVICE=cuda
YOLO_MODEL_SIZE=xlarge
VISION_DEEPFAKE_VIDEO_MODEL=dire
CLIP_MODEL_NAME=openai/clip-vit-large-patch14

# Stance and hostility — enable GPU
STANCE_DEVICE=cuda
STANCE_BATCH_SIZE=32
HOSTILITY_DEVICE=cuda
HOSTILITY_BATCH_SIZE=32
# Cheap inference lets the timeline cover smaller narratives
STANCE_MIN_CLUSTER_SIZE=2

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
The one exception is the torch wheel index, which is a build-time choice rather than an env var.
See the Torch Wheel Variant section above.

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
