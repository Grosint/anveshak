# Production Validation Plan: 7-10 Day Real-World Monitoring

## Context

Anveshak's codebase is **frozen as of 2026-05-10**. No code changes for 10-12 days.
Current state: Leiden community detection (threshold 0.70) is live, real HuggingFace
deepfake models deployed (facetorch + efficientnet), RBAC + audit trail enforced,
UX overhaul complete (ScheduleManager, Analytics Dashboard, Settings page).

We've never tested with **live, continuous, real-world data**. This 7-10 day production
validation will:
1. Deploy the frozen codebase on an AWS VM
2. Monitor real defence/security topics with real sources
3. Measure actual recall/precision against ground-truth events
4. Identify pipeline failures, silent drops, and robustness issues
5. Generate daily reports for morning review sessions

**Key constraint:** No manual data insertion. Everything flows through the real pipeline:
scrape → NLP → clustering → signals → reports. No code changes during validation —
issues are logged and fixed after the trial.

---

## VM Deployment (AWS g4dn.2xlarge)

### Instance Spec

| Spec | Value |
|------|-------|
| Instance | g4dn.2xlarge |
| GPU | NVIDIA T4 16GB VRAM |
| CPU | 8 vCPU |
| RAM | 32 GB |
| Storage | 200 GB EBS gp3 |
| OS | Ubuntu 22.04 LTS (Deep Learning AMI — Docker + NVIDIA pre-installed) |
| Cost | ~$0.75/hr × 240h = ~$180 (on-demand) |

### Why GPU

- Ollama report gen: ~30s/report (vs ~3 min on CPU)
- Vision deepfake/YOLO/CLIP: seconds per image (vs minutes on CPU)
- NLLB translation: ~15s/article (vs ~4 min on CPU)
- 4 daily scheduled reports + ad-hoc + 100-200 articles/day with non-English content

### Setup Steps (one-time, ~20 min)

```bash
# 1. Launch g4dn.2xlarge with 200GB gp3 EBS
#    Security group: 22 (your IP), 3000 (analyst network), 8000 (API)
#    Use Deep Learning AMI (Docker + NVIDIA Container Toolkit pre-installed)

# 2. SSH in, verify GPU and Docker
ssh -i key.pem ubuntu@<VM_IP>
nvidia-smi                    # T4 visible
docker compose version        # v2+ required

# 3. Clone and configure
git clone <repo-url> anveshak && cd anveshak
cp .env.example .env

# 4. Edit .env — set these mandatory values:
#    POSTGRES_PASSWORD=<openssl rand -hex 16>
#    API_SECRET_KEY=<openssl rand -hex 32>
#    GRAFANA_ADMIN_PASSWORD=<secure-password>
#    VISION_DEVICE=cuda
#    OLLAMA_KEEP_ALIVE=-1              (GPU keeps model resident)
#    TELEGRAM_API_ID=<your-id>
#    TELEGRAM_API_HASH=<your-hash>
#    TELEGRAM_SESSION_STRING=<your-session>
#    TELEGRAM_ADAPTER_ENABLED=true
#    X_BEARER_TOKEN=<your-token>
#    X_ADAPTER_ENABLED=true
#    X_MONTHLY_READ_CAP=10000

# 5. Full automated setup (~15 min)
make setup    # builds images, starts containers, runs migrations, pulls qwen2:7b

# 6. Verify
make health                   # all 23 containers healthy
make ps                       # status table
nvidia-smi                    # GPU utilisation visible

# 7. Run setup script to create topics and sources
python scripts/setup_production_topics.py
```

### Security

- SSH key-based auth only (no password login)
- Security group: port 22 (your IP only), 3000+8000 (analyst network)
- Grafana (3001) and Prometheus (9090) restricted to your IP only
- Sovereign: Ollama on localhost inside Docker network, no outbound LLM calls
- All secrets in `.env`, never committed to git

### Daily Operations (on VM)

```bash
make ps                            # Container status
make health                        # All-service health check
python scripts/pipeline_health.py  # Full pipeline diagnostics
make logs-<service>                # Tail specific service logs

# Backup (run before any changes)
make backup BACKUP_DIR=./backups/$(date +%Y%m%d)

# Monitor disk
df -h /var/lib/docker
docker system df
```

### If Something Breaks

```bash
make restart                       # Restart all containers
docker compose -p anveshak logs --tail=200 <service>
# Code is FROZEN — log the issue, don't fix on VM
# Track in docs/production_validation_log.md
```

---

## Phase 1: Topic & Source Setup

### 4 Topics (Indian Defence Analyst Perspective, May 2026)

**Topic 1: India-China LAC Military Posturing**
The LAC remains India's primary conventional threat. PLA infrastructure build-up, troop rotations, and exercises near Aksai Chin/Depsang are continuous.

```
name: "India-China LAC Military Posturing"
keywords: ["LAC", "Line of Actual Control", "Ladakh", "Aksai Chin", "Depsang", "PLA", "India China border", "Galwan", "Pangong", "Arunachal", "Tawang", "Chinese military", "India China standoff", "eastern Ladakh", "border infrastructure"]
languages: ["en", "hi", "zh"]
signal_threshold: 2
credibility_min: 30.0
scheduled_report_cron: "0 3 * * *"    # 8:30 AM IST daily
scheduled_report_type: "intelligence_brief"
```

**Topic 2: Pakistan Cross-Border Terrorism & LoC Violations**
Post-Pahalgam attack (Apr 2026) tensions remain elevated. Arms smuggling via drones, ceasefire violations, and terror financing are active threats.

```
name: "Pakistan Cross-Border Terror & LoC Activity"
keywords: ["LoC", "Line of Control", "Kashmir", "cross-border", "infiltration", "ceasefire violation", "Pakistan terrorism", "LeT", "JeM", "Jaish", "Lashkar", "IED", "encounter", "Pulwama", "Pahalgam", "drone smuggling", "terror funding", "FATF Pakistan"]
languages: ["en", "hi", "ur"]
signal_threshold: 2
credibility_min: 30.0
scheduled_report_cron: "0 3 * * *"
scheduled_report_type: "intelligence_brief"
```

**Topic 3: Indian Ocean Region — Maritime Security & Chinese Naval Expansion**
China's naval presence in IOR (Hambantota, Djibouti, dual-use ports) and submarine deployments are a strategic concern for Indian Navy.

```
name: "Indian Ocean Maritime Security & Chinese Naval Presence"
keywords: ["Indian Ocean", "IOR", "South China Sea", "Chinese navy", "PLA Navy", "Hambantota", "String of Pearls", "Djibouti", "submarine", "Indian Navy", "INS", "Quad naval", "Malabar exercise", "maritime surveillance", "PLAN", "aircraft carrier", "Andaman Nicobar"]
languages: ["en", "hi"]
signal_threshold: 2
credibility_min: 30.0
scheduled_report_cron: "0 3 * * *"
scheduled_report_type: "intelligence_brief"
```

**Topic 4: Disinformation & Influence Operations Targeting India**
Deepfakes, AI-generated content, and coordinated campaigns targeting Indian military/elections.

```
name: "Disinformation & Info Ops Targeting India"
keywords: ["deepfake India", "disinformation India", "fake news military", "propaganda India", "influence operation", "information warfare", "AI generated", "manipulated media", "fact check India", "ISPR propaganda", "anti-India narrative", "social media manipulation", "coordinated inauthentic"]
languages: ["en", "hi"]
signal_threshold: 2
credibility_min: 25.0
scheduled_report_cron: "0 3 * * *"
scheduled_report_type: "intelligence_brief"
```

### Sources Per Topic (focus on RSS for reliable continuous content)

We need **3+ distinct platforms per topic** for ISC to hit threshold. Strategy: heavy RSS (reliable, continuous, no auth needed) + web + social where available.

#### Tier 1: RSS Feeds (platform: "rss") — No auth, reliable, high volume
| Source | URL | Credibility | Topics |
|--------|-----|-------------|--------|
| Reuters World | `https://feeds.reuters.com/reuters/worldNews` | 85 | All 4 |
| Al Jazeera | `https://www.aljazeera.com/xml/rss/all.xml` | 72 | All 4 |
| NDTV India | `https://feeds.feedburner.com/ndtvnews-india-news` | 70 | 1,2,4 |
| The Hindu Defence | `https://www.thehindu.com/news/national/feeder/default.rss` | 78 | 1,2,3 |
| Times of India | `https://timesofindia.indiatimes.com/rssfeeds/296589292.cms` | 65 | 1,2,4 |
| Dawn (Pakistan) | `https://www.dawn.com/feeds/home` | 55 | 2 |
| South China Morning Post | `https://www.scmp.com/rss/91/feed` | 74 | 1,3 |
| The Diplomat | `https://thediplomat.com/feed/` | 80 | 1,3 |
| Defense News | `https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml` | 82 | 1,2,3 |
| BBC World | `https://feeds.bbci.co.uk/news/world/rss.xml` | 88 | All 4 |
| Livemint | `https://www.livemint.com/rss/news` | 68 | 1,2,4 |

#### Tier 2: Web Sources (platform: "web") — Crawled by Crawl4AI
| Source | URL | Credibility | Topics |
|--------|-----|-------------|--------|
| GlobalSecurity.org | `https://www.globalsecurity.org` | 82 | 1,2,3 |
| Indian Defence Research Wing | `https://idrw.org` | 60 | 1,2 |
| Janes | `https://www.janes.com` | 91 | 1,3 |
| The Wire | `https://thewire.in` | 65 | 2,4 |
| OSINT aggregator: Bellingcat | `https://www.bellingcat.com` | 85 | 4 |
| India Today | `https://www.indiatoday.in` | 62 | 1,2,4 |

#### Tier 3: Social — Telegram (session available) + X/Twitter (credentials available)
| Source | Handle | Platform | Credibility | Topics |
|--------|--------|----------|-------------|--------|
| Telegram: Defence Updates | `@defence_updates` | telegram | 38 | 1,2 |
| Telegram: Indian OSINT | `@indian_osint` | telegram | 42 | 1,2,4 |
| Telegram: China Military Watch | `@china_military` | telegram | 40 | 1,3 |
| X: India defence keywords | (keyword search) | twitter | 35 | All 4 |

**NOTE: Reddit credentials not available currently — skip Reddit sources.**

**Platform diversity per topic:**
- Topic 1 (LAC): ~8 RSS + ~4 web + telegram + X = 4 platforms
- Topic 2 (LoC): ~7 RSS + ~3 web + telegram + X = 4 platforms
- Topic 3 (IOR): ~6 RSS + ~3 web + telegram + X = 4 platforms
- Topic 4 (Disinfo): ~6 RSS + ~3 web + telegram + X = 4 platforms

ISC of 2 is easily achievable with RSS + web. Telegram and X add ISC 3-4.

---

## Pre-requisite: Compose Config Fixes (DONE)

The following compose config issues were identified and **fixed**:

1. **Social service** — Reddit and Bluesky adapter env vars were missing from compose.
   Added: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`, `REDDIT_ADAPTER_ENABLED`,
   `BLUESKY_HANDLE`, `BLUESKY_PASSWORD`, `BLUESKY_ADAPTER_ENABLED`, `X_ADAPTER_MODE`,
   `POLL_INTERVAL_S`, `METRICS_PORT`. Telegram and X vars were already present.

2. **Orphaned Instagram vars** — `INSTAGRAM_USERNAME` and `INSTAGRAM_PASSWORD` were in compose
   but no Instagram adapter exists. Removed.

3. **Dead HDBSCAN vars** — Replaced with `CLUSTERING_SIMILARITY_THRESHOLD` and
   `CLUSTERING_MIN_CLUSTER_SIZE` (Leiden community detection).

4. **Env var pre-flight check** — `make up` runs `scripts/check_env.sh` which parses
   compose files for required vars and blocks startup if any are missing from `.env`.
   Additional `scripts/check_env_sync.sh` validates bidirectional sync.

---

## Phase 2: Pipeline Diagnostics Script

### Problem
Currently, when a signal does NOT fire, there's no easy way to know why. Was it:
- Not enough content scraped?
- Content filtered by quality gate?
- Embeddings failed (NULL)?
- Clustering didn't group them?
- ISC too low?
- Signal deduplication (24h window)?

### Solution: Daily diagnostics SQL query + Python script

Create `scripts/pipeline_health.py` that runs daily (or on-demand) and outputs:

```
=== PIPELINE HEALTH REPORT (2026-05-12) ===

TOPIC: India-China LAC Military Posturing
  Content scraped (24h):     47 items
  Quality-filtered out:       3 items (content_quality != 'good')
  Embeddings NULL:            0 items (orphans)
  Relevance-filtered:         8 items (topic_relevance_score < threshold)
  Active clusters:            5
    - Cluster "PLA infrastructure Depsang": 12 items, ISC=3 ✅ SIGNAL FIRED
    - Cluster "Arunachal patrol reports":    8 items, ISC=2 ✅ SIGNAL FIRED
    - Cluster "General LAC commentary":      6 items, ISC=1 ❌ ISC below threshold
    - Cluster (unlabelled):                  4 items, ISC=1 ❌ ISC below threshold
    - Cluster (unlabelled):                  2 items, ISC=1 ❌ too few items
  Unassigned items:           9 (not in any cluster)
  Signals fired (24h):       2
  Signals deduped:           0
  Report generated:          Yes (08:30 AM IST)

DEAD LETTER QUEUE:
  analyst: 0 failed jobs
  vision:  1 failed job (deepfake_analyse — OOM on 4K image)
  reporter: 0 failed jobs

SOURCE HEALTH:
  healthy: 18    degraded: 2    down: 1

GPU UTILIZATION:
  T4: 34% memory, 22% compute

PIPELINE BOTTLENECK: 9 unassigned items → may need lower cluster_assign_threshold
```

Key diagnostics:
1. **Scrape yield**: How many items per topic per day?
2. **Quality gate losses**: How many filtered by quality/relevance?
3. **Orphaned embeddings**: Items with NULL embedding (analyse_content failed)
4. **Cluster coverage**: % of items assigned to clusters vs floating
5. **ISC distribution**: How many clusters at ISC=1, 2, 3+?
6. **Signal fire rate**: Signals fired vs eligible clusters
7. **Report success**: Did scheduled reports generate successfully?
8. **Media download yield**: Media assets downloaded vs content items with media URLs
9. **Vision job throughput**: Jobs completed/failed/pending in 24h
10. **Deepfake score distribution**: Count of scores > 0.5 (suspicious), > 0.8 (high risk)
11. **YOLO detections**: Object categories detected, count per category
12. **CLIP classifications**: Top labels assigned, confidence distribution
13. **Dead Letter Queue**: Failed jobs by queue (analyst/vision/reporter)
14. **Source health**: Circuit breaker status (healthy/degraded/down counts)
15. **GPU utilization**: T4 memory and compute usage (nvidia-smi)

**Note:** `scripts/validate_vision_full.py` (650 lines) is available for standalone vision validation
with 6 test categories (real/fake face, real/fake no-face, real/fake video) + CLIP classification.

---

## Phase 3: Setup Script

Create `scripts/setup_production_topics.py`:

1. **Authenticate** via `POST /api/v1/auth/login` → JWT token (admin role required)
2. Delete old test topics (E2E Validation, existing seed topics that overlap)
3. Create 4 new topics via API
4. Create all sources via API (with health probing)
5. Link sources to topics via API
6. Verify everything is wired: `GET /topics/{id}/sources` for each topic
7. Print summary

**Why a Python script using the API (not raw SQL)?**
- Health probing runs on source creation (validates RSS feeds work)
- `backfill_topic_job` auto-enqueues on topic creation
- Labels auto-assigned
- RBAC enforced — all mutations logged in `audit_trail` table
- Exercises the same codepath as production

**Note:** Topics and sources can also be managed via the frontend UI
(TopicsDashboard + SourceManager pages) at `http://<VM_IP>:3000`.

---

## Phase 4: Daily Review Workflow

**Schedule (for 7-10 days starting after setup):**

| Time (IST) | Action |
|-------------|--------|
| 08:30 AM | Scheduled reports auto-generate (cron: `0 3 * * *` UTC = 8:30 AM IST) |
| 09:00 AM | SSH to VM → `python scripts/pipeline_health.py` for diagnostics |
| 09:00 AM | Browse `http://<VM_IP>:3000` — check Analytics Dashboard, Signals Inbox |
| Evening  | Review: read reports, check diagnostics, discuss issues |

**Remote access:**
- Frontend: `http://<VM_IP>:3000` (analyst workbench — reports, signals, analytics charts)
- Grafana: `http://<VM_IP>:3001` (7 pre-built dashboards + Loki log aggregation)
- SSH: for `pipeline_health.py`, logs, debugging
- Scheduled reports manageable via ScheduleManager UI component (no SSH needed)

**What to track daily:**
- Total content items scraped (per topic)
- Signal count and relevance
- False positives: signals that fired on irrelevant content
- False negatives: known real-world events that Anveshak missed
- Pipeline failures: scrape errors, embedding nulls, clustering hangs
- Report quality: are LLM-generated reports coherent and sourced?
- Vision analysis: deepfake detections, suspicious media flagged (score > 0.5)
- Media pipeline: download success rate, vision job backlog, YOLO/CLIP detections
- DLQ accumulation: failed jobs that need investigation
- Source health: any sources circuit-broken (degraded/down)

**Ground truth tracking:**
Maintain a simple log (markdown file or spreadsheet) of real-world events we know happened, then check if Anveshak detected them.

---

## Phase 5: End-of-Trial Benchmark

After 7-10 days:
1. Run `scripts/pipeline_health.py --summary` for full-period stats
2. Compare detected signals against ground truth events
3. Calculate real-world recall/precision/F1
4. Identify systematic failure patterns
5. Create actionable improvement plan
6. Terminate VM (or snapshot EBS for future reference)

---

## Deliverables

| # | Deliverable | Type |
|---|-------------|------|
| 0 | VM running on g4dn.2xlarge | AWS deployment |
| 1 | `scripts/setup_production_topics.py` | New file — creates topics, sources, links |
| 2 | `scripts/pipeline_health.py` | New file — daily diagnostics |
| 3 | Topic/source data in DB | Via API calls (setup script) |
| 4 | Daily reports (auto-generated) | Via scheduled_report_cron |
| 5 | Ground truth log template | `docs/production_validation_log.md` |

---

## Risks

| Risk | Level | Mitigation |
|------|-------|------------|
| RSS feeds return 403/rate-limit | MEDIUM | Health probing on creation; monitor source_health |
| Not enough content for clustering | HIGH | Use 10+ sources per topic, focus on high-volume RSS |
| Analyst OOM with translation enabled | MEDIUM | 32GB VM; NLLB only for non-English content |
| Ollama fails report gen | VERY LOW | GPU + OLLAMA_KEEP_ALIVE=-1, model stays resident |
| Web scraping blocked (CloudFlare) | MEDIUM | Prefer RSS over web; web sources as supplement |
| Telegram channels may not exist | MEDIUM | Verify channels before adding; use known public channels |
| X API spend — pay-per-read | MEDIUM | X_MONTHLY_READ_CAP enforced; monitor Redis key |
| Clustering hangs on large corpus | LOW | 5-min cycle; monitor via diagnostics script |
| VM disk fills up (media downloads) | MEDIUM | 200GB EBS; monitor with `df -h` / Grafana node exporter |
| DLQ accumulation | LOW | Monitor via pipeline_health.py; investigate daily |
| Setup script RBAC auth | LOW | Admin credentials set in .env; script authenticates first |

---

## Decisions (Resolved)

1. **Replace** existing 3 topics entirely with 4 new production topics
2. **Reddit:** Not available — skip. **Telegram:** Session available. **X/Twitter:** Credentials available.
3. **Signal threshold:** Set to 2. Clustering uses Leiden community detection with `clustering_similarity_threshold=0.70`. Can raise to 3 later if too noisy.
4. **Report time:** 8:30 AM IST daily (`0 3 * * *` UTC)
5. **Compose config fixed** — see Pre-requisite section above
6. **Deployment:** Docker Compose on AWS g4dn.2xlarge (K3s manifests exist but not used for this validation)
7. **Content retention:** Disabled during validation (`CONTENT_RETENTION_DAYS=0`) — keep all data for analysis
8. **RBAC roles:** Admin creates topics/sources via setup script; analyst role for daily review
9. **Code freeze:** No changes during 10-12 day validation — issues logged, fixed after trial
