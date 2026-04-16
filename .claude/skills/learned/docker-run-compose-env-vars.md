---
name: docker-run-compose-env-vars
description: docker run with --env-file misses compose x-common-env vars (POSTGRES_URL, REDIS_URL etc) — must pass them explicitly with -e
type: feedback
---

# docker run Misses compose x-common-env Variables

## Rule

When restarting a container with `docker run` instead of `docker compose up`, always pass the compose-defined environment variables explicitly with `-e`, in addition to `--env-file`.

**Why:** `docker compose` evaluates the `environment:` block (including YAML anchors like `x-common-env`) and injects vars at run time. `docker run --env-file .env` only reads the flat `.env` file. Variables set via compose `environment:` (e.g. `POSTGRES_URL`, `REDIS_URL`, `OLLAMA_BASE_URL`) are **not** in `.env` — they're in `compose.yml`. Running `docker run --env-file .env` alone means those vars are absent, and the service crashes on DB connection.

## How to apply

When you must restart a single container outside compose (e.g. network overlap prevents `docker compose up`):

```bash
# Step 1: stop + remove old container
docker stop anveshak-api-1 && docker rm anveshak-api-1

# Step 2: run with --env-file PLUS explicit compose vars AND network alias
docker run -d --name anveshak-api-1 \
  --network anveshak_anveshak-net \
  --network-alias api \                      # nginx upstream resolves 'api'
  --env-file .env \                          # flat secrets from .env
  -e POSTGRES_URL="postgresql://anveshak:${POSTGRES_PASSWORD}@postgres:5432/anveshak" \
  -e REDIS_URL="redis://redis:6379/0" \
  -e OLLAMA_BASE_URL="http://ollama:11434" \
  -p 8000:8000 \
  infra-api
```

## Checklist for manual `docker run` restarts

- [ ] `--network <compose_project>_<network_name>` — same network as other services
- [ ] `--network-alias <service_name>` — so nginx upstream DNS resolves
- [ ] `--env-file .env` — secrets
- [ ] `-e POSTGRES_URL=...` — compose-defined vars not in .env
- [ ] `-e REDIS_URL=...`
- [ ] `-e OLLAMA_BASE_URL=...`
- [ ] Port `-p <host>:<container>` — check nginx.conf for actual container port (may not be 80)

## Port mapping pitfall

nginx.conf inside the container may listen on a non-standard port (e.g. 3000, not 80). Always check:
```bash
docker exec <container> grep "listen" /etc/nginx/conf.d/default.conf
```
Map host port to the port nginx actually listens on:
```bash
-p 3000:3000   # NOT -p 3000:80 if nginx listens on 3000
```
