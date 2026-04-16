# =============================================================================
# ANVESHAK — Makefile
# =============================================================================
# Usage:
#   make up           — start core stack
#   make up-vision    — start core + vision service
#   make up-bridge    — start core + Drishti bridge
#   make down         — stop all containers
#   make init         — first-run setup (pull models + run migrations)
#   make migrate      — run Alembic migrations
#   make test         — run all tests
#   make seed-demo    — load demo scenario (Indian Navy)
#   make demo-check   — verify demo is ready
#   make logs         — tail all service logs
#   make ps           — show container status
# =============================================================================

COMPOSE      := docker compose --env-file .env -p anveshak -f infra/compose.yml
COMPOSE_VIS  := $(COMPOSE) -f infra/compose.vision.yml
COMPOSE_BRG  := $(COMPOSE) -f infra/compose.bridge.yml
UV           := uv run

.PHONY: all up up-vision up-bridge build build-vision down restart ps logs \
        init pull-models migrate migrate-hnsw seed-demo \
        fresh fresh-all \
        test unit integration test-unit test-integration test-e2e \
        demo-check validate validate-vision health lint format typecheck \
        clean clean-volumes

# -----------------------------------------------------------------------------
# Fresh start shortcuts
# -----------------------------------------------------------------------------

# fresh — rebuild + start + seed + verify (skips model pull/migrations)
fresh: build up seed-demo demo-check

# fresh-all — full first-run sequence (includes model pull + migrations)
fresh-all: build up init seed-demo demo-check

# -----------------------------------------------------------------------------
# Docker Compose lifecycle
# -----------------------------------------------------------------------------

# build — rebuild all images (run once after code changes)
build:
	@echo "Building Anveshak images..."
	$(COMPOSE) build

build-vision:
	$(COMPOSE_VIS) build

# up — start with existing images (fast restart, no rebuild)
up:
	@echo "Starting Anveshak core stack..."
	$(COMPOSE) up -d
	@echo "Services starting. Run 'make ps' to check health."

up-vision:
	@echo "Starting Anveshak + Vision service..."
	$(COMPOSE_VIS) up -d

up-bridge:
	@echo "Starting Anveshak + Drishti bridge..."
	$(COMPOSE_BRG) up -d

down:
	$(COMPOSE_BRG) down 2>/dev/null || true
	$(COMPOSE_VIS) down 2>/dev/null || true
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

logs-%:
	$(COMPOSE) logs -f --tail=100 $*

# -----------------------------------------------------------------------------
# First-run initialisation
# -----------------------------------------------------------------------------

init: pull-models migrate
	@echo ""
	@echo "Anveshak initialised."
	@echo "  API:       http://localhost:8000"
	@echo "  Frontend:  http://localhost:3000"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana:   http://localhost:3001"
	@echo ""
	@echo "Run 'make seed-demo' to load the demo scenario."

pull-models:
	@echo "Pulling Ollama models (this may take several minutes on first run)..."
	$(COMPOSE) exec -T ollama ollama pull $(shell grep OLLAMA_REPORT_MODEL .env 2>/dev/null | cut -d= -f2 || echo "mistral:7b")
	$(COMPOSE) exec -T ollama ollama pull $(shell grep OLLAMA_CLUSTER_MODEL .env 2>/dev/null | cut -d= -f2 || echo "llama3.2:3b")
	@echo "Models ready."

# Pull upgraded models when hardware is available (see hardware.md)
pull-models-gpu:
	@echo "Pulling GPU-tier Ollama models..."
	$(COMPOSE) exec ollama ollama pull llama3.1:8b
	$(COMPOSE) exec ollama ollama pull llama3.1:70b

# -----------------------------------------------------------------------------
# Database migrations
# -----------------------------------------------------------------------------

migrate:
	@echo "Running Alembic migrations..."
	$(COMPOSE) exec -T api alembic upgrade head
	@echo "Migrations complete."

migrate-status:
	cd services/api && $(UV) --package anveshak-api alembic current

# Upgrade pgvector index to HNSW — run when 32GB RAM available (see hardware.md)
migrate-hnsw:
	@echo "Upgrading pgvector index to HNSW (requires 32GB RAM)..."
	cd services/api && $(UV) --package anveshak-api alembic upgrade hnsw
	@echo "HNSW migration complete."

migrate-rollback:
	cd services/api && $(UV) --package anveshak-api alembic downgrade -1

# -----------------------------------------------------------------------------
# Demo seed
# -----------------------------------------------------------------------------

seed-demo:
	@echo "Loading Anveshak demo scenario..."
	@$(COMPOSE) exec -T postgres psql -U anveshak -d anveshak < scripts/seed_demo.sql
	@echo "Demo scenario loaded. Log in at http://localhost:3000"
	@echo "  Username: demo@anveshak.local"
	@echo "  Password: AnveshakDemo2024!"

# -----------------------------------------------------------------------------
# Testing
# -----------------------------------------------------------------------------

test: test-unit test-integration

unit: test-unit

integration: test-integration

test-unit:
	@echo "Running unit tests..."
	$(UV) pytest tests/unit/ -v --tb=short -q

test-integration:
	@echo "Running integration tests (requires running stack)..."
	$(UV) pytest tests/integration/ -v --tb=short -q -m integration

test-e2e:
	@echo "Running e2e tests (requires full stack + live credentials)..."
	E2E_LIVE=1 $(UV) pytest tests/e2e/ -v --tb=short -m e2e

test-coverage:
	$(UV) pytest tests/unit/ tests/integration/ \
		--cov=services --cov-report=term-missing --cov-report=html:htmlcov

# -----------------------------------------------------------------------------
# Health + demo readiness checks
# -----------------------------------------------------------------------------

health:
	@echo "Checking service health..."
	@curl -sf http://localhost:8000/health | python3 -m json.tool || echo "API: DOWN"
	@$(COMPOSE) ps scraper | grep -q "healthy" && echo "Scraper: healthy (worker)" || echo "Scraper: DOWN"
	@$(COMPOSE) ps social  | grep -q "healthy" && echo "Social: healthy (worker)"  || echo "Social: DOWN"
	@$(COMPOSE) ps analyst | grep -q "healthy" && echo "Analyst: healthy (worker)" || echo "Analyst: DOWN"
	@$(COMPOSE) exec -T reporter curl -sf http://localhost:8005/health 2>/dev/null | python3 -m json.tool || echo "Reporter: DOWN"
	@$(COMPOSE) exec -T ollama ollama list 2>/dev/null | head -1 && echo "Ollama: healthy" || echo "Ollama: DOWN"

demo-check:
	@echo "Running demo readiness verification..."
	$(UV) python scripts/demo_check.py

validate:
	@echo "Running Anveshak pipeline validation (on-demand E2E check)..."
	$(UV) python scripts/validate_pipeline.py

validate-vision:
	@echo "Running Anveshak vision pipeline validation (M4 deepfake E2E check)..."
	$(UV) python scripts/validate_vision.py

# Verify all Pydantic models have non-optional labels field
verify-labels:
	@echo "Verifying labels non-optional constraint..."
	$(UV) --package anveshak-sdk python scripts/verify_labels.py

# Verify report immutability constraints
verify-reports:
	@echo "Verifying report immutability..."
	$(UV) --package anveshak-sdk python scripts/verify_reports_immutable.py

# -----------------------------------------------------------------------------
# Code quality
# -----------------------------------------------------------------------------

lint:
	$(UV) run ruff check services/ sdk/ tests/ scripts/

format:
	$(UV) run ruff format services/ sdk/ tests/ scripts/
	$(UV) run ruff check --fix services/ sdk/ tests/ scripts/

typecheck:
	$(UV) run pyright services/ sdk/

security-scan:
	$(UV) run bandit -r services/ sdk/ -ll --quiet

# -----------------------------------------------------------------------------
# Maintenance
# -----------------------------------------------------------------------------

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

clean-volumes:
	@echo "WARNING: This will delete all PostgreSQL, Redis, and Ollama data."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	$(COMPOSE) down -v

# Shell into a service container
shell-%:
	$(COMPOSE) exec $* /bin/bash
