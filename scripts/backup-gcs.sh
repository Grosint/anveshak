#!/bin/bash
# Anveshak — GCS Backup Script
# Backs up PostgreSQL, Redis, and syncs media/reports to GCS.
# Usage: bash scripts/backup-gcs.sh
# Cron:  30 20 * * * /data/anveshak/scripts/backup-gcs.sh >> /var/log/anveshak-backup.log 2>&1
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/data/backups/anveshak_${TIMESTAMP}"
BUCKET="${GCS_BACKUP_BUCKET:-gs://anveshak-backups-prod}"
LOG="/var/log/anveshak-backup.log"

log() { echo "[$(date -Iseconds)] $1" | tee -a "$LOG"; }

mkdir -p "$BACKUP_DIR"

# PostgreSQL (custom format for selective restore)
log "Starting PostgreSQL backup..."
docker exec anveshak-postgres-1 pg_dump -U anveshak -Fc anveshak > "$BACKUP_DIR/postgres.dump"
gzip "$BACKUP_DIR/postgres.dump"
log "PostgreSQL backup: $(du -sh "$BACKUP_DIR/postgres.dump.gz" | cut -f1)"

# Redis (trigger BGSAVE, wait, copy)
log "Starting Redis backup..."
docker exec anveshak-redis-1 redis-cli BGSAVE
sleep 5
docker cp anveshak-redis-1:/data/dump.rdb "$BACKUP_DIR/redis.rdb"
log "Redis backup: $(du -sh "$BACKUP_DIR/redis.rdb" | cut -f1)"

# Upload DB backups to GCS
log "Uploading DB backups to ${BUCKET}..."
gsutil -m cp -r "$BACKUP_DIR" "${BUCKET}/db-backups/"

# Media sync (incremental, delete removed files)
log "Syncing media to GCS..."
gsutil -m rsync -r /data/media/ "${BUCKET}/media/" 2>&1 | tail -3

# Reports sync (incremental, keep all)
log "Syncing reports to GCS..."
gsutil -m rsync -r /data/reports/ "${BUCKET}/reports/" 2>&1 | tail -3

# Cleanup local backups older than 7 days
find /data/backups -maxdepth 1 -type d -name "anveshak_*" -mtime +7 -exec rm -rf {} + 2>/dev/null || true

log "Backup complete: ${BUCKET}/db-backups/anveshak_${TIMESTAMP}"
