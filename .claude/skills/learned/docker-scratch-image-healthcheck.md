# Docker Scratch Image Healthcheck

## When to load: writing healthchecks for third-party Docker images

---

## Problem

Many lightweight exporter images (redis_exporter, node_exporter, etc.) use scratch or distroless base images. These have **no shell** (`/bin/sh` doesn't exist).

```yaml
# THIS FAILS on scratch images:
healthcheck:
  test: ["CMD-SHELL", "wget -qO- http://localhost:9121/metrics | head -1 || exit 1"]
# Error: /bin/sh: no such file or directory
# Container marked unhealthy forever despite running fine
```

## Solutions

**Option 1: Disable healthcheck** (best for stateless exporters)
```yaml
healthcheck:
  disable: true
```

**Option 2: Use CMD with binary path** (if the binary supports a check mode)
```yaml
healthcheck:
  test: ["CMD", "/redis_exporter", "--version"]
```

**Option 3: Use a health-check sidecar** (overkill for most cases)

## When to use which

- Stateless exporters (redis-exporter, postgres-exporter): **disable** — if they crash, `restart: unless-stopped` handles it
- Application services with health endpoints: **CMD-SHELL with curl/wget** — these images have shells
- Databases: **CMD with native tools** — `redis-cli ping`, `pg_isready`

## How to check before writing

```bash
# Check if image has a shell
docker run --rm --entrypoint sh image_name -c "echo ok"
# If "no such file or directory" → scratch/distroless → don't use CMD-SHELL
```
