# Infra, Docker, and Compose

Applies to everything under `infra/`, the root `Makefile`, and any `docker-compose*` file.
Repo-wide rules are in [../AGENTS.md](../AGENTS.md).

12 learned instincts covering all Docker Compose and container work.

## Compose invocation

- Always use `-p anveshak --env-file .env` with docker compose, which avoids image and volume name mismatch
- Use `make ps` for container status, not raw `docker ps` or `docker compose ps`

## Environment variables

- Every env var in `settings.py` MUST be in the compose `environment:` block.
  Missing vars silently default to `false` or `""`, so features are disabled with no error.
- `docker run --env-file` does NOT pick up compose `environment:` vars.
  Pass them explicitly with `-e` flags for one-off containers.

## Volume naming

- All services sharing a data dir MUST mount the same named volume.
  `media_store:/app/media` and `vision_media:/app/media` are TWO SEPARATE host dirs.
  Mismatched names create invisible data silos with no error or log.
- After a compose volume change, grep the mount path across services:
  `grep -n '/app/media' infra/compose.yml` and verify volume name consistency.
  See: `.agents/skills/learned/references/docker-volume-name-consistency.md`

## Build context

- Build context paths resolve relative to the compose file location, not CWD
- The SDK workspace must be inside the build context, so set context depth to reach the project root, for example `context: ../..` from `infra/`

## Overlay files

- Core user-facing features go in base `compose.yml`, never in overlay files
- Overlay compose files (`compose.vision.yml`, `compose.bridge.yml`) are ONLY for optional GPU or dev services that not every deployment needs
- A feature whose env var exists only in an overlay is silently disabled on non-overlay deployments

## Cleanup

- Graduated cleanup: `clean`, then `clean-containers`, then `clean-volumes`, then `nuke`
- `make nuke` must filter images by project prefix so unrelated images survive
- Include build cache pruning for fresh-clone simulation

## Integration testing

- Tests needing running services (PostgreSQL, Redis) use `docker compose exec` or `docker cp` plus `docker exec`.
  Never assume host-reachable unless the port is forwarded.

## Compose override port merging (CRITICAL)

- NEVER put `ports:` in a compose override file, because Compose v2 MERGES lists rather than replacing them.
  `ports: ["127.0.0.1:8000:8000"]` in an override APPENDS to the base `"8000:8000"`, giving "address already in use".
  `ports: []` does not clear base ports either; it merges an empty list and the base remains.
  Use a cloud or host firewall for port restriction instead.
  See: `.agents/skills/learned/references/compose-port-override-merge-trap.md`

## Bind mount permissions for init containers

- Init containers such as model downloaders crash with PermissionError on bind mounts owned by root.
  Fix with `chmod -R 777 /data/models /data/vision-models` before the first run.
  Observability UIDs: Prometheus 65534, Loki 10001, Grafana 472. Set chown before first run.
  See: `.agents/skills/learned/references/bind-mount-init-container-permissions.md`

## Ubuntu 24.04 differences

- Docker package is `docker-ce` from the official repo, not `docker.io`
- NVIDIA container toolkit needs a separate NVIDIA apt repo
- NVIDIA driver: use the `-server` variant on headless VMs
- SSH service: `systemctl restart ssh`, not `sshd`
  See: `.agents/skills/learned/references/ubuntu-2404-docker-nvidia-setup.md`

## bcrypt hash shell escaping

- bcrypt `$` characters get shell-expanded when inserting via psql or bash.
  Generate the hash INSIDE the API container, then update via psql with `\$` escaping.
  Passwords containing `!` need single quotes, because of bash history expansion.
  See: `.agents/skills/learned/references/bcrypt-hash-shell-escaping.md`

## GCP GPU quota

- Two layers apply, per-region (NVIDIA_T4_GPUS) AND global (GPUS_ALL_REGIONS), and both must be at least 1.
  Global defaults to 0 on new projects, so request an increase first; it takes 24 to 48 hours.
  On zone exhaustion, try all zones, then L4, then a different region.
  Admin commands such as bucket create and snapshot policies run from local, not the VM.
  See: `.agents/skills/learned/references/gcp-gpu-quota-two-layers.md`
