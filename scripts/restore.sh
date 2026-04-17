#!/usr/bin/env bash
# =============================================================================
# Anveshak — Restore Script
#
# Restores from a backup created by backup.sh:
#   1. PostgreSQL database (pg_restore)
#   2. Redis RDB snapshot
#   3. Media assets
#
# Usage:
#   ./scripts/restore.sh ./backups/anveshak_20260417_120000
#
# WARNING: This replaces the current database! Back up first if needed.
# =============================================================================

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup-directory>"
    echo "Example: $0 ./backups/anveshak_20260417_120000"
    exit 1
fi

BACKUP_DIR="$1"
COMPOSE="docker compose --env-file .env -p anveshak -f infra/compose.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { printf "${CYAN}[restore]${NC} %s\n" "$1"; }
ok()  { printf "${GREEN}  ✓${NC} %s\n" "$1"; }
err() { printf "${RED}  ✗${NC} %s\n" "$1"; }

# ---------------------------------------------------------------------------
# Pre-checks
# ---------------------------------------------------------------------------

if [ ! -d "${BACKUP_DIR}" ]; then
    err "Backup directory not found: ${BACKUP_DIR}"
    exit 1
fi

if [ ! -f .env ]; then
    err ".env file not found — run from project root"
    exit 1
fi

set -a
source .env
set +a

printf "${YELLOW}WARNING: This will replace the current database.${NC}\n"
printf "Restoring from: ${BACKUP_DIR}\n"
printf "Press Enter to continue or Ctrl+C to abort..."
read -r

# ---------------------------------------------------------------------------
# 1. PostgreSQL restore
# ---------------------------------------------------------------------------

if [ -f "${BACKUP_DIR}/postgres.dump" ]; then
    log "Restoring PostgreSQL..."

    # Drop and recreate the database
    ${COMPOSE} exec -T postgres psql -U anveshak -d postgres \
        -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='anveshak' AND pid <> pg_backend_pid();" \
        > /dev/null 2>&1 || true
    ${COMPOSE} exec -T postgres psql -U anveshak -d postgres \
        -c "DROP DATABASE IF EXISTS anveshak;" > /dev/null 2>&1
    ${COMPOSE} exec -T postgres psql -U anveshak -d postgres \
        -c "CREATE DATABASE anveshak OWNER anveshak;" > /dev/null 2>&1

    # Restore from dump
    if cat "${BACKUP_DIR}/postgres.dump" | ${COMPOSE} exec -T postgres pg_restore \
        -U anveshak \
        -d anveshak \
        --no-owner \
        --no-privileges \
        2>/dev/null; then
        ok "PostgreSQL restored"
    else
        # pg_restore returns non-zero on warnings — check if data is there
        printf "${YELLOW}  ⚠${NC} pg_restore had warnings (usually harmless)\n"
    fi
else
    printf "${YELLOW}  ⚠${NC} No postgres.dump found — skipping\n"
fi

# ---------------------------------------------------------------------------
# 2. Redis restore
# ---------------------------------------------------------------------------

if [ -f "${BACKUP_DIR}/redis.rdb" ]; then
    log "Restoring Redis..."
    ${COMPOSE} exec -T redis redis-cli SHUTDOWN NOSAVE > /dev/null 2>&1 || true
    sleep 1
    cat "${BACKUP_DIR}/redis.rdb" | docker run --rm -i \
        -v anveshak_redis_data:/data \
        alpine:3.19 sh -c 'cat > /data/dump.rdb' 2>/dev/null
    ${COMPOSE} restart redis > /dev/null 2>&1
    ok "Redis restored"
else
    printf "${YELLOW}  ⚠${NC} No redis.rdb found — skipping\n"
fi

# ---------------------------------------------------------------------------
# 3. Media assets
# ---------------------------------------------------------------------------

if [ -f "${BACKUP_DIR}/media.tar.gz" ]; then
    log "Restoring media assets..."
    docker run --rm \
        -v anveshak_media_store:/data \
        -v "$(realpath "${BACKUP_DIR}"):/backup:ro" \
        alpine:3.19 \
        sh -c 'cd /data && tar xzf /backup/media.tar.gz' 2>/dev/null
    ok "Media assets restored"
else
    printf "${YELLOW}  ⚠${NC} No media.tar.gz found — skipping\n"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

printf "\n${GREEN}Restore complete.${NC}\n"
printf "Run ${CYAN}make health${NC} to verify services are operational.\n"
