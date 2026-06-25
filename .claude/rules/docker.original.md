---
paths:
  - "infra/**"
  - "Makefile"
  - "docker-compose*"
---
# Docker & Compose Rules

Consolidated from 7 learned instincts. These apply to all Docker Compose and container work.

## Compose Invocation

- Always use `-p anveshak --env-file .env` with docker compose to avoid image/volume
  name mismatch across invocations
- Use `make ps` to check container status, not raw `docker ps` or `docker compose ps`

## Environment Variables

- Every env var in `settings.py` MUST be forwarded in the compose `environment:` block
  Otherwise the var silently defaults (usually to `false`/`""`) with no error —
  features appear disabled for no visible reason
- `docker run --env-file` does NOT pick up vars set in compose's `environment:` block —
  pass them explicitly with `-e` flags when running one-off containers

## Volume Naming

- All services sharing a data directory MUST mount the same named volume
  `media_store:/app/media` and `vision_media:/app/media` are TWO SEPARATE directories
  on the host — mismatched names create invisible data silos with no error or log
- After any compose volume change, grep for the mount path across all services:
  `grep -n '/app/media' infra/compose.yml` — verify volume name consistency
  See: `learned/docker-volume-name-consistency.md`

## Build Context

- Build context paths resolve relative to the compose file location, not CWD
- SDK workspace must be included in the build context — set context depth
  to reach the project root (e.g., `context: ../..` from `infra/`)

## Overlay Files

- Core user-facing features go in base `compose.yml` — never in overlay files
- Overlay compose files (`compose.vision.yml`, `compose.bridge.yml`) are ONLY for
  optional GPU/dev services that not every deployment needs
- If a feature requires an env var, and that env var is only in an overlay,
  the feature is silently disabled on every non-overlay deployment

## Cleanup

- Implement graduated cleanup: `clean` → `clean-containers` → `clean-volumes` → `nuke`
- `make nuke` must filter images by project prefix to avoid deleting unrelated images
- Include build cache pruning for true fresh-clone simulation

## Integration Testing

- For tests that need running services (PostgreSQL, Redis), use `docker compose exec`
  or `docker cp` + `docker exec` — never assume services are reachable from the host
  unless port-forwarded
