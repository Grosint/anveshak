# Anveshak — LLM Briefing Prompt

> Paste this into any conversation to give an LLM full context on Anveshak.

---

## What is Anveshak?

Anveshak (Sanskrit: investigator) is a **standalone, sovereign AI-OSINT analysis and monitoring platform** for Indian defence forces and law enforcement agencies. Built under iDEX ADITI 4.0 PS-18. It runs entirely on one machine — no cloud dependencies. Intelligence data never leaves the deployment boundary.

**Product strategy:** Anveshak sells first. Drishti (entity resolution platform) is the upsell. Anveshak never depends on Drishti.

## What it does (5 modules)

| Module | What | How |
|--------|------|-----|
| **M1** | Source credibility scoring | 3 auto-scoring passes (deepfake amplification, cross-verification, contradiction), immutable audit log |
| **M2** | Web crawling + NLP | Crawl4AI + trafilatura, spaCy NER (en/ru/zh), NLLB-200 translation, sentence-transformer embeddings (384d), Leiden narrative clustering, entity MinHash |
| **M3** | Social media collection | Telegram (Telethon), Reddit (PRAW), Bluesky (atproto), X/Twitter (tweepy, pay-per-use with spend guard) |
| **M4** | Image/video analysis | YOLOv8 object detection, CLIP zero-shot classification, face deepfake (ViT ONNX), non-face deepfake (Swin ONNX), EXIF extraction, pHash reverse lookup |
| **M5** | Report generation | RAG over pgvector embeddings, Ollama qwen2:7b, Pydantic-validated output, offline geocoding, PDF export, scheduled cron reports |

**Cross-cutting:** Signal engine fires when N independent platforms corroborate a narrative. Cross-topic convergence detection. Real-time WebSocket push to analyst sessions.

## Tech stack

```
Backend:   Python 3.12, FastAPI, Pydantic v2 (strict), asyncpg, ARQ (Redis queue)
Database:  PostgreSQL 16 + pgvector (384d HNSW), 18 tables
LLM:       Ollama (local only, sovereign requirement) + LiteLLM
NLP:       spaCy 3, NLLB-200, sentence-transformers, VADER, YAKE
Vision:    YOLOv8, CLIP, Facetorch, EfficientNet (all ONNX)
Frontend:  React + TypeScript + Vite + Tailwind + MapLibre GL
Infra:     Docker Compose (23 containers, dev), k3s (14 manifests, prod)
Observe:   Prometheus (11 alert rules) + Alertmanager + Grafana (8 dashboards) + Loki + Promtail
Tests:     974 Python (pytest) + 171 frontend (vitest) = 1145 total
```

## Architecture (data flow)

```
Internet (websites, RSS, Telegram, Reddit, Bluesky, X)
    │
    ▼
scraper + social ──► content_items (SHA-256 deduplicated)
    │                     │
    ▼                     ▼
PostgreSQL ◄──── analyst (spaCy NER, NLLB translation, embeddings,
    │              Leiden clustering, signal engine, convergence)
    │                     │
    ▼                     ▼
reporter (RAG + Ollama) ──► immutable reports + GeoJSON + PDF
    │
    ▼
API gateway (FastAPI, JWT + RBAC, WebSocket signals) ──► React frontend
```

## Key architectural rules

1. **Standalone-first** — no Kafka, Vault, Keycloak, or Drishti required
2. **All LLM calls are async** — dispatched as ARQ jobs, never inline in routes
3. **Content dedup mandatory** — SHA-256 hash, ON CONFLICT DO NOTHING
4. **Reports are immutable** — `generated_at` set once, never updated
5. **Hardware independence** — all model names, device strings, batch sizes from env vars
6. **Deepfake scores are float 0.0-1.0** — never boolean
7. **No cloud LLM with real data** — Ollama on localhost/Docker only
8. **LLM output is Pydantic-validated** — raw strings never stored
9. **Credibility changes are audit-logged** — every score change inserts audit row
10. **Labels mandatory** — every Pydantic model has `labels: Labels` (never Optional)

## Security model

- **RBAC:** 3 roles (admin / analyst / viewer) enforced on every route via `require_role()`
- **JWT:** tokens include `role` + `jti` (unique ID for revocation)
- **Token revocation:** `POST /auth/logout` adds jti to Redis blocklist
- **Audit trail:** 17 mutating actions logged (user_id, IP, action, details, timestamp)
- **Headers:** CSP, HSTS (optional), X-Frame-Options, X-Content-Type-Options
- **Rate limiting:** 4-tier sliding window (login 10/min, vision 30/min, auth 120/min, anon 60/min)
- **CORS:** explicit method list, configurable origins

## Database (18 tables)

Core: `users`, `topics`, `sources`, `content_items`, `extracted_entities`, `narrative_clusters`, `near_duplicates`, `signals`, `reports`, `media_assets`, `vision_results`, `credibility_audit_log`, `report_source_warnings`, `topic_content_items`, `topic_sources`, `analysis_jobs`

Production audit additions: `token_blocklist`, `audit_trail`, `failed_jobs`

## Container map (23 containers)

postgres, redis, ollama, api, scraper, scraper-worker, social, analyst-scheduler (512MB), analyst-worker (6GB), reporter, reporter-worker, vision-init, vision, vision-worker, frontend, prometheus, alertmanager, grafana, loki, promtail, postgres-exporter, redis-exporter, cadvisor, tor-proxy

## K3s production (14 manifests)

namespace, secrets, postgres, redis, api (+ PDB), analyst, ollama (8Gi, model PVC), scraper, reporter, vision (media + model PVCs), frontend, ingress (Traefik), networkpolicy (default-deny + 5 allows), kustomization

All pods: `runAsNonRoot`, `allowPrivilegeEscalation: false`, `livenessProbe` + `readinessProbe`

## Key directories

```
services/api/          FastAPI gateway, auth/rbac.py, routes/, db/, middleware/
services/scraper/      Crawl4AI, trafilatura, PDF extraction, robots.txt, health
services/social/       Telegram/Reddit/Bluesky/X adapters, circuit breaker
services/analyst/      NLP pipeline, Leiden clustering, signal engine, convergence
services/reporter/     RAG, Ollama LLM, geocoder, PDF, circuit breaker
services/vision/       YOLO, CLIP, deepfake (face/non-face), EXIF, pHash
frontend/src/          React pages, components, hooks, api modules
infra/                 compose.yml, k3s/, configs/ (prometheus, alertmanager, grafana, loki)
tests/                 unit/ (974), integration/, e2e/, contracts/
```

## Useful commands

```bash
make up                    # start all 23 containers
make ps                    # check health
make migrate               # run Alembic migrations
make test-unit             # 974 Python tests (~14s)
make test-frontend         # 171 vitest tests (~2s)
make check-env-sync        # verify .env matches .env.example
make validate              # 7-stage live pipeline validation
make demo-check            # 8-step demo arc
```

## What Anveshak is NOT

- Not an entity resolution platform (that's Drishti)
- Not a graph database (flat PostgreSQL only)
- Not cloud-dependent (sovereign, air-gap capable)
- Not a general-purpose scraper (OSINT analysis with intelligence output)
