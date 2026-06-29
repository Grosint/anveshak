---
paths:
  - "infra/**"
  - "Makefile"
  - "docker-compose*"
---
# Docker & Compose Rules

12 learned instincts. All Docker Compose and container work.

## Compose Invocation

- Always use `-p anveshak --env-file .env` with docker compose — avoids image/volume name mismatch
- Use `make ps` for container status, not raw `docker ps` or `docker compose ps`

## Environment Variables

- Every env var in `settings.py` MUST be in compose `environment:` block
  Missing vars silently default (`false`/`""`) — features disabled, no error
- `docker run --env-file` does NOT pick up compose `environment:` vars — pass explicitly with `-e` flags for one-off containers

## Volume Naming

- All services sharing data dir MUST mount same named volume
  `media_store:/app/media` and `vision_media:/app/media` = TWO SEPARATE host dirs — mismatched names create invisible data silos, no error/log
- After compose volume change, grep mount path across services:
  `grep -n '/app/media' infra/compose.yml` — verify volume name consistency
  See: `learned/docker-volume-name-consistency.md`

## Build Context

- Build context paths resolve relative to compose file location, not CWD
- SDK workspace must be in build context — set context depth to reach project root (e.g., `context: ../..` from `infra/`)

## Overlay Files

- Core user-facing features go in base `compose.yml` — never overlay files
- Overlay compose files (`compose.vision.yml`, `compose.bridge.yml`) ONLY for optional GPU/dev services not every deployment needs
- Feature requires env var only in overlay → silently disabled on non-overlay deployments

## Cleanup

- Graduated cleanup: `clean` → `clean-containers` → `clean-volumes` → `nuke`
- `make nuke` must filter images by project prefix — avoid deleting unrelated images
- Include build cache pruning for fresh-clone simulation

## Integration Testing

- Tests needing running services (PostgreSQL, Redis): use `docker compose exec` or `docker cp` + `docker exec` — never assume host-reachable unless port-forwarded

## Compose Override Port Merging (CRITICAL)

- NEVER put `ports:` in compose override files — Compose v2 MERGES lists, doesn't replace
  `ports: ["127.0.0.1:8000:8000"]` in override APPENDS to base `"8000:8000"` → "address already in use"
  `ports: []` also doesn't clear base ports — merges empty list, base remains
  Use cloud/host firewall for port restriction instead
  See: `learned/compose-port-override-merge-trap.md`

## Bind Mount Permissions for Init Containers

- Init containers (model downloaders) crash with PermissionError on bind mounts owned by root
  Fix: `chmod -R 777 /data/models /data/vision-models` before first run
  Observability: Prometheus=65534, Loki=10001, Grafana=472 — set chown before first run
  See: `learned/bind-mount-init-container-permissions.md`

## Ubuntu 24.04 Differences

- Docker package: `docker-ce` (official repo), not `docker.io`
- NVIDIA container toolkit: needs separate NVIDIA apt repo
- NVIDIA driver: use `-server` variant on headless VMs
- SSH service: `systemctl restart ssh` not `sshd`
  See: `learned/ubuntu-2404-docker-nvidia-setup.md`

## bcrypt Hash Shell Escaping

- bcrypt `$` characters get shell-expanded when inserting via psql/bash
  Generate hash INSIDE API container, then update via psql with `\$` escaping
  Passwords with `!` need single quotes (bash history expansion)
  See: `learned/bcrypt-hash-shell-escaping.md`

## GCP GPU Quota

- Two layers: per-region (NVIDIA_T4_GPUS) AND global (GPUS_ALL_REGIONS) — both must be >= 1
  Global defaults to 0 on new projects — request increase first (24-48h)
  Zone exhaustion: try all zones, then L4, then different region
  Admin commands (bucket create, snapshot policies): run from local, not VM
  See: `learned/gcp-gpu-quota-two-layers.md`