# Production Validation — Scripts Reference & Daily Operations

## Daily Morning Check (Phase 4)

| Script | What it does | When to run |
|--------|-------------|-------------|
| `pipeline_health.py` | Full diagnostics — content counts, clusters, signals, DLQ, source health, deepfake stats | Every morning + anytime you want a status check |
| `pipeline_health.py --summary` | Same but all-time stats (not just 24h) | End of trial (Phase 5 benchmark) |
| `pipeline_health.py --hours 48` | Last 48 hours of data | When you missed a day |
| `pipeline_health.py --topic "LAC"` | Filter to one topic by name substring | When investigating a specific topic |

## One-Time Setup (already done)

| Script | What it does | Status |
|--------|-------------|--------|
| `setup_production_topics.py` | Creates 4 topics + 21 sources + links them via API | DONE |
| `setup_production_topics.py --dry-run` | Shows what would be created without calling API | For verification |
| `setup_runpod.sh` | One-command GPU VM setup (RunPod/Vast/any Linux GPU VM) | Not needed when running locally |
| `syscheck.py` | Checks RAM, disk, Docker, GPU, ports | Already ran via `make setup` |

## Validation Suites (run if something seems off)

| Script | What it does | When to run |
|--------|-------------|-------------|
| `validate_pipeline.py` | 7-stage pipeline validation (API, DB, scraper, analyst, reporter, vision, signals) | If services seem broken |
| `validate_vision.py` | Quick vision pipeline test (deepfake + pHash) | If vision scores look wrong |
| `validate_vision_full.py` | Full vision validation (6 categories, CLIP, video) — 650 lines | Deep vision debugging |
| `validate_vector.py` | Vector/HNSW/clustering validation (dedup, temporal, convergence) | If clustering seems broken |
| `demo_check.py` | 8-step demo arc verification for iDEX ADITI reviewers | Before demos |

## Source Connectivity (run if content stops flowing)

| Script | What it does | When to run |
|--------|-------------|-------------|
| `test_scrape.py` | Orchestrator — tests RSS + web + social connectivity inside containers | If scraper shows 0 content |
| `test_scrape_sources.py` | Tests each RSS/web source individually | Debugging a specific source |
| `test_scrape_social.py` | Tests Telegram + X connectivity | If social adapters fail |

## ML Model Tests (run inside containers via docker exec)

| Script | What it does | When to run |
|--------|-------------|-------------|
| `test_analyst_models.py` | Tests spaCy NER, embeddings, VADER sentiment, NLLB translation | If NLP/embedding seems broken |
| `test_vision_models.py` | Tests YOLO, CLIP, deepfake detectors against real models | If vision scores are wrong |
| `test_ollama_models.py` | Tests Ollama LLM inference inside reporter-worker | If reports fail to generate |
| `test_multilingual_pipeline.py` | Tests NER + translation + clustering end-to-end | If non-English content drops |

## Backup & Restore

| Script | What it does | When to run |
|--------|-------------|-------------|
| `backup.sh` | pg_dump + media archive to timestamped directory | Before any risky changes |
| `restore.sh` | Restore database + media from a backup directory | If you need to recover |

## Maintenance Scripts (not needed during validation)

| Script | Purpose |
|--------|---------|
| `backfill_clean_text.py` | Backfill missing clean_text on old content_items rows |
| `backfill_quality_and_titles.py` | Backfill quality scores and titles on pre-migration rows |
| `regenerate_cluster_labels.py` | Re-label narrative clusters via LLM (useful after threshold tuning) |
| `seed_chinese_sources.py` | Add Chinese news sources for Topic 1 (LAC) |
| `verify_labels.py` | Verify all Pydantic models have mandatory `labels` field |
| `verify_reports_immutable.py` | Verify report immutability rule (generated_at never updated) |
| `check_env.sh` | Env var preflight check (runs automatically on `make up`) |
| `check_env_sync.sh` | Bidirectional sync between .env and .env.example |
| `gen_demo_password.py` | Generate bcrypt hash for demo account password |
| `gen_telegram_session.py` | Generate Telegram session string from API credentials |
| `bootstrap_telegram_session.py` | Interactive Telegram session bootstrap (requires phone auth) |
| `download_models.py` | Download vision models — YOLO, CLIP, deepfake ONNX (runs via `make setup`) |
| `regen_summaries_openai.py` | Regenerate summaries via OpenAI (not used — we use Ollama) |

---

## Daily Cheat Sheet

```bash
# === MORNING CHECK (1 min) ===
python3 scripts/pipeline_health.py

# === QUICK STATUS ===
make ps                                        # Container status
make health                                    # Service health (10 endpoints)

# === MONITOR LOGS ===
make logs-scraper                              # Scraper activity
make logs-analyst                              # Analyst/clustering/signals
make logs-reporter                             # Report generation
make logs                                      # All services

# === IF SOMETHING LOOKS WRONG ===
make health                                    # Are services up?
uv run python3 scripts/validate_pipeline.py    # Full 7-stage validation

# === IF CONTENT STOPS FLOWING ===
make logs-scraper                              # Check scraper activity
uv run python3 scripts/test_scrape_sources.py  # Test source connectivity

# === IF CLUSTERS/SIGNALS SEEM OFF ===
uv run python3 scripts/validate_vector.py      # Check clustering pipeline

# === IF VISION SEEMS BROKEN ===
uv run python3 scripts/validate_vision.py      # Quick vision check

# === END OF TRIAL (Phase 5 benchmark) ===
python3 scripts/pipeline_health.py --summary   # Full-period stats

# === BACKUP (before any changes) ===
bash scripts/backup.sh ./backups/$(date +%Y%m%d)
```

---

## 4 Production Topics — What to Monitor

### Topic 1: India-China LAC Military Posturing
- **Keywords:** LAC, Ladakh, Aksai Chin, Depsang, PLA, Galwan, Pangong, Arunachal, Tawang
- **Languages:** en, hi, zh
- **Sources:** 17 (9 RSS, 3 web, 3 Telegram, 1 X)
- **Watch for:** PLA infrastructure build-up, troop rotations, exercises near Aksai Chin/Depsang
- **Signal threshold:** ISC >= 2
- **Report:** Daily at 08:30 AM IST

### Topic 2: Pakistan Cross-Border Terror & LoC Activity
- **Keywords:** LoC, Kashmir, infiltration, ceasefire, LeT, JeM, Pahalgam, drone smuggling
- **Languages:** en, hi, ur
- **Sources:** 15 (9 RSS, 3 web, 2 Telegram, 1 X)
- **Watch for:** Infiltration attempts, ceasefire violations, drone smuggling, terror financing
- **Signal threshold:** ISC >= 2
- **Report:** Daily at 08:30 AM IST

### Topic 3: Indian Ocean Maritime Security & Chinese Naval Presence
- **Keywords:** IOR, South China Sea, PLA Navy, Hambantota, submarine, Malabar exercise
- **Languages:** en, hi
- **Sources:** 10 (7 RSS, 2 web, 1 Telegram)
- **Watch for:** Chinese submarine deployments, Hambantota activity, dual-use ports
- **Signal threshold:** ISC >= 2
- **Report:** Daily at 08:30 AM IST

### Topic 4: Disinformation & Info Ops Targeting India
- **Keywords:** deepfake India, disinformation, propaganda, influence operation, ISPR, AI generated
- **Languages:** en, hi
- **Sources:** 10 (6 RSS, 3 web, 1 Telegram)
- **Watch for:** Deepfakes targeting military, coordinated campaigns, manipulated media
- **Signal threshold:** ISC >= 2
- **Report:** Daily at 08:30 AM IST

---

## Pipeline Flow (how content becomes a signal)

```
Source (RSS/web/social)
  → Scraper (fetch + extract clean_text + content_hash dedup)
    → Analyst Worker (NLP: language detect → translate → NER → embed → quality score)
      → Analyst Scheduler (relevance gate → cluster via Leiden → compute ISC)
        → Signal Engine (ISC >= threshold → fire signal → WebSocket push)
          → Reporter (RAG context → LLM generate → Pydantic validate → PDF)
```

### Why content might not become a signal
1. **Quality filtered** — content_quality = 'low_quality' (too short, boilerplate)
2. **Relevance filtered** — topic_relevance_score < 0.35 (off-topic for this topic)
3. **Not clustered** — no similar content to group with (isolated article)
4. **ISC too low** — cluster has content from only 1 platform (need 2+)
5. **Signal dedup** — same cluster already fired a signal in the last 24h

### Typical timeline
- **Minutes 0-5:** Scraper fetches content from sources
- **Minutes 5-10:** Analyst worker processes NLP (embed, NER, quality)
- **Minutes 10-15:** Analyst scheduler runs clustering cycle
- **Minutes 15-20:** Signals fire if ISC threshold met
- **Daily 08:30 IST:** Scheduled report generates via Ollama LLM

---

## Makefile Quick Reference

```bash
# Lifecycle
make up                   # Start full stack
make down                 # Stop all containers
make restart              # Restart all containers
make ps                   # Container status table
make health               # Quick health check

# Logs
make logs                 # Tail all logs
make logs-scraper         # Scraper logs
make logs-analyst         # Analyst logs
make logs-reporter        # Reporter logs
make logs-vision          # Vision logs
make logs-social          # Social adapter logs

# Validation
make validate             # Full 7-stage pipeline validation
make validate-vision      # Vision pipeline validation
make validate-vector      # Vector/clustering validation
make validate-all         # All three validation suites

# Testing
make test-unit            # Unit tests (< 30s)
make test-integration     # Integration tests (< 5min, requires stack)
make test-scrape          # Source connectivity tests (needs internet)
make test-e2e             # End-to-end tests (requires full stack + seeded data)

# Database
make migrate              # Run Alembic migrations
make seed-demo            # Load Indian Navy demo scenario
```
