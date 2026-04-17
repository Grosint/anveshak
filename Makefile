# =============================================================================
# ANVESHAK — AI-OSINT Platform Makefile
# =============================================================================
#
# SETUP (new developer):
#   make setup            full first-run: syscheck -> build -> up -> migrate -> pull-models -> validate
#
# LIFECYCLE:
#   make up               start core stack (no rebuild)
#   make up-vision        core + vision overlay
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
#
# VALIDATE:
#   make syscheck         system requirements check (RAM, disk, Docker, ports)
#   make health           quick health check (are services up?)
#   make validate         full pipeline validation (7 stages)
#   make validate-vision  vision pipeline validation (M4 deepfake)
#
# TEST:
#   make test             unit + integration
#   make test-unit        unit tests only
#   make test-integration integration tests (requires running stack)
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

.PHONY: all setup up up-vision up-bridge build build-vision down restart \
        ps logs init pull-models migrate migrate-status migrate-hnsw \
        migrate-rollback seed-demo \
        fresh fresh-all \
        test test-unit test-integration test-e2e test-coverage \
        demo-check validate validate-vision health syscheck \
        lint format typecheck security-scan \
        clean clean-containers clean-volumes clean-cache purge \
        verify-labels verify-reports shell-%

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

# Check .env exists
define check_env
	@if [ ! -f .env ]; then \
		printf "\n$(_BOLD)$(_RED)  ERROR: .env file not found$(_RST)\n"; \
		printf "  $(_INFO) Run: $(_BOLD)cp .env.example .env$(_RST) and fill in your secrets\n\n"; \
		exit 1; \
	fi
endef

# ---------------------------------------------------------------------------
# SETUP — Full first-run for new developers
# ---------------------------------------------------------------------------

setup:
	$(call header,ANVESHAK — First-Run Setup)
	$(call step,Step 1/6,System requirements check)
	@$(UV) python scripts/syscheck.py || { \
		printf "\n"; \
		$(call warn,System does not meet minimum requirements — see above); \
		printf "  $(_INFO) Continue anyway? [y/N] "; \
		read confirm; \
		if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then exit 1; fi; \
	}
	$(call check_env)
	$(call step,Step 2/6,Building Docker images)
	@$(COMPOSE) build --quiet
	$(call success,Images built)
	$(call step,Step 3/6,Starting services)
	@$(COMPOSE) up -d --remove-orphans
	$(call success,Services started)
	$(call step,Step 4/6,Waiting for services to be healthy...)
	@sleep 10
	$(call step,Step 5/6,Running migrations + pulling Ollama model)
	@$(COMPOSE) exec -T api alembic upgrade head 2>&1 | tail -1
	$(call success,Migrations applied)
	@printf "  $(_WORK) Pulling Ollama model (this may take several minutes on first run)...\n"
	@$(COMPOSE) exec -T ollama ollama pull $$(grep -E '^OLLAMA_MODEL=' .env 2>/dev/null | cut -d= -f2 | sed 's/#.*//' | tr -d ' ' || echo "qwen2:7b") 2>&1 | tail -3
	$(call success,Ollama model ready)
	$(call step,Step 6/6,Validating pipeline)
	@$(UV) python scripts/validate_pipeline.py
	$(call header,Setup Complete)
	@printf "  $(_GRN)$(_BOLD)Anveshak is ready!$(_RST)\n\n"
	@printf "  Analyst workbench:  $(_CYN)http://localhost:3000$(_RST)\n"
	@printf "  API:                $(_CYN)http://localhost:8000$(_RST)\n"
	@printf "  Grafana:            $(_CYN)http://localhost:3001$(_RST)\n"
	@printf "  Prometheus:         $(_CYN)http://localhost:9090$(_RST)\n\n"
	@printf "  Next: $(_BOLD)make seed-demo$(_RST) to load the demo scenario\n"
	@printf "        $(_BOLD)make validate$(_RST)  to re-run validation anytime\n\n"

# ---------------------------------------------------------------------------
# Docker Compose lifecycle
# ---------------------------------------------------------------------------

build:
	$(call header,Building Docker Images)
	$(call check_env)
	@$(COMPOSE) build
	$(call success,All images built)

build-vision:
	$(call header,Building Docker Images (+ Vision))
	$(call check_env)
	@$(COMPOSE_VIS) build
	$(call success,All images built (including vision))

up:
	$(call header,Starting Anveshak Core Stack)
	$(call check_env)
	@$(COMPOSE) up -d --remove-orphans
	$(call success,Core stack started)
	@printf "\n  Run $(_BOLD)make ps$(_RST) to check health status\n"
	@printf "  Run $(_BOLD)make health$(_RST) for quick health check\n\n"

up-vision:
	$(call header,Starting Anveshak + Vision Service)
	$(call check_env)
	@$(COMPOSE_VIS) up -d --remove-orphans
	$(call success,Core + Vision stack started)

up-bridge:
	$(call header,Starting Anveshak + Drishti Bridge)
	$(call check_env)
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

migrate-status:
	$(call header,Migration Status)
	@cd services/api && $(UV) --package anveshak-api alembic current

migrate-rollback:
	$(call header,Rolling Back Migration)
	@cd services/api && $(UV) --package anveshak-api alembic downgrade -1
	$(call success,Rolled back one revision)

# Upgrade pgvector index to HNSW — run when 32GB RAM available (see hardware.md)
migrate-hnsw:
	$(call header,Upgrading pgvector Index to HNSW)
	$(call warn,This requires 32GB RAM — see hardware.md)
	@cd services/api && $(UV) --package anveshak-api alembic upgrade hnsw
	$(call success,HNSW migration complete)

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

# ---------------------------------------------------------------------------
# Fresh start shortcuts
# ---------------------------------------------------------------------------

fresh: clean-containers build up migrate validate
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
	@$(MAKE) --no-print-directory up
	@sleep 8
	@$(MAKE) --no-print-directory migrate
	@$(MAKE) --no-print-directory pull-models
	@$(MAKE) --no-print-directory seed-demo
	@$(MAKE) --no-print-directory validate
	$(call success,Full fresh start complete)

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

test: test-unit test-integration

unit: test-unit

integration: test-integration

test-unit:
	$(call header,Running Unit Tests)
	@$(UV) pytest tests/unit/ -v --tb=short -q

test-integration:
	$(call header,Running Integration Tests)
	$(call info,Requires running stack — run make up first)
	@$(UV) pytest tests/integration/ -v --tb=short -q -m integration

test-e2e:
	$(call header,Running End-to-End Tests)
	$(call info,Requires full stack + live credentials)
	@E2E_LIVE=1 $(UV) pytest tests/e2e/ -v --tb=short -m e2e

test-coverage:
	$(call header,Running Tests with Coverage)
	@$(UV) pytest tests/unit/ tests/integration/ \
		--cov=services --cov-report=term-missing --cov-report=html:htmlcov
	$(call success,Coverage report: htmlcov/index.html)

# ---------------------------------------------------------------------------
# Health + validation
# ---------------------------------------------------------------------------

syscheck:
	@$(UV) python scripts/syscheck.py

health:
	$(call header,Service Health Check)
	@printf "  %-20s %s\n" "SERVICE" "STATUS"
	@printf "  %-20s %s\n" "───────────────────" "──────────────────────────"
	@for svc in api:8000 scraper:8001 social:8002 analyst:8004 reporter:8005; do \
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

validate-all: validate validate-vision

# Verify all Pydantic models have non-optional labels field
verify-labels:
	$(call header,Verifying Labels Constraint)
	@$(UV) --package anveshak-sdk python scripts/verify_labels.py

# Verify report immutability constraints
verify-reports:
	$(call header,Verifying Report Immutability)
	@$(UV) --package anveshak-sdk python scripts/verify_reports_immutable.py

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

lint:
	$(call header,Linting)
	@$(UV) run ruff check services/ sdk/ tests/ scripts/

format:
	$(call header,Formatting)
	@$(UV) run ruff format services/ sdk/ tests/ scripts/
	@$(UV) run ruff check --fix services/ sdk/ tests/ scripts/
	$(call success,Formatted)

typecheck:
	$(call header,Type Checking)
	@$(UV) run pyright services/ sdk/

security-scan:
	$(call header,Security Scan)
	@$(UV) run bandit -r services/ sdk/ -ll --quiet
	$(call success,No security issues found)

# ---------------------------------------------------------------------------
# Maintenance / Cleanup (graduated)
# ---------------------------------------------------------------------------

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
	@docker image prune -f 2>/dev/null || true
	$(call success,Full purge complete)
	@printf "\n  To start fresh: $(_BOLD)make setup$(_RST)\n\n"
