# ANVESHAK — AI-POWERED OSINT ANALYSIS PLATFORM

Read this before touching anything. These rules are non-negotiable.

## WHAT ANVESHAK IS

Anveshak is a standalone, sovereign AI-OSINT analysis and monitoring platform built
for defence forces and law enforcement agencies (LEAs). Originally developed under
iDEX ADITI 4.0 PS-18. It is a separate product from Drishti.

**Product strategy:** Sell Anveshak first. Drishti is the upsell.
Anveshak deploys standalone — no Redpanda, no AGE, no Vault required.
Every intelligence officer should be able to run it on one machine.

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

1. **Standalone-first.** Every service starts with ANVESHAK_DRISHTI_BRIDGE=false.
   Anveshak NEVER requires Drishti to run.

2. **Labels are mandatory.** Every Pydantic model MUST have a `labels: Labels` field.
   Labels are NEVER Optional. Never create a model without them.

3. **Content deduplication is mandatory.** Every ContentItem MUST have a `content_hash`
   (SHA-256 of normalised clean_text). All inserts use ON CONFLICT(content_hash) DO NOTHING.

4. **Reports are immutable.** Once `generated_at` is set, it is NEVER updated.
   A report is a point-in-time snapshot. If content changes, generate a new report.
   `source_snapshot` captures credibility scores at generation time.

5. **All LLM calls are async.** FastAPI routes NEVER call Ollama directly.
   All LLM inference is dispatched as ARQ background jobs and polled by the client.

6. **Hardware independence is mandatory.** No model name, device string ("cpu"/"cuda"),
   batch size, or ML parameter may be hardcoded in service code. All come from settings.py
   which reads from environment variables. See hardware.md for the full upgrade matrix.

7. **Deepfake scores are probabilities, never booleans.** Always return float 0.0–1.0.
   Never store or return `is_deepfake: bool`. The analyst decides the threshold.

8. **Credibility changes are audit-logged.** Every change to source credibility_score
   MUST insert a row into credibility_audit_log. No silent updates.

9. **LLM output is validated before use.** All LLM responses are parsed through a
   Pydantic model before storage or display. Never trust raw LLM string output.

10. **No cloud LLM with real data.** Ollama must be localhost or internal Docker network.
    Sovereign requirement — intelligence data never leaves the deployment boundary.

11. **X/Twitter spend guard.** XAdapter checks monthly read count against
    X_MONTHLY_READ_CAP before every API call. Never exceed budget silently.

12. **Drishti bridge is strictly one-directional.** Anveshak emits entities TO Drishti
    via source.envelopes.v1. Anveshak NEVER reads from Drishti. No circular dependency.

## FIVE MODULES — PS-18 SCOPE (NOTHING MORE)

| Module | Service | Capability |
|--------|---------|-----------|
| M1 | analyst | Source credibility scoring, auto-feedback loop, audit log |
| M2 | scraper + analyst | Open-web crawling, NLP, multilingual, clustering, backfill |
| M3 | social | Platform adapters: Telegram, Reddit, Bluesky, X (pay-per-use) |
| M4 | vision | YOLO, CLIP, deepfake (image+video), EXIF, pHash reverse lookup |
| M5 | reporter | LLM report gen (RAG), GIS output, PDF export, scheduled reports |

Cross-cutting: Signals engine (threshold-based notifications), real-time topic monitoring.

## SOURCE-TOPIC ASSOCIATION — MANDATORY

Sources are linked to topics via the `topic_sources` join table:

```
topics ──┬── topic_sources ──┬── sources
         │                   │
         └── content_items ──┘
```

- **Sources are global entities** but must be explicitly assigned to topics.
- The scraper ONLY scrapes sources linked to a topic via `topic_sources`.
- `SQL_GET_WEB_SOURCES` and `SQL_GET_RSS_SOURCES` MUST filter by topic_id
  through a JOIN on `topic_sources`.
- When a source is created with a `topic_id`, it is auto-linked.
- API: `POST /api/v1/topics/{id}/sources/{source_id}` to link,
       `DELETE /api/v1/topics/{id}/sources/{source_id}` to unlink.
- Migration 007 backfills existing associations from content_items.

## WHAT ANVESHAK IS NOT

- Not an entity resolution platform (that is Drishti's job)
- Not a cross-domain fusion engine (that is Drishti's job)
- Not a graph database (flat PostgreSQL relationships only)
- Not dependent on Kafka/Redpanda/AGE/Vault/Keycloak

## HARDWARE INDEPENDENCE RULE

Every hardware-sensitive choice MUST be in settings.py reading from env vars.
When adding any new ML component, immediately add its upgrade path to hardware.md.
Tests MUST pass on CPU with default medium/nano/cpu configuration.
See hardware.md for full current vs upgrade matrix.

## SECURITY RULES

- NEVER hardcode secrets — use environment variables
- NEVER log raw scraped content — log content_hash and URL only
- NEVER call cloud LLM with real intelligence data
- NEVER trust LLM output without Pydantic validation
- NEVER embed user input directly in LLM prompts — sanitise and wrap in boundary markers
- Every Pydantic model uses model_config = ConfigDict(strict=True)

## NAMING CONVENTIONS

- Services: snake_case (scraper, social, vision, analyst, reporter)
- Topics: user-defined strings
- Content items: UUID primary keys
- PostgreSQL tables: snake_case, always created_at, updated_at, labels jsonb
- ARQ job functions: snake_case verbs (generate_report, scrape_topic, analyse_image)
- Storage paths: media/{topic_id}/{YYYY}/{MM}/{DD}/{content_hash}.{ext}

## TESTING RULES

- Every new source adapter MUST pass the SourceAdapterConformanceSuite
- Every new Pydantic model MUST have a test asserting labels is non-Optional
- Tests run on CPU — never assume GPU
- Integration tests use Docker Compose — no mocking of PostgreSQL or Redis
- 80%+ coverage on all new service code

## SIGNAL ENGINE RULES

- Signals fire when narrative_clusters.independent_source_count >= topic.signal_threshold
- independent_source_count counts distinct source.platform values in a cluster
- Signals are delivered via WebSocket push to connected analyst sessions
- Signal status transitions: new → acknowledged → dismissed

## REPORT IMMUTABILITY — EVIDENCE CHAIN

Reports are Anveshak's auditable, traceable output. Immutability is non-negotiable:
- generated_at is set ONCE on first write
- source_snapshot captures credibility scores AT generation time
- If a source is later downgraded: report_source_warnings is inserted — report itself is NOT modified
- A new report must be generated if the analyst wants updated content

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

- If a design decision involves entity resolution or cross-domain linking: STOP — that is Drishti's job
- If a schema change might break backward compat: STOP and flag explicitly
- If adding a new ML model: check hardware.md first, document upgrade path
- If a security decision is ambiguous: FAIL CLOSED and document why
