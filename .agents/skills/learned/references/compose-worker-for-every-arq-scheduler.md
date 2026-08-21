# Every ARQ Scheduler Needs a Matching Worker in Compose

## Problem

Social scheduler (`social` container) ran `main.py` which enqueued `poll_social_topic`
ARQ jobs every 15 minutes. But no `social-worker` container existed in compose.yml to
process them. Jobs sat in Redis until they expired. All social adapters (Telegram, X,
Reddit, Bluesky, Instagram) were dead since project start.

Seed data masked the gap — frontend showed fake Telegram content, so nobody noticed
real scraping wasn't happening.

## Rule

For every service that calls `enqueue_job(...)`, verify there is a container in compose
with `command: ["python", "-m", "arq", "...WorkerSettings"]` that processes those jobs.

Audit checklist:
1. Grep `enqueue_job` in all services
2. For each target function, find which WorkerSettings registers it
3. Verify that WorkerSettings has a container in compose.yml
4. Verify container has matching env vars (credentials, Redis, Postgres)

## Pattern

Scheduler + worker always come in pairs:
```yaml
# Scheduler: enqueues jobs
social:
  command: ["python", "-m", "anveshak.social.main"]

# Worker: processes jobs (MUST EXIST)
social-worker:
  image: anveshak-social:latest    # same image
  command: ["python", "-m", "arq", "anveshak.social.jobs.WorkerSettings"]
  environment: *same-as-scheduler  # needs same credentials
```

## Detection

- `pipeline_health.py` container check: flags MISSING workers
- ARQ queue depth > 0 with no worker → jobs accumulating
- Source staleness: "NEVER scraped" for social sources

## See also

- `scheduler-worker-split.md` — why scheduler + worker are separate
