---
paths:
  - "infra/**"
  - "Makefile"
  - "docker-compose*"
---
# Docker & Compose Rules

7 learned instincts. All Docker Compose and container work.

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