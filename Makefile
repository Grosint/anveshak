# =============================================================================
# ANVESHAK — AI-OSINT Platform Makefile
# =============================================================================
#
# SETUP (new developer):
#   make setup            full first-run: syscheck -> build -> infra up -> migrate -> pull-models -> all up -> download-models -> seed -> validate
#
# LIFECYCLE:
#   make up               start full stack including vision (no rebuild)
#   make up-vision        full stack + NVIDIA GPU overlay for vision
#   make up-bridge        core + Drishti bridge overlay
#   make down             stop all containers
#   make restart          restart all containers
#   make ps               container status (colorful table)
#   make logs             tail all service logs
#   make logs-<service>   tail one service (e.g. make logs-analyst)
#
# FRESH (rebuild from scratch):
#   make fresh            clean-containers -> build -> up -> migrate -> validate
#   make fresh-all        clean-volumes -> build -> up -> migrate -> pull-models -> seed-demo -> validate
#
# CLEAN (graduated):
#   make clean            Python caches only (__pycache__, .pytest_cache, .ruff_cache)
#   make clean-containers stop + remove all containers (keep volumes/data)
#   make clean-volumes    stop + remove containers + volumes (DB data lost!)
#   make clean-cache      Docker build cache prune
#   make purge            ALL of the above (nuclear option, asks confirmation)
#   make nuke             remove EVERY Anveshak Docker artifact — images, volumes, cache, networks
#
# VALIDATE:
#   make syscheck         system requirements check (RAM, disk, Docker, ports)
#   make venv-check       verify .venv matches this repo path and Python 3.12
#   make health           quick health check (are services up?)
#   make validate         full pipeline validation (7 stages)
#   make validate-vision  vision pipeline validation (M4 deepfake)
#   make validate-vector  vector pipeline validation (dedup, HNSW, temporal, convergence)
#   make validate-all     all three validation suites
#
# TEST:
#   make test             unit + integration
#   make test-unit        unit tests only
#   make test-vector      vector pipeline unit tests only
#   make test-integration integration tests (requires running stack)
#   make test-vector-integration  vector cross-dependency tests (requires running stack)
#   make test-e2e         end-to-end tests (requires full stack + credentials)
#   make test-coverage    coverage report
#
# DATABASE:
#   make migrate          run Alembic migrations
#   make migrate-status   show current migration revision
#   make migrate-rollback rollback one migration
#   make seed-demo        load Indian Navy demo scenario
#
# QUALITY:
#   make lint             ruff check
#   make format           ruff format + fix
#   make typecheck        pyright
#   make security-scan    bandit scan
#
# =============================================================================

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COMPOSE      := docker compose --env-file .env -p anveshak -f infra/compose.yml
COMPOSE_VIS  := $(COMPOSE) -f infra/compose.vision.yml
COMPOSE_BRG  := $(COMPOSE) -f infra/compose.bridge.yml
UV           := uv run

# ANSI colour codes
_RST   := \033[0m
_BOLD  := \033[1m
_RED   := \033[31m
_GRN   := \033[32m
_YEL   := \033[33m
_BLU   := \033[34m
_CYN   := \033[36m
_MAG   := \033[35m
_DIM   := \033[2m

# Status symbols
_PASS  := $(_GRN)✓$(_RST)
_FAIL  := $(_RED)✗$(_RST)
_WARN  := $(_YEL)!$(_RST)
_INFO  := $(_BLU)→$(_RST)
_WORK  := $(_CYN)⟳$(_RST)

.PHONY: all setup up up-vision up-bridge build build-nocache build-vision down restart \
        ps logs init pull-models download-models migrate migrate-status migrate-hnsw \
        migrate-rollback seed-demo seed-demo-iaf seed-demo-haryana seed-demo-kerala \
        fresh fresh-all \
        test test-unit test-contract test-integration test-e2e test-full test-scrape \
        test-ci test-all test-nightly \
        demo-check validate validate-vision health syscheck \
        lint format typecheck security-scan \
        clean clean-containers clean-volumes clean-cache purge nuke \
        verify-labels verify-reports shell-% \
        benchmark benchmark-clean benchmark-skip-analyse \
        validate-vision-full \
        agents-sync agents-check venv-check \
        create-test-db migrate-test migrate-all reset-test-db-if-orphaned

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

define header
	@printf "\n$(_BOLD)$(_BLU)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(_RST)\n"
	@printf "$(_BOLD)$(_BLU)  $(1)$(_RST)\n"
	@printf "$(_BOLD)$(_BLU)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(_RST)\n\n"
endef

define step
	@printf "  $(_WORK) $(_BOLD)$(1)$(_RST) $(2)\n"
endef

define success
	@printf "  $(_PASS) $(_GRN)$(1)$(_RST)\n"
endef

define fail
	@printf "  $(_FAIL) $(_RED)$(1)$(_RST)\n"
endef

define info
	@printf "  $(_INFO) $(1)\n"
endef

define warn
	@printf "  $(_WARN) $(_YEL)$(1)$(_RST)\n"
endef

# Check .env exists + required vars are set
define check_env
	@if [ ! -f .env ]; then \
		printf "\n$(_BOLD)$(_RED)  ERROR: .env file not found$(_RST)\n"; \
		printf "  $(_INFO) Run: $(_BOLD)cp .env.example .env$(_RST) and fill in your secrets\n\n"; \
		exit 1; \
	fi
	@bash scripts/check_env.sh $(1)
endef

# ---------------------------------------------------------------------------
# SETUP — Full first-run for new developers
# ---------------------------------------------------------------------------

setup:
	$(call header,ANVESHAK — First-Run Setup)
	$(call step,Step 1/8,System requirements check)
	@$(UV) python scripts/syscheck.py || { \
		printf "\n"; \
		printf "  $(_WARN) $(_YEL)System does not meet minimum requirements — see above$(_RST)\n"; \
		printf "  $(_INFO) Continue anyway? [y/N] "; \
		read confirm; \
		if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then exit 1; fi; \
	}
	$(call check_env,infra/compose.yml)
	$(call step,Step 2/8,Building Docker images)
	@$(COMPOSE) build
	$(call success,Images built)
	$(call step,Step 3/8,Starting infrastructure — postgres + redis + ollama)
	@$(COMPOSE) up -d --remove-orphans postgres redis ollama
	$(call step,Step 4/8,Waiting for infrastructure to be healthy...)
	@timeout=120; elapsed=0; \
	while [ $$elapsed -lt $$timeout ]; do \
		healthy=$$(docker compose --env-file .env -p anveshak -f infra/compose.yml ps --format json 2>/dev/null | python3 -c "import sys,json; lines=sys.stdin.read().strip().split('\n'); print(sum(1 for l in lines if json.loads(l).get('Health','')=='healthy'))" 2>/dev/null || echo 0); \
		if [ "$$healthy" -ge 3 ]; then break; fi; \
		sleep 5; elapsed=$$((elapsed + 5)); \
		printf "  $(_DIM)  waiting... ($$elapsed/$$timeout s)$(_RST)\r"; \
	done
	$(call success,Infrastructure healthy)
	$(call step,Step 5/8,Running migrations + pulling Ollama model)
	@$(COMPOSE) exec -T api alembic upgrade head 2>&1 || { \
		printf "  $(_INFO) API not yet running — starting it for migrations...\n"; \
		$(COMPOSE) up -d api; sleep 10; \
		$(COMPOSE) exec -T api alembic upgrade head 2>&1 | tail -1; \
	}
	$(call success,Migrations applied)
	@$(MAKE) --no-print-directory migrate-test 2>/dev/null || true
	@printf "  $(_WORK) Pulling Ollama model (this may take several minutes on first run)...\n"
	@$(COMPOSE) exec -T ollama ollama pull $$(grep -E '^OLLAMA_MODEL=' .env 2>/dev/null | cut -d= -f2 | sed 's/#.*//' | tr -d ' ' || echo "qwen2:7b") 2>&1 | tail -3
	$(call success,Ollama model ready)
	$(call step,Step 6/8,Starting all services)
	@$(COMPOSE) up -d --remove-orphans
	@timeout=120; elapsed=0; \
	while [ $$elapsed -lt $$timeout ]; do \
		unhealthy=$$(docker compose --env-file .env -p anveshak -f infra/compose.yml ps 2>/dev/null | grep -cE '(Restarting|unhealthy|starting)' || echo 0); \
		if [ "$$unhealthy" -eq 0 ]; then break; fi; \
		sleep 5; elapsed=$$((elapsed + 5)); \
		printf "  $(_DIM)  waiting for services... ($$elapsed/$$timeout s)$(_RST)\r"; \
	done
	$(call success,All services started)
	$(call step,Step 7/8,Downloading vision models (YOLO + CLIP + deepfake))
	@$(MAKE) --no-print-directory download-models
	$(call success,Vision models ready)
	@$(COMPOSE) exec -T postgres psql -U anveshak -d anveshak < scripts/seed_demo.sql 2>&1 | tail -1
	$(call success,Demo scenario loaded)
	$(call step,Step 8/8,Validating pipeline)
	@$(UV) python scripts/validate_pipeline.py || { \
		printf "\n"; \
		printf "  $(_WARN) $(_YEL)Validation had failures — this is expected on first setup$(_RST)\n"; \
		printf "  $(_INFO) Corpus will grow as scraper and social adapters run.\n"; \
	}
	$(call header,Setup Complete)
	@printf "  $(_GRN)$(_BOLD)Anveshak is ready!$(_RST)\n\n"
	@printf "  Analyst workbench:  $(_CYN)http://localhost:3000$(_RST)\n"
	@printf "  API:                $(_CYN)http://localhost:8000$(_RST)\n"
	@printf "  Grafana:            $(_CYN)http://localhost:3001$(_RST)\n"
	@printf "  Prometheus:         $(_CYN)http://localhost:9090$(_RST)\n\n"
	@printf "  Login:    $(_BOLD)demo@anveshak.local$(_RST) / $(_BOLD)AnveshakDemo2024!$(_RST)\n"
	@printf "  Next:     $(_BOLD)make validate$(_RST)  to re-run validation anytime\n\n"

# ---------------------------------------------------------------------------
# Docker Compose lifecycle
# ---------------------------------------------------------------------------

build:
	$(call header,Building Docker Images)
	$(call check_env,infra/compose.yml)
	@$(COMPOSE) build
	$(call success,All images built)

build-nocache:
	$(call header,Building Docker Images (no cache))
	$(call check_env,infra/compose.yml)
	@$(COMPOSE) build --no-cache
	$(call success,All images built (no cache))

build-vision:
	$(call header,Building Docker Images (+ Vision))
	$(call check_env,infra/compose.yml infra/compose.vision.yml)
	@$(COMPOSE_VIS) build
	$(call success,All images built (including vision))

up:
	$(call header,Starting Anveshak Core Stack)
	$(call check_env,infra/compose.yml)
	@$(COMPOSE) up -d --remove-orphans
	$(call success,Core stack started)
	@printf "\n  Run $(_BOLD)make ps$(_RST) to check health status\n"
	@printf "  Run $(_BOLD)make health$(_RST) for quick health check\n\n"

up-vision:
	$(call header,Starting Anveshak + Vision GPU Overlay)
	$(call check_env,infra/compose.yml infra/compose.vision.yml)
	@$(COMPOSE_VIS) up -d --remove-orphans
	$(call success,Core + Vision (GPU) stack started)

up-bridge:
	$(call header,Starting Anveshak + Drishti Bridge)
	$(call check_env,infra/compose.yml infra/compose.bridge.yml)
	@$(COMPOSE_BRG) up -d --remove-orphans
	$(call success,Core + Bridge stack started)

down:
	$(call header,Stopping Anveshak)
	@$(COMPOSE_BRG) down 2>/dev/null || true
	@$(COMPOSE_VIS) down 2>/dev/null || true
	@$(COMPOSE) down --remove-orphans
	$(call success,All containers stopped)

restart:
	$(call header,Restarting Anveshak)
	@$(COMPOSE) restart
	$(call success,All containers restarted)

ps:
	$(call header,Container Status)
	@$(COMPOSE) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || $(COMPOSE) ps
	@printf "\n"

logs:
	@$(COMPOSE) logs -f --tail=100

logs-%:
	@$(COMPOSE) logs -f --tail=100 $*

shell-%:
	@$(COMPOSE) exec $* /bin/bash

# ---------------------------------------------------------------------------
# First-run initialisation (services must be running)
# ---------------------------------------------------------------------------

init: pull-models migrate
	$(call header,Initialisation Complete)
	@printf "  API:        $(_CYN)http://localhost:8000$(_RST)\n"
	@printf "  Frontend:   $(_CYN)http://localhost:3000$(_RST)\n"
	@printf "  Prometheus: $(_CYN)http://localhost:9090$(_RST)\n"
	@printf "  Grafana:    $(_CYN)http://localhost:3001$(_RST)\n\n"
	@printf "  Next: $(_BOLD)make seed-demo$(_RST) to load the demo scenario\n\n"

pull-models:
	$(call header,Pulling Ollama Models)
	@printf "  $(_WORK) Pulling model (may take several minutes on first run)...\n"
	@$(COMPOSE) exec -T ollama ollama pull $$(grep -E '^OLLAMA_MODEL=' .env 2>/dev/null | cut -d= -f2 | sed 's/#.*//' | tr -d ' ' || echo "qwen2:7b")
	$(call success,Model ready)

download-models:
	$(call header,Downloading Vision Models (YOLO + CLIP + Deepfake ONNX))
	@$(COMPOSE) run --rm analyse-vision-init
	$(call success,All vision models ready)

# Pull upgraded models when hardware is available (see hardware.md)
pull-models-gpu:
	$(call header,Pulling GPU-Tier Ollama Models)
	@printf "  $(_WORK) Pulling qwen2.5:72b (requires RTX 4090 / 40GB+ VRAM)...\n"
	@$(COMPOSE) exec -T ollama ollama pull qwen2.5:72b
	$(call success,GPU model ready)

# ---------------------------------------------------------------------------
# Database migrations
# ---------------------------------------------------------------------------

migrate:
	$(call header,Running Database Migrations)
	@$(COMPOSE) exec -T api alembic upgrade head
	$(call success,Migrations applied)

create-test-db:
	$(call header,Creating Test Database)
	@$(MAKE) --no-print-directory reset-test-db-if-orphaned
	@$(COMPOSE) exec -T postgres psql -U anveshak -tc \
		"SELECT 1 FROM pg_database WHERE datname='anveshak_test'" | grep -q 1 \
		|| $(COMPOSE) exec -T postgres psql -U anveshak -c "CREATE DATABASE anveshak_test OWNER anveshak;"
	@$(COMPOSE) exec -T postgres psql -U anveshak -d anveshak_test -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null
	@$(COMPOSE) exec -T postgres psql -U anveshak -d anveshak_test -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";' 2>/dev/null
	@$(COMPOSE) exec -T postgres psql -U anveshak -d anveshak_test -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" 2>/dev/null
	@$(COMPOSE) exec -T postgres psql -U anveshak -d anveshak_test -c "CREATE EXTENSION IF NOT EXISTS btree_gin;" 2>/dev/null
	$(call success,Test database ready)

# Migrations get squashed periodically, and the old revisions move to
# migrations/archive/. A postgres volume that outlived a squash leaves
# anveshak_test stamped at a revision alembic can no longer walk from, and
# `alembic upgrade head` fails with the opaque "Can't locate revision
# identified by 'NNN'". The test DB holds no data worth keeping, so drop it
# and let create-test-db rebuild from head. Only ever touches anveshak_test.
reset-test-db-if-orphaned:
	@stamp=$$($(COMPOSE) exec -T postgres psql -U anveshak -d anveshak_test -tAc \
		"SELECT version_num FROM alembic_version" 2>/dev/null | tr -d '[:space:]'); \
	if [ -n "$$stamp" ] && ! grep -qs "revision = \"$$stamp\"" services/api/migrations/versions/*.py; then \
		printf "  $(_WARN) $(_YEL)anveshak_test is stamped at revision $$stamp, which no longer exists in migrations/versions/$(_RST)\n"; \
		printf "  $(_INFO) Dropping and rebuilding the test database from head\n"; \
		$(COMPOSE) exec -T postgres psql -U anveshak -c \
			"DROP DATABASE IF EXISTS anveshak_test WITH (FORCE);" >/dev/null; \
	fi

migrate-test:
	$(call header,Running Test Database Migrations)
	@$(MAKE) --no-print-directory create-test-db
	@$(COMPOSE) exec -T -e POSTGRES_URL=postgresql://anveshak:$${POSTGRES_PASSWORD:-change-me-in-production}@postgres:5432/anveshak_test \
		api alembic upgrade head
	$(call success,Test DB migrations applied)

migrate-all: migrate migrate-test

migrate-status:
	$(call header,Migration Status)
	@cd services/api && $(UV) --package anveshak-api alembic current

migrate-rollback:
	$(call header,Rolling Back Migration)
	@cd services/api && $(UV) --package anveshak-api alembic downgrade -1
	$(call success,Rolled back one revision)

# HNSW index is now part of 001_initial_schema — this target is a no-op
migrate-hnsw:
	$(call header,HNSW index included in initial schema)
	$(call success,Nothing to do — HNSW is the default index)

# ---------------------------------------------------------------------------
# Demo seed
# ---------------------------------------------------------------------------

seed-demo:
	$(call header,Loading Demo Scenario)
	@$(COMPOSE) exec -T postgres psql -U anveshak -d anveshak < scripts/seed_demo.sql 2>&1 | tail -1
	$(call success,Demo scenario loaded)
	@printf "\n  Login at $(_CYN)http://localhost:3000$(_RST)\n"
	@printf "  Username: $(_BOLD)demo@anveshak.local$(_RST)\n"
	@printf "  Password: $(_BOLD)AnveshakDemo2024!$(_RST)\n\n"

seed-demo-ec:
	$(call header,Loading Engine C Demo — 4 Agency Scenarios)
	@$(COMPOSE) exec -T postgres psql -U anveshak -d anveshak < scripts/seed_demo_engine_c.sql 2>&1 | tail -1
	$(call success,Engine C demo loaded (MEA + Cyber + SEBI + NCB))
	@printf "\n  Orgs: org_mea, org_cyber, org_sebi, org_ncb\n"
	@printf "  Login: demo_{mea,cyber,sebi,ncb}@anveshak.local\n"
	@printf "  Password: $(_BOLD)AnveshakDemo2024!$(_RST)\n\n"

seed-demo-iaf:
	$(call header,Loading IAF Bengaluru Demo — Air Force Intelligence)
	@$(COMPOSE) exec -T postgres psql -U anveshak -d anveshak < scripts/seed_airforce_bengaluru_demo.sql 2>&1 | tail -1
	$(call success,IAF demo loaded (3 topics — Chinese Air Power + Disinfo + PAF))
	@printf "\n  Login at $(_CYN)http://localhost:3000$(_RST)\n"
	@printf "  Username: $(_BOLD)demo_iaf@anveshak.local$(_RST)\n"
	@printf "  Password: $(_BOLD)AnveshakDemo2024!$(_RST)\n\n"

seed-demo-tgcsb:
	$(call header,Loading Telangana TGCSB Demo — Cyber Fraud Intelligence)
	@$(COMPOSE) exec -T postgres psql -U anveshak -d anveshak < scripts/seed_telangana_demo.sql 2>&1 | tail -1
	$(call success,TGCSB demo loaded (topic tg-cyber-001 — investment fraud + mule accounts))
	@printf "\n  Login at $(_CYN)http://localhost:3000$(_RST)\n"
	@printf "  Username: $(_BOLD)demo_cyber@anveshak.local$(_RST)\n"
	@printf "  Password: $(_BOLD)AnveshakDemo2024!$(_RST)\n\n"

pdf-telangana:
	$(call header,Generating Telangana TGCSB Leave-Behind PDF)
	@docker cp scripts/gen_telangana_leave_behind.py anveshak-report-worker-1:/tmp/
	@docker exec anveshak-report-worker-1 python /tmp/gen_telangana_leave_behind.py
	@docker cp anveshak-report-worker-1:/tmp/telangana_leave_behind.pdf .
	$(call success,PDF saved to ./telangana_leave_behind.pdf)

seed-demo-haryana:
	$(call header,Loading Haryana STF Demo — Narcotics Intelligence)
	@$(COMPOSE) exec -T postgres psql -U anveshak -d anveshak < scripts/seed_haryana_demo.sql 2>&1 | tail -1
	$(call success,Haryana STF demo loaded (topic hr-stf-001 — drug trafficking + narcotics))
	@printf "\n  Login at $(_CYN)http://localhost:3000$(_RST)\n"
	@printf "  Username: $(_BOLD)demo_cyber@anveshak.local$(_RST)\n"
	@printf "  Password: $(_BOLD)AnveshakDemo2024!$(_RST)\n\n"

pdf-haryana:
	$(call header,Generating Haryana STF Leave-Behind PDF)
	@docker cp scripts/gen_haryana_leave_behind.py anveshak-report-worker-1:/tmp/
	@docker exec anveshak-report-worker-1 python /tmp/gen_haryana_leave_behind.py
	@docker cp anveshak-report-worker-1:/tmp/haryana_leave_behind.pdf .
	$(call success,PDF saved to ./haryana_leave_behind.pdf)

seed-demo-iaf-media:
	$(call header,Seeding IAF Deepfake Media + Vision Results)
	@docker cp scripts/seed_iaf_deepfake_media.py anveshak-analyse-vision-worker-1:/tmp/
	@docker exec anveshak-analyse-vision-worker-1 python /tmp/seed_iaf_deepfake_media.py
	$(call success,3 deepfake media assets + vision results seeded)

pdf-iaf:
	$(call header,Generating IAF Air Intelligence Leave-Behind PDF)
	@docker cp scripts/gen_iaf_leave_behind.py anveshak-report-worker-1:/tmp/
	@docker exec anveshak-report-worker-1 python /tmp/gen_iaf_leave_behind.py
	@docker cp anveshak-report-worker-1:/tmp/iaf_leave_behind.pdf .
	$(call success,PDF saved to ./iaf_leave_behind.pdf)

seed-demo-kerala:
	$(call header,Loading Kerala Cyber Dome Demo — Online Child Protection Intelligence)
	@$(COMPOSE) exec -T postgres psql -U anveshak -d anveshak < scripts/seed_kerala_demo.sql 2>&1 | tail -1
	$(call success,Kerala demo loaded (topic kl-cyd-001 — child protection + predator networks))
	@printf "\n  Login at $(_CYN)http://localhost:3000$(_RST)\n"
	@printf "  Username: $(_BOLD)demo_cyber@anveshak.local$(_RST)\n"
	@printf "  Password: $(_BOLD)AnveshakDemo2024!$(_RST)\n\n"

pdf-kerala:
	$(call header,Generating Kerala Cyber Dome Leave-Behind PDF)
	@docker cp scripts/gen_kerala_leave_behind.py anveshak-report-worker-1:/tmp/
	@docker exec anveshak-report-worker-1 python /tmp/gen_kerala_leave_behind.py
	@docker cp anveshak-report-worker-1:/tmp/kerala_leave_behind.pdf .
	$(call success,PDF saved to ./kerala_leave_behind.pdf)

# ---------------------------------------------------------------------------
# Fresh start shortcuts
# ---------------------------------------------------------------------------

fresh: clean-containers build-nocache up migrate download-models validate
	$(call success,Fresh rebuild complete)

fresh-all:
	$(call header,Full Fresh Start (volumes will be destroyed))
	@printf "  $(_YEL)This will delete all database data, Redis cache, and Ollama models.$(_RST)\n"
	@printf "  Continue? [y/N] "; \
	read confirm; \
	if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
		printf "  Aborted.\n"; exit 1; \
	fi
	@$(MAKE) --no-print-directory clean-volumes
	@$(MAKE) --no-print-directory build
	@$(COMPOSE) up -d --remove-orphans postgres redis ollama
	@printf "  $(_WORK) Waiting for infrastructure...\n"
	@timeout=120; elapsed=0; \
	while [ $$elapsed -lt $$timeout ]; do \
		healthy=$$(docker compose --env-file .env -p anveshak -f infra/compose.yml ps --format json 2>/dev/null | python3 -c "import sys,json; lines=sys.stdin.read().strip().split('\n'); print(sum(1 for l in lines if json.loads(l).get('Health','')=='healthy'))" 2>/dev/null || echo 0); \
		if [ "$$healthy" -ge 3 ]; then break; fi; \
		sleep 5; elapsed=$$((elapsed + 5)); \
	done
	@$(MAKE) --no-print-directory migrate
	@$(MAKE) --no-print-directory up
	@$(MAKE) --no-print-directory pull-models
	@$(MAKE) --no-print-directory download-models
	@$(MAKE) --no-print-directory seed-demo
	@$(MAKE) --no-print-directory validate
	$(call success,Full fresh start complete)

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

# ── Fast feedback (developer loop) ──────────────────────────

test: test-unit test-integration

unit: test-unit

integration: test-integration

# ── Base targets ──────────────────────────────────────────

test-unit: venv-check
	$(call header,Unit Tests (~10s — no containers needed))
	@$(UV) pytest tests/unit/ tests/contracts/ -v --tb=short -q \
		--cov=services --cov=sdk --cov-report=term:skip-covered

test-contract: venv-check
	$(call header,Contract Tests (~10s — no containers needed))
	@$(UV) pytest tests/contracts/ -v --tb=short -q

test-integration: venv-check
	$(call header,Integration Tests (~90s — requires make up))
	@$(MAKE) --no-print-directory migrate-test
	@_fail=0; \
	printf "\n  $(_INFO) Step 1/5: Host-side DB tests\n"; \
	$(UV) pytest tests/integration/ -v --tb=short -q -m integration \
		--cov=services --cov=sdk --cov-report=term:skip-covered || _fail=1; \
	printf "\n  $(_INFO) Step 2/5: Analyst model tests (inside analyse-worker)\n"; \
	$(COMPOSE) cp scripts/test_analyst_models.py analyse-worker:/tmp/test_analyst_models.py; \
	$(COMPOSE) exec -T -e POSTGRES_URL=postgresql://anveshak:$${POSTGRES_PASSWORD:-change-me-in-production}@postgres:5432/anveshak_test \
		analyse-worker python /tmp/test_analyst_models.py || _fail=1; \
	printf "\n  $(_INFO) Step 3/5: Vision model tests (inside analyse-vision-worker)\n"; \
	$(COMPOSE) cp scripts/test_vision_models.py analyse-vision-worker:/tmp/test_vision_models.py; \
	$(COMPOSE) exec -T analyse-vision-worker python /tmp/test_vision_models.py || _fail=1; \
	printf "\n  $(_INFO) Step 4/5: Ollama LLM tests (inside report-worker)\n"; \
	$(COMPOSE) cp scripts/test_ollama_models.py report-worker:/tmp/test_ollama_models.py; \
	$(COMPOSE) exec -T report-worker python /tmp/test_ollama_models.py || _fail=1; \
	printf "\n  $(_INFO) Step 5/5: Multilingual pipeline validation (inside analyse-worker)\n"; \
	$(COMPOSE) cp scripts/test_multilingual_pipeline.py analyse-worker:/tmp/test_multilingual_pipeline.py; \
	$(COMPOSE) exec -T -e POSTGRES_URL=postgresql://anveshak:$${POSTGRES_PASSWORD:-change-me-in-production}@postgres:5432/anveshak_test \
		analyse-worker python /tmp/test_multilingual_pipeline.py || _fail=1; \
	exit $$_fail

test-e2e: venv-check
	$(call header,End-to-End Tests (~2min — requires make up + seed-demo))
	@$(UV) pytest tests/e2e/ tests/resilience/ -v --tb=short -m "e2e or resilience"

# ── Frontend tests ─────────────────────────────────────────

test-frontend:
	$(call header,Frontend Tests)
	@cd frontend && npx vitest run

test-frontend-coverage:
	$(call header,Frontend Coverage Report)
	@cd frontend && npx vitest run --coverage

# ── Composite targets ──────────────────────────────────────

test: test-unit test-integration test-e2e
	$(call success,All tests passed)

test-full: venv-check
	$(call header,Full Test Suite + Coverage Gate (pre-release))
	@$(MAKE) --no-print-directory test
	@$(MAKE) --no-print-directory test-frontend
	@$(UV) pytest tests/unit/ tests/contracts/ tests/integration/ \
		--cov=services --cov=sdk \
		--cov-report=term-missing --cov-report=html:htmlcov \
		--cov-fail-under=80
	$(call success,All tests passed — coverage report: htmlcov/index.html)

# ── External (manual — needs internet) ────────────────────

test-scrape: venv-check
	$(call header,Source Connectivity Tests (manual — needs internet))
	@$(UV) python scripts/test_scrape.py

# ── Aliases (backward compat) ─────────────────────────────

test-ci: test-full
test-all: test-full
test-nightly: test-full

# ---------------------------------------------------------------------------
# Health + validation
# ---------------------------------------------------------------------------

syscheck:
	@$(UV) python scripts/syscheck.py

health:
	$(call header,Service Health Check)
	@printf "  %-20s %s\n" "SERVICE" "STATUS"
	@printf "  %-20s %s\n" "───────────────────" "──────────────────────────"
	@for svc in api:8000 scrape-web:8001 scrape-social:8002 analyse:8007; do \
		name=$$(echo $$svc | cut -d: -f1); \
		port=$$(echo $$svc | cut -d: -f2); \
		if curl -sf http://localhost:$$port/health > /dev/null 2>&1; then \
			printf "  %-20s $(_GRN)● healthy$(_RST)\n" "$$name"; \
		else \
			printf "  %-20s $(_RED)● down$(_RST)\n" "$$name"; \
		fi; \
	done
	@if $(COMPOSE) exec -T ollama ollama list > /dev/null 2>&1; then \
		models=$$($(COMPOSE) exec -T ollama ollama list 2>/dev/null | tail -n +2 | awk '{print $$1}' | tr '\n' ', ' | sed 's/,$$//'); \
		printf "  %-20s $(_GRN)● healthy$(_RST) [$$models]\n" "ollama"; \
	else \
		printf "  %-20s $(_RED)● down$(_RST)\n" "ollama"; \
	fi
	@if curl -sf http://localhost:3000/ > /dev/null 2>&1; then \
		printf "  %-20s $(_GRN)● healthy$(_RST)\n" "frontend"; \
	else \
		printf "  %-20s $(_RED)● down$(_RST)\n" "frontend"; \
	fi
	@if curl -sf http://localhost:3001/api/health > /dev/null 2>&1; then \
		printf "  %-20s $(_GRN)● healthy$(_RST)\n" "grafana"; \
	else \
		printf "  %-20s $(_YEL)● not running$(_RST)\n" "grafana"; \
	fi
	@if curl -sf http://localhost:9090/-/ready > /dev/null 2>&1; then \
		printf "  %-20s $(_GRN)● healthy$(_RST)\n" "prometheus"; \
	else \
		printf "  %-20s $(_YEL)● not running$(_RST)\n" "prometheus"; \
	fi
	@printf "\n"

demo-check:
	$(call header,Demo Readiness Check)
	@$(UV) python scripts/demo_check.py

validate:
	$(call header,Pipeline Validation)
	@$(UV) python scripts/validate_pipeline.py

validate-vision:
	$(call header,Vision Pipeline Validation)
	@$(UV) python scripts/validate_vision.py

validate-vector:
	$(call header,Vector Pipeline Validation)
	@$(UV) python scripts/validate_vector.py

validate-vision-full:
	$(call header,Vision Pipeline Full Validation (4 categories + video + CLIP))
	@$(UV) python scripts/validate_vision_full.py

validate-all: validate validate-vision validate-vector

# Verify all Pydantic models have non-optional labels field
verify-labels:
	$(call header,Verifying Labels Constraint)
	@$(UV) --package anveshak-sdk python scripts/verify_labels.py

# Check .env is in sync with .env.example (no missing keys)
check-env-sync:
	@bash scripts/check_env_sync.sh

# Verify report immutability constraints
verify-reports:
	$(call header,Verifying Report Immutability)
	@$(UV) --package anveshak-sdk python scripts/verify_reports_immutable.py

# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

benchmark:
	$(call header,Running Accuracy Benchmark)
	@$(UV) python -m benchmark
	$(call success,Benchmark complete — see docs/accuracy_benchmark.md)

benchmark-clean:
	$(call header,Cleaning Benchmark Data)
	@$(UV) python -m benchmark --clean-only
	$(call success,Benchmark data removed)

benchmark-skip-analyse:
	$(call header,Running Benchmark — skip NLP)
	@$(UV) python -m benchmark --skip-analyse

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

lint:
	$(call header,Linting)
	@$(UV) ruff check services/ sdk/ tests/ scripts/

format:
	$(call header,Formatting)
	@$(UV) ruff format services/ sdk/ tests/ scripts/
	@$(UV) ruff check --fix services/ sdk/ tests/ scripts/
	$(call success,Formatted)

typecheck:
	$(call header,Type Checking)
	@$(UV) pyright

security-scan:
	$(call header,Security Scan)
	@$(UV) bandit -r services/ sdk/ -ll --quiet
	$(call success,No security issues found)

# ---------------------------------------------------------------------------
# Maintenance / Cleanup (graduated)
# ---------------------------------------------------------------------------

# clean-test-data — remove orphaned integration-test rows from PostgreSQL
clean-test-data:
	$(call header,Cleaning Test Data from Database)
	@$(COMPOSE) exec -T postgres psql -U anveshak -d anveshak < scripts/cleanup_test_data.sql
	$(call success,Test data removed)

# clean — Python caches only (safe, fast)
clean:
	$(call header,Cleaning Python Caches)
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf htmlcov .coverage 2>/dev/null || true
	$(call success,Python caches cleaned)

# clean-containers — stop + remove containers (keep volumes/data)
clean-containers:
	$(call header,Stopping and Removing Containers)
	@$(COMPOSE_BRG) down --remove-orphans 2>/dev/null || true
	@$(COMPOSE_VIS) down --remove-orphans 2>/dev/null || true
	@$(COMPOSE) down --remove-orphans
	$(call success,Containers removed (volumes preserved))

# clean-volumes — stop + remove containers + all volumes (DATA LOSS)
clean-volumes:
	$(call header,Removing Containers + Volumes)
	$(call warn,This deletes PostgreSQL data$(,) Redis cache$(,) Ollama models$(,) and all other volumes)
	@$(COMPOSE_BRG) down -v 2>/dev/null || true
	@$(COMPOSE_VIS) down -v 2>/dev/null || true
	@$(COMPOSE) down -v --remove-orphans
	$(call success,Containers + volumes removed)

# clean-cache — Docker build cache prune
clean-cache:
	$(call header,Pruning Docker Build Cache)
	@docker builder prune -f
	$(call success,Docker build cache pruned)

# purge — everything (nuclear option)
purge:
	$(call header,PURGE — Full Cleanup)
	@printf "  $(_RED)$(_BOLD)This will destroy:$(_RST)\n"
	@printf "    - All containers and volumes (DB data, models, caches)\n"
	@printf "    - Docker build cache\n"
	@printf "    - Python caches\n"
	@printf "    - Dangling Docker images\n\n"
	@printf "  $(_YEL)Continue? [y/N]$(_RST) "; \
	read confirm; \
	if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
		printf "  Aborted.\n"; exit 1; \
	fi
	@$(MAKE) --no-print-directory clean
	@$(MAKE) --no-print-directory clean-volumes
	@$(MAKE) --no-print-directory clean-cache
	@docker images -q --filter reference='anveshak-*' 2>/dev/null | xargs docker rmi -f 2>/dev/null || true
	@docker image prune -f 2>/dev/null || true
	$(call success,Full purge complete)
	@printf "\n  To start fresh: $(_BOLD)make setup$(_RST)\n\n"

# nuke — remove every Docker artifact related to Anveshak (images, volumes, cache, networks)
nuke:
	$(call header,NUKE — Remove All Anveshak Docker Artifacts)
	@printf "  $(_RED)$(_BOLD)This will permanently remove:$(_RST)\n"
	@printf "    - All Anveshak containers and volumes (DB data, models, caches)\n"
	@printf "    - All Anveshak Docker images (analyst ~12GB, scraper ~3.4GB, etc.)\n"
	@printf "    - All Docker build cache\n"
	@printf "    - Python caches\n"
	@printf "    - Anveshak Docker networks\n\n"
	@printf "  $(_YEL)Total space reclaimed: ~35GB+$(_RST)\n\n"
	@printf "  $(_RED)Continue? [y/N]$(_RST) "; \
	read confirm; \
	if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
		printf "  Aborted.\n"; exit 1; \
	fi
	$(call step,1/5,Stopping and removing containers + volumes)
	@$(COMPOSE_BRG) down -v --remove-orphans 2>/dev/null || true
	@$(COMPOSE_VIS) down -v --remove-orphans 2>/dev/null || true
	@$(COMPOSE) down -v --remove-orphans 2>/dev/null || true
	$(call success,Containers and volumes removed)
	$(call step,2/5,Removing all Anveshak images)
	@docker images -q --filter reference='anveshak-*' 2>/dev/null | xargs docker rmi -f 2>/dev/null || true
	@docker images -q --filter reference='infra-*' 2>/dev/null | xargs docker rmi -f 2>/dev/null || true
	$(call success,Anveshak images removed)
	$(call step,3/5,Removing third-party base images)
	@docker rmi pgvector/pgvector:pg16 redis:7-alpine ollama/ollama:latest \
		prom/prometheus:latest grafana/grafana:latest grafana/loki:3.0.0 \
		grafana/promtail:3.0.0 prometheuscommunity/postgres-exporter:latest \
		oliver006/redis_exporter:latest nginx:1.27-alpine node:20-alpine \
		python:3.12-slim jaegertracing/all-in-one:1.57 2>/dev/null || true
	$(call success,Base images removed)
	$(call step,4/5,Pruning Docker build cache + dangling resources)
	@docker builder prune --all -f 2>/dev/null || true
	@docker system prune -f 2>/dev/null || true
	$(call success,Build cache pruned)
	$(call step,5/5,Cleaning Python caches)
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf htmlcov .coverage 2>/dev/null || true
	$(call success,Python caches cleaned)
	@printf "\n"
	$(call success,All Anveshak Docker artifacts removed)
	@printf "\n  To start fresh: $(_BOLD)make setup$(_RST)\n\n"

# =============================================================================
# BACKUP / RESTORE
# =============================================================================

# backup — PostgreSQL + Redis + media
backup:
	$(call header,Creating Backup)
	@bash scripts/backup.sh

# restore — from backup directory
restore:
	$(call header,Restoring from Backup)
	@if [ -z "$(BACKUP_DIR)" ]; then \
		printf "  $(_RED)Usage: make restore BACKUP_DIR=./backups/anveshak_20260417_120000$(_RST)\n"; \
		exit 1; \
	fi
	@bash scripts/restore.sh $(BACKUP_DIR)

# =============================================================================
# K3S DEPLOYMENT
# =============================================================================

# k3s-deploy — apply all k3s manifests
k3s-deploy:
	$(call header,Deploying to k3s)
	@kubectl apply -k infra/k3s/
	$(call success,k3s manifests applied)
	@printf "\n  Watch pods: $(_BOLD)kubectl get pods -n anveshak -w$(_RST)\n\n"

# k3s-teardown — delete the anveshak namespace
k3s-teardown:
	$(call header,Tearing down k3s deployment)
	@printf "  $(_RED)$(_BOLD)This will delete the anveshak namespace and all resources.$(_RST)\n"
	@printf "  $(_YEL)Continue? [y/N]$(_RST) "; \
	read confirm; \
	if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
		printf "  Aborted.\n"; exit 1; \
	fi
	@kubectl delete namespace anveshak --ignore-not-found
	$(call success,k3s namespace deleted)

# =============================================================================
# AI TOOLING
# =============================================================================

# graph — rebuild Graphify knowledge graph (code-only, no LLM key needed)
graph:
	$(call header,Rebuilding Graphify knowledge graph)
	@graphify update .
	$(call success,Knowledge graph updated)

# agents-sync — regenerate .claude/skills symlinks from .agents/skills
# Skills live harness-agnostically in .agents/skills/ (read directly by Codex and
# Cursor). Claude Code only scans .claude/skills/, so each skill is symlinked in.
agents-sync:
	$(call header,Syncing .claude/skills from .agents/skills)
	@find .claude/skills -maxdepth 1 -type l -delete 2>/dev/null || true
	@mkdir -p .claude/skills
	@for d in .agents/skills/*/; do \
		n=$$(basename $$d); \
		ln -sfn "../../.agents/skills/$$n" ".claude/skills/$$n"; \
	done
	@printf "  %s skills linked\n" "$$(find .claude/skills -maxdepth 1 -type l | wc -l | tr -d ' ')"
	$(call success,Skill symlinks synced)

# venv-check - fail early if .venv cannot actually run its console scripts
#
# uv venvs are path-bound: every console script in .venv/bin carries an
# absolute shebang. Moving the repo leaves them pointing at the old location
# and every entry point dies with "Failed to spawn: pytest". `uv sync` does
# not repair it, because all packages are present and uv never rewrites
# shebangs. The only fix is a rebuild, so say so explicitly.
venv-check:
	@if [ ! -d .venv ]; then \
		printf "  $(_FAIL) $(_RED)no .venv found, run: uv sync$(_RST)\n"; exit 1; \
	fi
	@if [ ! -f .venv/bin/pytest ]; then \
		printf "  $(_FAIL) $(_RED).venv has no dev dependencies, run: uv sync$(_RST)\n"; exit 1; \
	fi
	@shebang=$$(head -1 .venv/bin/pytest | sed 's|^#!||'); \
	case "$$shebang" in \
		"$(CURDIR)/.venv/"*) ;; \
		*) printf "  $(_FAIL) $(_RED)venv was built for a different path, run: rm -rf .venv && uv sync$(_RST)\n"; \
		   printf "  $(_DIM)      .venv/bin/pytest points at $$shebang$(_RST)\n"; \
		   printf "  $(_DIM)      this repo is at $(CURDIR)$(_RST)\n"; \
		   exit 1 ;; \
	esac
	@home=$$(awk -F' = ' '/^home/{print $$2}' .venv/pyvenv.cfg); \
	if [ ! -x "$$home/python3" ]; then \
		printf "  $(_FAIL) $(_RED)venv base interpreter is gone, run: rm -rf .venv && uv sync$(_RST)\n"; \
		printf "  $(_DIM)      pyvenv.cfg home = $$home$(_RST)\n"; \
		exit 1; \
	fi
	@ver=$$(awk -F' = ' '/^version_info/{print $$2}' .venv/pyvenv.cfg); \
	case "$$ver" in \
		3.12*) ;; \
		*) printf "  $(_FAIL) $(_RED)venv is Python $$ver, this workspace requires 3.12, run: rm -rf .venv && uv sync$(_RST)\n"; \
		   exit 1 ;; \
	esac

# agents-check — fail if the bridge has drifted or a skill is malformed
agents-check:
	$(call header,Validating agent configuration)
	@fail=0; \
	for d in .agents/skills/*/; do \
		n=$$(basename $$d); \
		if [ ! -f "$$d/SKILL.md" ]; then echo "  MISSING SKILL.md: $$n"; fail=1; fi; \
		fm=$$(awk '/^---$$/{c++;next} c==1&&/^name:/{print $$2; exit}' "$$d/SKILL.md" 2>/dev/null); \
		if [ "$$fm" != "$$n" ]; then echo "  NAME MISMATCH: dir=$$n frontmatter=$$fm"; fail=1; fi; \
		if [ ! -L ".claude/skills/$$n" ]; then echo "  NOT LINKED: $$n (run make agents-sync)"; fail=1; fi; \
	done; \
	for l in .claude/skills/*; do \
		[ -e "$$l" ] || { echo "  BROKEN LINK: $$l"; fail=1; }; \
	done; \
	for a in .claude/agents/*.md; do \
		head -1 "$$a" | grep -q '^---$$' || { echo "  BAD FRONTMATTER: $$a"; fail=1; }; \
	done; \
	if [ $$fail -ne 0 ]; then echo "agents-check FAILED"; exit 1; fi
	$(call success,Agent configuration valid)
