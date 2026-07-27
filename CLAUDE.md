# ANVESHAK — AI-POWERED OSINT ANALYSIS PLATFORM

Read before touching. Rules non-negotiable.

## WHAT ANVESHAK IS

Standalone sovereign AI-OSINT analysis+monitoring platform for defence forces and LEAs. Built under iDEX ADITI 4.0 PS-18. Separate product from Drishti.

**Product strategy:** Sell Anveshak first. Drishti = upsell.
Deploys standalone — no Redpanda, no AGE, no Vault.
One machine per intelligence officer.

## TECH STACK — CANONICAL (DO NOT DEVIATE)

- Language: Python 3.12 (backend), TypeScript (frontend)
- API: FastAPI + Pydantic v2 strict mode
- Database: PostgreSQL 16 + pgvector extension
- Task queue: Redis + ARQ (async Redis Queue)
- LLM runtime: Ollama + LiteLLM abstraction layer
- NLP: spaCy 3 (multi-language) + sentence-transformers
- Vision: YOLOv8 + CLIP + Facetorch + DIRE (ONNX)
- Web scraping: Crawl4AI + trafilatura
- Social: Telethon (Telegram), PRAW (Reddit), atproto (Bluesky), tweepy (X/Twitter)
- Frontend: React + TypeScript + Vite + MapLibre GL
- Observability: Prometheus + structlog + OpenTelemetry
- Package manager: uv workspace
- Containers: Docker Compose (dev), k3s (prod)

## ARCHITECTURAL RULES — ALWAYS ENFORCE

1. **Standalone-first.** Every service starts with ANVESHAK_DRISHTI_BRIDGE=false. Anveshak NEVER requires Drishti.

2. **Labels mandatory.** Every Pydantic model MUST have `labels: Labels`. NEVER Optional. Never create model without.

3. **Content dedup mandatory.** Every ContentItem MUST have `content_hash` (SHA-256 normalised clean_text). All inserts use ON CONFLICT(content_hash) DO NOTHING.

4. **Reports immutable.** Once `generated_at` set, NEVER updated. Point-in-time snapshot. Content changes → new report. `source_snapshot` captures credibility at gen time.

5. **All LLM calls async.** FastAPI routes NEVER call Ollama directly. All LLM inference dispatched as ARQ jobs, polled by client.

6. **Hardware independence mandatory.** No model name, device string ("cpu"/"cuda"), batch size, ML param hardcoded in service code. All from settings.py via env vars. See hardware.md.

7. **Deepfake scores = probabilities, never booleans.** Return float 0.0–1.0. Never `is_deepfake: bool`. Analyst decides threshold.

8. **Credibility changes audit-logged.** Every credibility_score change MUST insert row into credibility_audit_log. No silent updates.

9. **LLM output validated before use.** All LLM responses parsed through Pydantic model before storage/display. Never trust raw LLM string.

10. **No cloud LLM with real data.** Ollama = localhost or internal Docker network. Sovereign — intel data never leaves deployment boundary.

11. **X/Twitter spend guard.** XAdapter checks monthly read count against X_MONTHLY_READ_CAP before every API call. Never exceed budget silently.

12. **Drishti bridge one-directional.** Anveshak emits entities TO Drishti via source.envelopes.v1. NEVER reads from Drishti. No circular dependency.

## FIVE MODULES — PS-18 SCOPE (NOTHING MORE)

| Module | Service | Capability |
|--------|---------|-----------|
| M1 | analyst | Source credibility scoring, auto-feedback loop, audit log |
| M2 | scraper + analyst | Open-web crawling, NLP, multilingual, clustering, backfill |
| M3 | social | Platform adapters: Telegram, Reddit, Bluesky, X (pay-per-use) |
| M4 | vision | YOLO, CLIP, deepfake (image+video), EXIF, pHash reverse lookup |
| M5 | reporter | LLM report gen (RAG), GIS output, PDF export, scheduled reports |

Cross-cutting: Signals engine (threshold notifications), real-time topic monitoring.

## SOURCE-TOPIC ASSOCIATION — MANDATORY

Sources linked to topics via `topic_sources` join table:

```
topics ──┬── topic_sources ──┬── sources
         │                   │
         └── content_items ──┘
```

- **Sources = global entities** but must be explicitly assigned to topics.
- Scraper ONLY scrapes sources linked via `topic_sources`.
- `SQL_GET_WEB_SOURCES` and `SQL_GET_RSS_SOURCES` MUST filter by topic_id through JOIN on `topic_sources`.
- Source created with `topic_id` → auto-linked.
- API: `POST /api/v1/topics/{id}/sources/{source_id}` to link, `DELETE /api/v1/topics/{id}/sources/{source_id}` to unlink.
- Migration 007 backfills existing associations from content_items.

## WHAT ANVESHAK IS NOT

- Not entity resolution platform (Drishti's job)
- Not cross-domain fusion engine (Drishti's job)
- Not graph database (flat PostgreSQL only)
- Not dependent on Kafka/Redpanda/AGE/Vault/Keycloak

## HARDWARE INDEPENDENCE RULE

Every hardware-sensitive choice MUST be in settings.py from env vars.
New ML component → immediately add upgrade path to hardware.md.
Tests MUST pass on CPU with default medium/nano/cpu config.
See hardware.md for full matrix.

## SECURITY RULES

- NEVER hardcode secrets — use env vars
- NEVER log raw scraped content — log content_hash and URL only
- NEVER call cloud LLM with real intel data
- NEVER trust LLM output without Pydantic validation
- NEVER embed user input directly in LLM prompts — sanitise + boundary markers
- Every Pydantic model uses model_config = ConfigDict(strict=True)

## NAMING CONVENTIONS

- Services: snake_case (scraper, social, vision, analyst, reporter)
- Topics: user-defined strings
- Content items: UUID primary keys
- PostgreSQL tables: snake_case, always created_at, updated_at, labels jsonb
- ARQ job functions: snake_case verbs (generate_report, scrape_topic, analyse_image)
- Storage paths: media/{topic_id}/{YYYY}/{MM}/{DD}/{content_hash}.{ext}

## TESTING RULES

- New source adapter MUST pass SourceAdapterConformanceSuite
- New Pydantic model MUST have test asserting labels non-Optional
- Tests run on CPU — never assume GPU
- Integration tests use Docker Compose — no mocking PostgreSQL/Redis
- 80%+ coverage on new service code

## SIGNAL ENGINE RULES

- Signals fire when narrative_clusters.independent_source_count >= topic.signal_threshold
- independent_source_count = distinct source.platform values in cluster
- Delivered via WebSocket push to connected analyst sessions
- Status transitions: new → acknowledged → dismissed

## REPORT IMMUTABILITY — EVIDENCE CHAIN

Reports = auditable, traceable output. Immutability non-negotiable:
- generated_at set ONCE on first write
- source_snapshot captures credibility scores AT gen time
- Source later downgraded → report_source_warnings inserted — report NOT modified
- Updated content needed → generate new report

## PROJECT LAYOUT

anveshak/
├── CLAUDE.md                    # This file
├── hardware.md                  # Hardware upgrade matrix — read before adding ML
├── pyproject.toml               # uv workspace root
├── Makefile                     # make up, down, migrate, test, demo-check
├── .env.example                 # all config vars with comments
├── .claude/                     # governance (commands, agents, rules, skills)
├── sdk/anveshak-sdk/            # shared Pydantic models + ARQ jobs + Drishti bridge
├── services/
│   ├── api/                     # FastAPI gateway, auth, WebSocket
│   ├── scraper/                 # M2: Crawl4AI web crawler
│   ├── social/                  # M3: platform adapters
│   ├── vision/                  # M4: YOLO, CLIP, deepfake, EXIF, pHash
│   ├── analyst/                 # M1+M2: NLP, clustering, Signals engine
│   └── reporter/                # M5: LLM reports, GIS, PDF
├── frontend/                    # React + TypeScript analyst workbench
├── infra/                # Docker Compose (core, vision, bridge)
├── schemas/                     # Pydantic canonical models
├── tests/                       # unit, integration, e2e
├── scripts/                     # verify_labels.py, seed_demo.sql, etc.
└── docs/                        # x_api_application.md, architecture.md

## WHAT TO DO WHEN UNCERTAIN

- Design involves entity resolution or cross-domain linking: STOP — Drishti's job
- Schema change might break backward compat: STOP and flag
- Adding new ML model: check hardware.md first, document upgrade path
- Security decision ambiguous: FAIL CLOSED and document why

## Agent skills

### Issue tracker

GitHub Issues on `Grosint/anveshak`. External PRs are not a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-label vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at repo root. See `docs/agents/domain.md`.