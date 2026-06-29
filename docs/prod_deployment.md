# Anveshak — Production Deployment Runbook

Cloud-agnostic. Tested on GCP (2026-06-29). Works on AWS, Azure, bare metal.

## Prerequisites

| Spec | Without GPU | With GPU |
|------|------------|----------|
| vCPUs | 8 | 16 |
| RAM | 32 GB | 60 GB |
| GPU | None | T4 16GB / L4 24GB |
| Boot disk | 50 GB SSD | 50 GB SSD |
| Data disk | 250 GB SSD | 250 GB SSD |
| OS | Ubuntu 22.04+ | Ubuntu 22.04+ |
| Ports open | 22, 80, 443 | 22, 80, 443 |

## Quick Deploy (5 commands after VM bootstrap)

```bash
# 1. Bootstrap VM (Docker, NVIDIA, sysctl, security)
sudo bash scripts/bootstrap-vm.sh

# 2. Reboot (if NVIDIA driver was installed), SSH back, clone repo
sudo reboot
# ... SSH back ...
cd /data && git clone <repo-url> anveshak && cd anveshak

# 3. Configure
cp .env.example .env
nano .env  # Set secrets, domain, GPU settings (see .env section below)

# 4. Build + start
docker compose -p anveshak --env-file .env -f infra/compose.yml -f infra/compose.prod.yml build
docker compose -p anveshak --env-file .env -f infra/compose.yml -f infra/compose.prod.yml up -d

# 5. Migrate + pull LLM
docker compose -p anveshak --env-file .env -f infra/compose.yml -f infra/compose.prod.yml exec api python -m alembic upgrade head
docker compose -p anveshak --env-file .env -f infra/compose.yml -f infra/compose.prod.yml exec ollama ollama pull qwen2.5:14b
```

## TLS Setup

```bash
# DNS: create A record → VM public IP
# Then:
sudo mkdir -p /var/www/certbot
sudo certbot --nginx -d YOUR_DOMAIN --non-interactive --agree-tos -m admin@YOUR_DOMAIN
```

Install nginx config from `infra/nginx/anveshak.conf` — update `server_name` to match domain.
Remove default nginx site after certbot runs.

## Create Admin User

Generate bcrypt hash INSIDE container (shell escaping breaks hashes):
```bash
# Generate hash
docker exec anveshak-api-1 python -c 'import bcrypt;print(bcrypt.hashpw(b"YOUR_PASSWORD",bcrypt.gensalt(12)).decode())'

# Create org + user
docker exec anveshak-postgres-1 psql -U anveshak -d anveshak -c \
  "INSERT INTO organizations (id, name, slug, labels) VALUES ('org-001', 'YourOrg', 'yourorg', '{}') ON CONFLICT DO NOTHING;
   INSERT INTO users (id, username, password_hash, role, org_id, labels) VALUES ('user-001', 'admin@yourorg', 'PASTE_HASH_HERE', 'super-admin', 'org-001', '{}') ON CONFLICT DO NOTHING;"
```

## Production .env — Key Changes from Dev

```bash
ENVIRONMENT=production
VITE_API_BASE_URL=https://YOUR_DOMAIN    # MUST set before building frontend
API_ALLOWED_ORIGINS=https://YOUR_DOMAIN
HSTS_ENABLED=true

# GPU settings (skip if CPU-only)
VISION_DEVICE=cuda
OLLAMA_KEEP_ALIVE=-1
OLLAMA_NUM_PARALLEL=4
OLLAMA_MODEL=qwen2.5:14b

# Upgraded models (fresh DB — no migration needed)
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
EMBEDDING_DIMENSIONS=1024
SPACY_EN_MODEL=en_core_web_trf
TRANSLATION_MODEL=facebook/nllb-200-1.3B
TRANSLATION_MAX_CHARS=3000
YOLO_MODEL_SIZE=medium
ANALYST_WORKER_REPLICAS=2
```

## Backup

```bash
# Setup daily cron
chmod +x scripts/backup-gcs.sh
echo '30 20 * * * root /data/anveshak/scripts/backup-gcs.sh >> /var/log/anveshak-backup.log 2>&1' | sudo tee /etc/cron.d/anveshak-backup

# For non-GCS clouds, edit scripts/backup-gcs.sh:
#   AWS: replace gsutil with aws s3 sync
#   Azure: replace gsutil with azcopy sync
#   Bare metal: replace gsutil with rsync -avz
```

## Deploy Updates

```bash
bash scripts/deploy.sh
# Or manually:
cd /data/anveshak && git pull origin main
docker compose -p anveshak --env-file .env -f infra/compose.yml -f infra/compose.prod.yml build
docker compose -p anveshak --env-file .env -f infra/compose.yml -f infra/compose.prod.yml up -d
make migrate
```

## Rollback

```bash
git checkout HEAD~1
docker compose -p anveshak --env-file .env -f infra/compose.yml -f infra/compose.prod.yml build
docker compose -p anveshak --env-file .env -f infra/compose.yml -f infra/compose.prod.yml up -d
```

## Known Gotchas

1. **compose.prod.yml must NOT have `ports:` overrides** — Docker Compose merges lists, doesn't replace. Use cloud/host firewall for port restriction.

2. **`chmod -R 777 /data/models /data/vision-models`** before first run — init containers run as non-root, bind mounts inherit host permissions.

3. **Observability UIDs:** Prometheus=65534, Loki=10001, Grafana=472. Set `chown` before first run (bootstrap-vm.sh handles this).

4. **Passwords with `!`** — bash history expansion. Always use single quotes: `'AnveshakProd2026!'` not `"AnveshakProd2026!"`.

5. **bcrypt hashes** — generate inside container, not on host. Shell `$` escaping corrupts hashes silently.

6. **GCP GPU quota** — need BOTH per-region (NVIDIA_T4_GPUS) AND global (GPUS_ALL_REGIONS). Global defaults to 0 on new projects.

7. **Ubuntu 24.04** — SSH service is `ssh` not `sshd`. Docker package is `docker-ce` not `docker.io`.

## Cloud-Specific Notes

### GCP
- GPU quota: request GPUS_ALL_REGIONS increase first (24-48h)
- Zone exhaustion: try all zones, or switch to L4 (more zones)
- Admin commands (bucket create, snapshot schedule): run from local, not VM
- Firewall: VPC firewall rules with target tags

### AWS
- GPU instance: g4dn.4xlarge (T4) or g5.4xlarge (A10G)
- Security Groups instead of VPC firewall
- EBS snapshots instead of resource policies
- S3 instead of GCS for backups

### Azure
- GPU: NC-series VMs
- NSG instead of firewall rules
- Managed disks with snapshots
- Blob Storage for backups

### Bare Metal
- Install NVIDIA drivers from .run file
- iptables/ufw for firewall
- rsync to NAS/remote for backups
- No disk snapshots — rely on backup script

## Monitoring

- Grafana: SSH tunnel `ssh -L 3001:localhost:3001 user@VM_IP` → http://localhost:3001
- GPU: `nvidia-smi` or cron logs via `journalctl -t anveshak-gpu`
- Disk: cron alerts at 80% → `journalctl -t anveshak-disk`
- Certbot: auto-renews, verify with `sudo certbot certificates`
