---
name: Compose build is a no-op for services that share an image
description: Only one service per image declares build; docker compose build <other-service> silently does nothing and a restart puts the old code back
type: pitfall
confidence: high
---

## Problem

Services that share an image declare `build:` on exactly one of them. In
`infra/compose.yml` the context owners are the schedulers:

| Image | Declares build | Shares the image, no build |
|---|---|---|
| anveshak-analyst | analyse-scheduler | analyse-worker, analyse-init |
| anveshak-scraper | scrape-web-scheduler | scrape-web-worker |
| anveshak-vision | analyse-vision-init | analyse-vision-worker |
| anveshak-reporter | report-worker | - |

`docker compose build analyse-worker` exits 0, prints nothing useful, and builds
nothing. A following `up -d` then recreates the container on the three-week-old
image, so the deployment runs the OLD code while every container reports
healthy and the logs show no error.

This is worse than a crash. A rollout that needs new code appears to have
succeeded, and the behaviour under test is the behaviour that was being fixed.

## Solution

Build via the context owner, not the service being changed:

```bash
# wrong - silently builds nothing
docker compose build analyse-worker scrape-web-worker

# right
docker compose build analyse-scheduler scrape-web-scheduler
docker compose up -d --no-deps analyse-worker analyse-scheduler \
    scrape-web-worker scrape-web-scheduler
```

`make build` builds everything and sidesteps the trap at the cost of time.

## Always verify in the container, never from the host

Image age tells you whether a build happened:

```bash
docker images --format '{{.Repository}}:{{.Tag}}\t{{.CreatedSince}}' | grep anveshak-
```

And exercise the changed code where it actually runs:

```bash
docker exec anveshak-analyse-worker-1 python -c \
    "from anveshak.analyst.settings import settings; print(settings.content_min_words)"
```

A host-side `uv run` proves nothing about the container: the working tree is not
what the image carries. This is the same class as
`migration-not-visible-in-container.md` - host files are COPYed at build time,
not mounted.

## See also

- `migration-not-visible-in-container.md` - the same gap, for Alembic files
- `compose-environment-consistency.md` - env vars reaching the right service
