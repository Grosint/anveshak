#!/bin/bash
# Anveshak — Manual Deploy Script
# Run on the production VM to update the application.
# Usage: bash scripts/deploy.sh
set -euo pipefail

cd /data/anveshak

echo "=== Anveshak Deploy ==="

# Pull latest code
echo "[1/5] Pulling latest code..."
git pull origin main

# Rebuild images
echo "[2/5] Building images..."
docker compose -p anveshak --env-file .env \
  -f infra/compose.yml -f infra/compose.prod.yml build

# Restart services
echo "[3/5] Restarting services..."
docker compose -p anveshak --env-file .env \
  -f infra/compose.yml -f infra/compose.prod.yml up -d

# Run migrations
echo "[4/5] Running migrations..."
make migrate

# Validate
echo "[5/5] Validating..."
make health

echo ""
echo "=== Deploy Complete ==="
echo "Check full validation: make validate"
echo "Check GPU: nvidia-smi"
echo "Rollback: git checkout HEAD~1 && bash scripts/deploy.sh"
