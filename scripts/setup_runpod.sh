#!/usr/bin/env bash
# =============================================================================
# ANVESHAK — RunPod GPU Pod Setup Script
#
# One-command setup for Anveshak on a RunPod GPU Pod.
# Run this ONCE after SSH-ing into a fresh pod.
#
# Prerequisites:
#   - RunPod GPU Pod (RTX A4000/T4/RTX 3090, 32GB+ RAM, 200GB+ disk)
#   - Template: "RunPod Pytorch" or any template with Docker + NVIDIA runtime
#   - SSH access enabled
#
# Usage:
#   # Option 1: Clone repo and run
#   git clone <your-repo-url> anveshak && cd anveshak
#   bash scripts/setup_runpod.sh
#
#   # Option 2: With social adapter credentials
#   TELEGRAM_API_ID=12345 TELEGRAM_API_HASH=abc123 \
#   TELEGRAM_SESSION_STRING=... X_BEARER_TOKEN=... \
#   bash scripts/setup_runpod.sh
#
# What this script does:
#   1. Verifies RunPod environment (GPU, Docker, NVIDIA runtime)
#   2. Installs missing tools (docker compose plugin, uv)
#   3. Generates .env with secure secrets + GPU-optimised settings
#   4. Runs make setup (build → infra → migrate → models → validate)
#   5. Sets up production topics (4 defence/security topics, 21 sources)
#   6. Prints access URLs (RunPod proxy URLs)
#
# Estimated time: ~15-20 min (first run, includes Docker image builds + model downloads)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --help|-h)
            echo "Usage: bash scripts/setup_runpod.sh [--dry-run]"
            echo ""
            echo "Options:"
            echo "  --dry-run   Simulate all steps without executing (works on macOS)"
            echo ""
            echo "Environment variables (optional):"
            echo "  TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_STRING"
            echo "  X_BEARER_TOKEN"
            echo "  RUNPOD_POD_ID  (auto-set on RunPod pods)"
            exit 0
            ;;
        *) echo "Unknown argument: $arg (use --help)"; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
RST="\033[0m"
BOLD="\033[1m"
RED="\033[31m"
GRN="\033[32m"
YEL="\033[33m"
BLU="\033[34m"
CYN="\033[36m"
DIM="\033[2m"

# Disable colours if not a terminal
if [ ! -t 1 ]; then
    RST="" BOLD="" RED="" GRN="" YEL="" BLU="" CYN="" DIM=""
fi

header() { printf "\n${BOLD}${BLU}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}\n  ${BOLD}${BLU}%s${RST}\n${BOLD}${BLU}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}\n\n" "$1"; }
step()   { printf "  ${CYN}⟳${RST} ${BOLD}%s${RST} %s\n" "$1" "$2"; }
ok()     { printf "  ${GRN}✓${RST} %s\n" "$1"; }
warn()   { printf "  ${YEL}!${RST} %s\n" "$1"; }
fail()   { printf "  ${RED}✗${RST} %s\n" "$1"; }
skip()   { printf "  ${DIM}⊘ [DRY RUN] %s${RST}\n" "$1"; }
die()    { fail "$1"; if [ "$DRY_RUN" = true ]; then warn "Would abort here in live mode"; return 0 2>/dev/null || true; else exit 1; fi; }

# ---------------------------------------------------------------------------
# Step 0: Detect environment
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" = true ]; then
    header "ANVESHAK — RunPod Setup (DRY RUN)"
    printf "  ${YEL}${BOLD}DRY RUN MODE — no changes will be made${RST}\n\n"
else
    header "ANVESHAK — RunPod GPU Pod Setup"
fi

step "Step 0/7" "Detecting environment..."

# Platform check — relaxed in dry-run
PLATFORM="$(uname -s)"
if [ "$PLATFORM" = "Linux" ]; then
    ok "Platform: Linux"
elif [ "$DRY_RUN" = true ]; then
    warn "Platform: $PLATFORM (not Linux — dry run will simulate Linux/GPU values)"
else
    die "This script is for Linux (RunPod). Got: $PLATFORM"
fi

# Detect RunPod environment
RUNPOD_POD_ID="${RUNPOD_POD_ID:-}"
if [ -n "$RUNPOD_POD_ID" ]; then
    ok "RunPod pod detected: $RUNPOD_POD_ID"
elif [ "$DRY_RUN" = true ]; then
    RUNPOD_POD_ID="abc123def456"
    warn "RUNPOD_POD_ID not set — using simulated ID: $RUNPOD_POD_ID"
else
    warn "RUNPOD_POD_ID not set — may not be a RunPod pod (continuing anyway)"
fi

# Check we're in the anveshak repo root
if [ ! -f "CLAUDE.md" ] || [ ! -f "Makefile" ] || [ ! -f "infra/compose.yml" ]; then
    die "Not in anveshak repo root. Run: cd /path/to/anveshak"
fi
ok "Anveshak repo root detected: $(pwd)"

# Check disk space (need 50GB+ free)
if [ "$PLATFORM" = "Linux" ]; then
    DISK_FREE_GB=$(df -BG --output=avail . | tail -1 | tr -dc '0-9')
elif [ "$DRY_RUN" = true ]; then
    # macOS df doesn't support -BG, use a different approach
    DISK_FREE_KB=$(df -k . | tail -1 | awk '{print $4}')
    DISK_FREE_GB=$((DISK_FREE_KB / 1024 / 1024))
else
    DISK_FREE_GB=0
fi
if [ "$DISK_FREE_GB" -lt 50 ]; then
    if [ "$DRY_RUN" = true ]; then
        warn "Disk space: ${DISK_FREE_GB}GB free (need 50GB+ — would fail in live mode)"
    else
        die "Need 50GB+ free disk. Available: ${DISK_FREE_GB}GB. Use a larger volume."
    fi
else
    ok "Disk space: ${DISK_FREE_GB}GB free"
fi

# Check RAM (need 16GB+)
if [ "$PLATFORM" = "Linux" ]; then
    RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    RAM_GB=$((RAM_KB / 1024 / 1024))
elif [ "$PLATFORM" = "Darwin" ]; then
    RAM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
    RAM_GB=$((RAM_BYTES / 1024 / 1024 / 1024))
else
    RAM_GB=0
fi
if [ "$RAM_GB" -lt 16 ]; then
    if [ "$DRY_RUN" = true ]; then
        warn "RAM: ${RAM_GB}GB (need 16GB+ — would fail in live mode)"
    else
        die "Need 16GB+ RAM. Available: ${RAM_GB}GB. Use a larger pod."
    fi
else
    ok "RAM: ${RAM_GB}GB"
fi

# ---------------------------------------------------------------------------
# Step 1: Verify GPU + NVIDIA runtime
# ---------------------------------------------------------------------------
step "Step 1/7" "Verifying GPU and NVIDIA runtime..."

if command -v nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    GPU_VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
    if [ -z "$GPU_NAME" ]; then
        die "No GPU detected. Ensure your RunPod pod has a GPU attached."
    fi
    ok "GPU: $GPU_NAME (${GPU_VRAM}MB VRAM)"
elif [ "$DRY_RUN" = true ]; then
    GPU_NAME="NVIDIA RTX A4000 (simulated)"
    GPU_VRAM="16384"
    warn "nvidia-smi not found — simulating: $GPU_NAME (${GPU_VRAM}MB VRAM)"
else
    die "nvidia-smi not found. Use a RunPod template with NVIDIA drivers (e.g. RunPod Pytorch)"
fi

# Check NVIDIA container runtime
if [ "$DRY_RUN" = true ]; then
    skip "NVIDIA container runtime check"
elif docker info 2>/dev/null | grep -q "nvidia"; then
    ok "NVIDIA container runtime available"
elif [ -f /etc/docker/daemon.json ] && grep -q "nvidia" /etc/docker/daemon.json 2>/dev/null; then
    ok "NVIDIA runtime configured in daemon.json"
else
    warn "NVIDIA container runtime not detected — vision GPU acceleration may not work"
    warn "Vision will fall back to CPU (slower but functional)"
fi

# ---------------------------------------------------------------------------
# Step 2: Install missing tools
# ---------------------------------------------------------------------------
step "Step 2/7" "Checking and installing dependencies..."

if [ "$DRY_RUN" = true ]; then
    # In dry-run, just check what exists locally and report what would happen
    if command -v docker &>/dev/null; then
        ok "Docker: $(docker --version | head -1)"
    else
        skip "Would install Docker (required — must use RunPod template with Docker)"
    fi
    if docker compose version &>/dev/null 2>&1; then
        ok "Docker Compose: $(docker compose version --short)"
    else
        skip "Would install Docker Compose plugin"
    fi
    if command -v uv &>/dev/null; then
        ok "uv: $(uv --version)"
    else
        skip "Would install uv (curl -LsSf https://astral.sh/uv/install.sh | sh)"
    fi
    if command -v make &>/dev/null; then
        ok "make: $(make --version | head -1)"
    else
        skip "Would install make (apt-get install make)"
    fi
    if command -v python3 &>/dev/null; then
        ok "python3: $(python3 --version)"
    else
        skip "Would require python3 (pre-installed on RunPod)"
    fi
else
    # Docker
    if ! command -v docker &>/dev/null; then
        warn "Docker not found — installing..."
        curl -fsSL https://get.docker.com | sh >/dev/null 2>&1
        command -v docker &>/dev/null || die "Docker installation failed"
        ok "Docker installed: $(docker --version | head -1)"
        # Install NVIDIA Container Toolkit for GPU passthrough
        if command -v nvidia-smi &>/dev/null; then
            step "" "Installing NVIDIA Container Toolkit..."
            curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg 2>/dev/null
            curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
                sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
                tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
            apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq nvidia-container-toolkit >/dev/null 2>&1
            nvidia-ctk runtime configure --runtime=docker >/dev/null 2>&1
            systemctl restart docker 2>/dev/null || service docker restart 2>/dev/null || true
            ok "NVIDIA Container Toolkit installed"
        fi
    else
        ok "Docker: $(docker --version | head -1)"
    fi

    # Docker Compose plugin
    if docker compose version &>/dev/null; then
        ok "Docker Compose: $(docker compose version --short)"
    else
        warn "Docker Compose plugin not found — installing..."
        DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
        mkdir -p "$DOCKER_CONFIG/cli-plugins"
        COMPOSE_VERSION=$(curl -sL https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name"' | head -1 | cut -d'"' -f4)
        curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
            -o "$DOCKER_CONFIG/cli-plugins/docker-compose"
        chmod +x "$DOCKER_CONFIG/cli-plugins/docker-compose"
        docker compose version &>/dev/null || die "Docker Compose installation failed"
        ok "Docker Compose installed: $(docker compose version --short)"
    fi

    # uv (Python package manager — needed for make setup)
    if command -v uv &>/dev/null; then
        ok "uv: $(uv --version)"
    else
        warn "uv not found — installing..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
        # Also add to shell profile for future sessions
        if [ -f "$HOME/.bashrc" ]; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        fi
        command -v uv &>/dev/null || die "uv installation failed"
        ok "uv installed: $(uv --version)"
    fi

    # Make
    if ! command -v make &>/dev/null; then
        warn "make not found — installing..."
        apt-get update -qq && apt-get install -y -qq make >/dev/null 2>&1
        command -v make &>/dev/null || die "make installation failed"
    fi
    ok "make: $(make --version | head -1)"

    # python3
    if ! command -v python3 &>/dev/null; then
        die "python3 not found — should be pre-installed on RunPod templates"
    fi
    ok "python3: $(python3 --version)"
fi

# ---------------------------------------------------------------------------
# Step 3: Generate .env with GPU-optimised settings
# ---------------------------------------------------------------------------
step "Step 3/7" "Generating .env with GPU-optimised settings..."

if [ "$DRY_RUN" = true ]; then
    if [ -f .env ]; then
        skip "Would backup existing .env to .env.backup.<timestamp>"
    fi
else
    if [ -f .env ]; then
        warn ".env already exists — backing up to .env.backup.$(date +%s)"
        cp .env ".env.backup.$(date +%s)"
    fi
fi

# Generate secure secrets (safe even in dry-run — just used for display)
PG_PASS=$(openssl rand -hex 16)
API_KEY=$(openssl rand -hex 32)
GRAFANA_PASS=$(openssl rand -hex 12)

# Detect RunPod proxy URL base
# RunPod exposes ports via: https://{POD_ID}-{PORT}.proxy.runpod.net
PROXY_BASE=""
if [ -n "$RUNPOD_POD_ID" ]; then
    PROXY_BASE="https://${RUNPOD_POD_ID}"
    API_URL="${PROXY_BASE}-8000.proxy.runpod.net"
    FRONTEND_URL="${PROXY_BASE}-3000.proxy.runpod.net"
    GRAFANA_URL="${PROXY_BASE}-3001.proxy.runpod.net"
else
    API_URL="http://localhost:8000"
    FRONTEND_URL="http://localhost:3000"
    GRAFANA_URL="http://localhost:3001"
fi

# Pick GPU-tier settings based on VRAM
VRAM_MB=${GPU_VRAM:-0}
if [ "$VRAM_MB" -ge 20000 ]; then
    # 24GB+ VRAM (RTX 3090, RTX 4090, A5000, A6000)
    YOLO_SIZE="xlarge"
    DEEPFAKE_MODEL="dire"
    OLLAMA_PARALLEL=4
    ANALYST_REPLICAS=2
elif [ "$VRAM_MB" -ge 14000 ]; then
    # 16GB VRAM (T4, A4000, RTX 4070 Ti)
    YOLO_SIZE="medium"
    DEEPFAKE_MODEL="efficientnet"
    OLLAMA_PARALLEL=2
    ANALYST_REPLICAS=1
else
    # <16GB VRAM
    YOLO_SIZE="nano"
    DEEPFAKE_MODEL="efficientnet"
    OLLAMA_PARALLEL=2
    ANALYST_REPLICAS=1
fi

# Read social credentials from environment (passed at script invocation)
TELE_ID="${TELEGRAM_API_ID:-}"
TELE_HASH="${TELEGRAM_API_HASH:-}"
TELE_SESSION="${TELEGRAM_SESSION_STRING:-}"
TELE_ENABLED="false"
if [ -n "$TELE_ID" ] && [ -n "$TELE_HASH" ] && [ -n "$TELE_SESSION" ]; then
    TELE_ENABLED="true"
fi

X_TOKEN="${X_BEARER_TOKEN:-}"
X_ENABLED="false"
if [ -n "$X_TOKEN" ]; then
    X_ENABLED="true"
fi

if [ "$DRY_RUN" = true ]; then
    # In dry-run, print what .env would contain but don't write it
    ok ".env would be generated (not written in dry-run)"
    cat << DRYEOF

  ${BOLD}GPU-tier settings that would be applied:${RST}
    VISION_DEVICE=cuda
    YOLO_MODEL_SIZE=${YOLO_SIZE}
    VISION_DEEPFAKE_VIDEO_MODEL=${DEEPFAKE_MODEL}
    OLLAMA_KEEP_ALIVE=-1
    OLLAMA_NUM_PARALLEL=${OLLAMA_PARALLEL}
    OLLAMA_REPORT_TIMEOUT_S=120
    ANALYST_WORKER_REPLICAS=${ANALYST_REPLICAS}

  ${BOLD}URLs (based on RUNPOD_POD_ID=${RUNPOD_POD_ID}):${RST}
    VITE_API_BASE_URL=${API_URL}
    API_ALLOWED_ORIGINS=${FRONTEND_URL}

  ${BOLD}Social adapters:${RST}
    TELEGRAM_ADAPTER_ENABLED=${TELE_ENABLED}
    X_ADAPTER_ENABLED=${X_ENABLED}

  ${BOLD}Env vars that would be set (${RST}$(grep -c '^[A-Z]' .env.example 2>/dev/null || echo "~60")${BOLD} total):${RST}
    Core secrets: POSTGRES_PASSWORD, API_SECRET_KEY, JWT_SECRET_KEY, GRAFANA_ADMIN_PASSWORD
    LLM: OLLAMA_MODEL=qwen2:7b, OLLAMA_KEEP_ALIVE=-1
    Vision: VISION_DEVICE=cuda, YOLO_MODEL_SIZE=${YOLO_SIZE}
    NLP: SPACY_EN_MODEL=en_core_web_md, TRANSLATION_ENABLED=true
    Embeddings: EMBEDDING_MODEL=all-MiniLM-L6-v2 (384-dim)
    Retention: CONTENT_RETENTION_DAYS=0 (keep all data), MEDIA_RETENTION_DAYS=0
DRYEOF

else
cat > .env << ENVEOF
# =============================================================================
# ANVESHAK — RunPod GPU Deployment
# Generated by setup_runpod.sh on $(date -u +"%Y-%m-%d %H:%M UTC")
# GPU: ${GPU_NAME} (${GPU_VRAM}MB VRAM)
# Pod: ${RUNPOD_POD_ID:-local}
# =============================================================================

# --- Core Secrets ---
POSTGRES_PASSWORD=${PG_PASS}
API_SECRET_KEY=${API_KEY}
JWT_SECRET_KEY=${API_KEY}
GRAFANA_ADMIN_PASSWORD=${GRAFANA_PASS}

# --- Application ---
ENVIRONMENT=production
LOG_LEVEL=INFO
VITE_API_BASE_URL=${API_URL}
API_ALLOWED_ORIGINS=${FRONTEND_URL}
JWT_EXPIRE_MINUTES=480
HSTS_ENABLED=false

# --- ARQ ---
ARQ_KEEP_RESULT_S=3600

# --- Ollama (GPU-optimised) ---
OLLAMA_MODEL=qwen2:7b
OLLAMA_KEEP_ALIVE=-1
OLLAMA_NUM_PARALLEL=${OLLAMA_PARALLEL}
OLLAMA_REPORT_TIMEOUT_S=120
OLLAMA_CIRCUIT_BREAKER_THRESHOLD=5
OLLAMA_CIRCUIT_BREAKER_COOLDOWN_S=120

# --- NLP ---
SPACY_EN_MODEL=en_core_web_md

# --- Translation ---
TRANSLATION_ENABLED=true
TRANSLATION_MODEL=facebook/nllb-200-distilled-600M
TRANSLATION_MAX_CHARS=1500
TRANSLATION_MAX_TOKENS=512

# --- Embeddings ---
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384

# --- Vision (GPU) ---
VISION_DEVICE=cuda
YOLO_MODEL_SIZE=${YOLO_SIZE}
VISION_DEEPFAKE_VIDEO_MODEL=${DEEPFAKE_MODEL}
MEDIA_RETENTION_DAYS=0

# --- Scraper ---
SCRAPER_CONCURRENCY=4
SCRAPER_REQUEST_TIMEOUT_S=30
DARKWEB_REQUEST_TIMEOUT_S=90
DARKWEB_CONCURRENCY=2

# --- Telegram ---
TELEGRAM_API_ID=${TELE_ID}
TELEGRAM_API_HASH=${TELE_HASH}
TELEGRAM_SESSION_STRING=${TELE_SESSION}
TELEGRAM_ADAPTER_ENABLED=${TELE_ENABLED}

# --- X / Twitter ---
X_BEARER_TOKEN=${X_TOKEN}
X_ADAPTER_ENABLED=${X_ENABLED}
X_ADAPTER_MODE=polling
X_MONTHLY_READ_CAP=10000

# --- Analyst ---
ANALYST_WORKER_REPLICAS=${ANALYST_REPLICAS}
CONTENT_RETENTION_DAYS=0
CONTENT_ARCHIVE_ROOT=/app/media/archive
MAX_TOPICS_PER_CYCLE=0
HDBSCAN_MIN_CLUSTER_SIZE=3
HDBSCAN_MIN_SAMPLES=2

# --- Credibility Engine ---
CREDIBILITY_DEEPFAKE_DROP=1.0
CREDIBILITY_MIN_AUTO_DROP=1.0
CREDIBILITY_HIGH_THRESHOLD=60.0
CREDIBILITY_CROSS_VERIFY_BOOST=5.0
CREDIBILITY_MIN_AUTO_BOOST=1.0
CREDIBILITY_CONTRADICTION_DROP=5.0
CREDIBILITY_NOISE_RATIO_THRESHOLD=0.6
CREDIBILITY_CONTRADICTION_MIN_ITEMS=5

# --- Signals ---
SIGNAL_WEBHOOK_ENABLED=false

# --- Drishti Bridge (disabled — standalone mode) ---
ANVESHAK_DRISHTI_BRIDGE=false

# --- Observability ---
PROMETHEUS_RETENTION=15d
GRAFANA_ADMIN_USER=admin
OTEL_ENABLED=false
ENVEOF

ok ".env generated with GPU-optimised settings"
fi  # end of DRY_RUN else block for .env generation

# Print credential summary (to terminal only, not logged)
printf "\n"
printf "  ${BOLD}Credentials (save these — shown only once):${RST}\n"
printf "  ├─ Postgres password:  ${PG_PASS}\n"
printf "  ├─ API secret key:     ${API_KEY:0:16}...\n"
printf "  ├─ Grafana password:   ${GRAFANA_PASS}\n"
printf "  ├─ Demo login:         demo@anveshak.local / AnveshakDemo2024!\n"
printf "  ├─ Telegram adapter:   ${TELE_ENABLED}\n"
printf "  └─ X/Twitter adapter:  ${X_ENABLED}\n"
printf "\n"

# ---------------------------------------------------------------------------
# Step 4: Build and start (make setup)
# ---------------------------------------------------------------------------
step "Step 4/7" "Running make setup (build → infra → migrate → models → validate)..."

if [ "$DRY_RUN" = true ]; then
    skip "make setup — would execute 8-step setup:"
    printf "    ${DIM}Step 1/8: syscheck.py (RAM, disk, Docker, ports)${RST}\n"
    printf "    ${DIM}Step 2/8: docker compose build (6 service images + frontend)${RST}\n"
    printf "    ${DIM}Step 3/8: Start infra (postgres, redis, ollama)${RST}\n"
    printf "    ${DIM}Step 4/8: Wait for infra healthy (120s timeout)${RST}\n"
    printf "    ${DIM}Step 5/8: Alembic migrations + ollama pull qwen2:7b${RST}\n"
    printf "    ${DIM}Step 6/8: Start all 23 services${RST}\n"
    printf "    ${DIM}Step 7/8: Download vision models (YOLO + CLIP + deepfake ONNX)${RST}\n"
    printf "    ${DIM}Step 8/8: validate_pipeline.py (7-stage validation)${RST}\n"
else
    printf "  ${YEL}This takes ~15-20 min on first run (image builds + model downloads)${RST}\n\n"

    make setup 2>&1 | while IFS= read -r line; do
        printf "    %s\n" "$line"
    done

    SETUP_EXIT=${PIPESTATUS[0]}
    if [ "$SETUP_EXIT" -ne 0 ]; then
        warn "make setup exited with code $SETUP_EXIT (validation warnings are expected on first run)"
    else
        ok "make setup completed successfully"
    fi
fi

# ---------------------------------------------------------------------------
# Step 5: Start with GPU vision overlay
# ---------------------------------------------------------------------------
step "Step 5/7" "Restarting with GPU vision overlay..."

if [ "$DRY_RUN" = true ]; then
    skip "docker compose -f compose.yml -f compose.vision.yml up -d"
    printf "    ${DIM}Adds NVIDIA device reservations to vision + vision-worker containers${RST}\n"
    printf "    ${DIM}Would wait up to 180s for all services to be healthy${RST}\n"
    skip "Ollama GPU check: docker exec anveshak-ollama-1 ollama ps"
else
    docker compose --env-file .env -p anveshak -f infra/compose.yml -f infra/compose.vision.yml up -d --remove-orphans 2>&1 | tail -5

    printf "  Waiting for services to be healthy"
    TIMEOUT=180
    ELAPSED=0
    while [ $ELAPSED -lt $TIMEOUT ]; do
        UNHEALTHY=$(docker compose --env-file .env -p anveshak -f infra/compose.yml ps 2>/dev/null | grep -cE '(Restarting|unhealthy|starting)' || echo 0)
        if [ "$UNHEALTHY" -eq 0 ]; then
            break
        fi
        sleep 5
        ELAPSED=$((ELAPSED + 5))
        printf "."
    done
    printf "\n"

    if [ "$UNHEALTHY" -eq 0 ] 2>/dev/null; then
        ok "All services healthy with GPU overlay"
    else
        warn "Some services still starting — check with: make ps"
    fi

    OLLAMA_GPU=$(docker exec anveshak-ollama-1 ollama ps 2>/dev/null | grep -c "GPU" || echo 0)
    if [ "$OLLAMA_GPU" -gt 0 ]; then
        ok "Ollama is using GPU"
    else
        warn "Ollama may not be using GPU — check with: docker exec anveshak-ollama-1 ollama ps"
    fi
fi

# ---------------------------------------------------------------------------
# Step 6: Set up production topics and sources
# ---------------------------------------------------------------------------
step "Step 6/7" "Setting up production validation topics (4 topics, 21 sources)..."

if [ "$DRY_RUN" = true ]; then
    skip "python3 scripts/setup_production_topics.py --api-url http://localhost:8000"
    printf "    ${DIM}Would create 4 topics:${RST}\n"
    printf "    ${DIM}  1. India-China LAC Military Posturing (15 keywords, en/hi/zh)${RST}\n"
    printf "    ${DIM}  2. Pakistan Cross-Border Terror & LoC Activity (18 keywords, en/hi/ur)${RST}\n"
    printf "    ${DIM}  3. Indian Ocean Maritime Security & Chinese Naval Presence (17 keywords, en/hi)${RST}\n"
    printf "    ${DIM}  4. Disinformation & Info Ops Targeting India (13 keywords, en/hi)${RST}\n"
    printf "    ${DIM}Would create 21 sources: 11 RSS + 6 web + 3 Telegram + 1 X/Twitter${RST}\n"
    printf "    ${DIM}Would link sources to topics and verify ISC potential per topic${RST}\n"
    # Also run the existing --dry-run to show source details
    printf "\n"
    python3 scripts/setup_production_topics.py --dry-run 2>&1 | while IFS= read -r line; do
        printf "    %s\n" "$line"
    done
else
    sleep 5
    python3 scripts/setup_production_topics.py --api-url http://localhost:8000 2>&1 | while IFS= read -r line; do
        printf "    %s\n" "$line"
    done

    TOPICS_EXIT=${PIPESTATUS[0]}
    if [ "$TOPICS_EXIT" -ne 0 ]; then
        warn "Some sources failed to create — check output above"
    else
        ok "Production topics and sources configured"
    fi
fi

# ---------------------------------------------------------------------------
# Step 7: Final status + access URLs
# ---------------------------------------------------------------------------
step "Step 7/7" "Final verification..."

if [ "$DRY_RUN" = true ]; then
    skip "make ps (container status table)"
    skip "nvidia-smi (GPU utilization)"
else
    printf "\n"
    make ps 2>&1 | while IFS= read -r line; do
        printf "    %s\n" "$line"
    done

    printf "\n"
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu \
        --format=csv,noheader 2>/dev/null | while IFS= read -r line; do
        printf "  GPU: %s\n" "$line"
    done
fi

# ---------------------------------------------------------------------------
# Print access URLs
# ---------------------------------------------------------------------------
printf "\n"
header "SETUP COMPLETE — Access URLs"

if [ -n "$RUNPOD_POD_ID" ]; then
    printf "  ${BOLD}Analyst Workbench:${RST}  ${GRN}${PROXY_BASE}-3000.proxy.runpod.net${RST}\n"
    printf "  ${BOLD}API:${RST}                ${GRN}${PROXY_BASE}-8000.proxy.runpod.net${RST}\n"
    printf "  ${BOLD}Grafana:${RST}            ${GRN}${PROXY_BASE}-3001.proxy.runpod.net${RST}\n"
    printf "  ${BOLD}Prometheus:${RST}         ${GRN}${PROXY_BASE}-9090.proxy.runpod.net${RST}\n"
else
    printf "  ${BOLD}Analyst Workbench:${RST}  ${GRN}http://localhost:3000${RST}\n"
    printf "  ${BOLD}API:${RST}                ${GRN}http://localhost:8000${RST}\n"
    printf "  ${BOLD}Grafana:${RST}            ${GRN}http://localhost:3001${RST}\n"
    printf "  ${BOLD}Prometheus:${RST}         ${GRN}http://localhost:9090${RST}\n"
fi

printf "\n"
printf "  ${BOLD}Login:${RST}  demo@anveshak.local / AnveshakDemo2024!\n"
printf "  ${BOLD}Grafana:${RST} admin / ${GRAFANA_PASS}\n"
printf "\n"

# ---------------------------------------------------------------------------
# Print daily operations cheat sheet
# ---------------------------------------------------------------------------
header "Daily Operations Cheat Sheet"

cat << 'CHEATSHEET'
  # Check status
  make ps                                    # Container status
  make health                                # Quick health check
  python3 scripts/pipeline_health.py         # Full pipeline diagnostics

  # Monitor logs
  make logs-scraper                          # Scraper activity
  make logs-analyst                          # Analyst/clustering
  make logs-reporter                         # Report generation

  # GPU monitoring
  nvidia-smi                                 # GPU utilization
  watch -n 5 nvidia-smi                      # Live GPU monitor

  # Pipeline health (daily morning check)
  python3 scripts/pipeline_health.py                # Last 24h
  python3 scripts/pipeline_health.py --hours 48     # Last 48h
  python3 scripts/pipeline_health.py --summary      # Full period

  # If something breaks
  make restart                               # Restart all containers
  make logs 2>&1 | grep -i error             # Find errors across all services

  # Disk monitoring (200GB should last 10 days easily)
  df -h /
  docker system df

  # Backup database before any changes
  docker exec anveshak-postgres-1 pg_dump -U anveshak anveshak | gzip > backup_$(date +%Y%m%d).sql.gz
CHEATSHEET

printf "\n"
ok "Anveshak is running. Scraper will begin collecting content within 5 minutes."
ok "First signals should appear within 1-2 hours (depends on content volume)."
ok "First scheduled report at 08:30 AM IST tomorrow (cron: 0 3 * * * UTC)."
printf "\n"
