# Anveshak — Deployment Runbook

Operator guide for installing and running Anveshak on a single machine.
Intended audience: IAF wing intelligence personnel and system administrators.

---

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 8-core x86_64 | 16-core |
| RAM | 16 GB | 32 GB |
| Storage | 100 GB SSD | 500 GB SSD |
| GPU | None (CPU inference) | NVIDIA RTX 3080+ (see hardware.md) |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| Network | Internal LAN only | Air-gapped optional |

> Anveshak is fully sovereign — it never calls cloud APIs with real intelligence data.
> All LLM inference runs on the local Ollama instance.

---

## Part 1 — Local Deployment (Docker Compose)

Use this for development, evaluation, and demo presentations.

### Step 1 — Prerequisites

```bash
# Install Docker Engine
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in

# Install Docker Compose plugin
sudo apt-get install -y docker-compose-plugin

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify
docker compose version
uv --version
```

### Step 2 — Clone and Configure

```bash
git clone <your-internal-git-url>/anveshak.git
cd anveshak

# Create environment file
cp .env.example .env

# Edit mandatory secrets (the three lines below MUST be changed)
nano .env
```

Set these three values in `.env`:

```bash
POSTGRES_PASSWORD=<strong-random-password>
API_SECRET_KEY=<output of: openssl rand -hex 32>
GRAFANA_ADMIN_PASSWORD=<strong-random-password>
```

### Step 3 — Start the Stack

```bash
make build    # build all Docker images (run once, takes ~5-10 minutes)
make up       # start all services
make ps       # verify all services are healthy
```

Expected output of `make ps` — all services should show `(healthy)`:

```
NAME                    STATUS
anveshak-postgres       running (healthy)
anveshak-redis          running (healthy)
anveshak-ollama         running (healthy)
anveshak-api            running (healthy)
anveshak-scraper        running (healthy)
anveshak-social         running (healthy)
anveshak-analyst        running (healthy)
anveshak-reporter       running (healthy)
anveshak-prometheus     running (healthy)
anveshak-grafana        running (healthy)
```

### Step 4 — Initialise (First Run Only)

```bash
make init       # pulls Ollama models + runs database migrations
                # takes 10-20 minutes on first run (model downloads)
```

### Step 5 — Load Demo Scenario

```bash
make seed-demo  # loads Operation Kargil Watch demo data
```

### Step 6 — Verify Demo Readiness

```bash
make demo-check
```

All 8 steps must show `[PASS]`. If any step fails, see the **Troubleshooting** section below.

### Step 7 — Access the Platform

| Interface | URL | Credentials |
|-----------|-----|-------------|
| Analyst Workbench | http://localhost:3000 | demo@anveshak.local / AnveshakDemo2024! |
| API (direct) | http://localhost:8000 | JWT via /api/v1/auth/login |
| Prometheus | http://localhost:9090 | No auth |
| Grafana | http://localhost:3001 | admin / (GRAFANA_ADMIN_PASSWORD from .env) |

---

## Part 2 — Production Deployment (k3s)

*This section will be updated once k3s manifests are finalised in Track 3.*

k3s is a lightweight Kubernetes distribution suitable for single-node production deployments.
It provides automatic restart, resource limits, and health management without the full
complexity of a multi-node Kubernetes cluster.

---

## Common Operations

### Stopping the Platform

```bash
make down          # stop all containers (data is preserved in volumes)
make clean-volumes # DESTRUCTIVE — deletes all data including the database
```

### Viewing Logs

```bash
make logs              # tail all services
make logs-api          # tail API service only
make logs-analyst      # tail analyst/NLP worker
make logs-reporter     # tail report generation worker
```

### Running Tests

```bash
make test          # unit + integration tests
make demo-check    # 8-step demo validation
```

### Rotating the Demo Password

If you need to change the demo analyst password:

```bash
uv run python scripts/gen_demo_password.py --password "YourNewPassword"
# Copy the hash output
nano scripts/seed_demo.sql   # replace hashed_password value
make seed-demo               # reload demo data
```

### Adding a New Analyst User

Currently done via direct database insert (user management UI is on the roadmap):

```bash
uv run python scripts/gen_demo_password.py --password "AnalystPassword123"

docker exec -i anveshak-postgres psql -U anveshak -d anveshak <<EOF
INSERT INTO users (id, email, hashed_password, full_name, role, is_active, created_at, updated_at, labels)
VALUES (
    gen_random_uuid(),
    'analyst@yourdomain.local',
    '<hash from gen_demo_password.py>',
    'Analyst Name',
    'analyst',
    true,
    NOW(), NOW(),
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb
);
EOF
```

---

## Enabling Social Adapters

All social adapters are disabled by default. Enable them in `.env`:

### Telegram

```bash
# 1. Get credentials from my.telegram.org → API development tools
# 2. Set in .env:
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# 3. Generate session string (run once)
uv run python scripts/bootstrap_telegram_session.py
# Copy TELEGRAM_SESSION_STRING= output into .env

# 4. Enable
TELEGRAM_ADAPTER_ENABLED=true

# 5. Restart
make restart
```

### Reddit

```bash
# 1. Create app at reddit.com/prefs/apps (type: script)
# 2. Set in .env:
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_ADAPTER_ENABLED=true
make restart
```

### X / Twitter (Pay-Per-Use)

```bash
# WARNING: X API charges $0.005 per read. Monitor your spend.
# Apply for access at developer.x.com (see docs/x_api_application.md)
# Set in .env:
X_BEARER_TOKEN=your_bearer_token
X_ADAPTER_ENABLED=true
X_MONTHLY_READ_CAP=40000   # $200/month cap — do not raise without reviewing billing
make restart
```

---

## Troubleshooting

### `[FAIL] Step 1 — API service: HTTP 0`

API container is not running or not healthy.

```bash
make logs-api      # check for startup errors
make ps            # check container status
docker inspect anveshak-api | grep -A5 Health
```

Common causes:
- `POSTGRES_PASSWORD` in `.env` doesn't match what PostgreSQL was initialised with → `make clean-volumes && make up && make init`
- Port 8000 already in use → `lsof -i :8000` and kill the conflicting process

### `[FAIL] Step 3 — Demo login: HTTP 401`

Demo user doesn't exist or password hash is wrong.

```bash
make seed-demo     # reload demo data
# If still failing:
uv run python scripts/gen_demo_password.py  # verify hash looks valid
```

### `[FAIL] Step 2 — Ollama model: mistral:7b not found`

Model hasn't been pulled yet.

```bash
make pull-models
# Or manually:
docker exec anveshak-ollama ollama pull mistral:7b
docker exec anveshak-ollama ollama pull llama3.2:3b
```

### `[FAIL] Step 8 — Grafana health`

Grafana container is not ready. Usually self-resolves in 30 seconds after `make up`.

```bash
make logs-grafana
# If database error — Grafana can't connect to its internal DB:
docker restart anveshak-grafana
```

### Service keeps restarting

```bash
make logs-<service>    # check for configuration errors
# Common: missing env var — check .env has all required values
```

### Out of disk space (Ollama models)

Ollama models are large (mistral:7b ≈ 4.1 GB, llama3.2:3b ≈ 2.0 GB).

```bash
docker exec anveshak-ollama ollama list   # see loaded models
df -h /var/lib/docker                     # check Docker volume space
```

---

## Security Notes

- Never expose Anveshak ports (8000, 3000, 9090, 3001) to the public internet
- Use a firewall (`ufw`) to restrict access to authorised analyst workstations only
- Rotate `API_SECRET_KEY` and `POSTGRES_PASSWORD` before production deployment
- The demo password `AnveshakDemo2024!` must be changed before operational use
- All intelligence data stays within the deployment boundary — Ollama is on localhost only
- Prometheus and Grafana should be behind authentication in production (Grafana auth is enabled by default via `GF_AUTH_ANONYMOUS_ENABLED=false`)
