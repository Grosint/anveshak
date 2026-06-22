# Cross-Service Metadata Enrichment via ARQ (Fail-Open)

## Pattern
When Service A (API) needs data from Service B (Social adapters) that has no HTTP endpoint:
1. API creates the primary row synchronously (stats, core data)
2. API enqueues an ARQ job on Service B's queue to fetch metadata
3. Service B's worker fetches metadata and UPDATEs the row directly
4. Frontend shows primary data immediately; metadata appears on refresh

## Why
Social service is ARQ-worker-only (no HTTP endpoints). Can't make synchronous
HTTP calls from API to social. Creating an internal HTTP endpoint just for
metadata is over-engineering for a single use case.

## How to Apply
- ARQ job takes the enrichment target ID (e.g., `assessment_id`) + lookup params (`platform`, `handle`)
- Worker looks up adapter from `_ADAPTERS` registry by platform
- Calls `adapter.fetch_profile_metadata(handle)` — new optional method on base class
- UPDATEs the target row's JSONB column directly via SQL
- Entire flow is fail-open: if social service is down or adapter doesn't support metadata,
  the assessment works fine without it (logged at INFO level)
- Queue name must match the worker's actual queue (social uses default `arq:queue`)

## Pitfall
Don't enqueue to the wrong queue name. Social worker uses default `arq:queue`,
not a custom name like `arq:social`. Always grep `WorkerSettings` for `queue_name`.

## Session Context
Phase 1 of Source Assessment — Telegram GetFullChannel + YouTube channels().list (2026-06-22).
