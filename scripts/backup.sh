#!/usr/bin/env bash
# =============================================================================
# Anveshak — Backup Script
#
# Creates a timestamped backup of:
#   1. PostgreSQL database (pg_dump)
#   2. Redis RDB snapshot (BGSAVE + copy)
#   3. Media assets directory (tar.gz)
#
# Usage:
#   ./scripts/backup.sh                    # backup to ./backups/
#   ./scripts/backup.sh /path/to/backups   # backup to custom directory
#
# Restore:
#   ./scripts/restore.sh /path/to/backup-dir
# =============================================================================

set -euo pipefail

BACKUP_ROOT="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_ROOT}/anveshak_${TIMESTAMP}"
COMPOSE="docker compose --env-file .env -p anveshak -f infra/compose.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { printf "${CYAN}[backup]${NC} %s\n" "$1"; }
ok()  { printf "${GREEN}  ✓${NC} %s\n" "$1"; }
err() { printf "${RED}  ✗${NC} %s\n" "$1"; }

# ---------------------------------------------------------------------------
# Pre-checks
# ---------------------------------------------------------------------------

if [ ! -f .env ]; then
    err ".env file not found — run from project root"
    exit 1
fi

# Source .env for POSTGRES_PASSWORD
set -a
source .env
set +a

mkdir -p "${BACKUP_DIR}"
log "Backup directory: ${BACKUP_DIR}"

# ---------------------------------------------------------------------------
# 1. PostgreSQL dump
# ---------------------------------------------------------------------------

log "Dumping PostgreSQL..."
if ${COMPOSE} exec -T postgres pg_dump \
    -U anveshak \
    -d anveshak \
    --format=custom \
    --compress=6 \
    > "${BACKUP_DIR}/postgres.dump" 2>/dev/null; then
    SIZE=$(du -sh "${BACKUP_DIR}/postgres.dump" | cut -f1)
    ok "PostgreSQL dump: ${SIZE}"
else
    err "PostgreSQL dump failed — is the container running?"
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. Redis RDB snapshot
# ---------------------------------------------------------------------------

log "Triggering Redis BGSAVE..."
${COMPOSE} exec -T redis redis-cli BGSAVE > /dev/null 2>&1
sleep 2  # Wait for BGSAVE to complete
if ${COMPOSE} exec -T redis cat /data/dump.rdb > "${BACKUP_DIR}/redis.rdb" 2>/dev/null; then
    SIZE=$(du -sh "${BACKUP_DIR}/redis.rdb" | cut -f1)
    ok "Redis RDB: ${SIZE}"
else
    printf "${YELLOW}  ⚠${NC} Redis backup skipped (no dump.rdb found)\n"
fi

# ---------------------------------------------------------------------------
# 3. Media assets
# ---------------------------------------------------------------------------

log "Archiving media assets..."
if docker volume inspect anveshak_media_store > /dev/null 2>&1; then
    docker run --rm \
        -v anveshak_media_store:/data:ro \
        -v "$(realpath "${BACKUP_DIR}"):/backup" \
        alpine:3.19 \
        tar czf /backup/media.tar.gz -C /data . 2>/dev/null
    if [ -f "${BACKUP_DIR}/media.tar.gz" ]; then
        SIZE=$(du -sh "${BACKUP_DIR}/media.tar.gz" | cut -f1)
        ok "Media archive: ${SIZE}"
    else
        printf "${YELLOW}  ⚠${NC} Media archive empty\n"
    fi
else
    printf "${YELLOW}  ⚠${NC} Media volume not found — skipping\n"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

TOTAL=$(du -sh "${BACKUP_DIR}" | cut -f1)
printf "\n${GREEN}Backup complete:${NC} ${BACKUP_DIR} (${TOTAL})\n"
printf "Files:\n"
ls -lh "${BACKUP_DIR}/" | grep -v "^total"
printf "\nRestore with: ${CYAN}./scripts/restore.sh ${BACKUP_DIR}${NC}\n"
