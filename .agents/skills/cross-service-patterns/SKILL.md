---
name: cross-service-patterns
description: "Inter-service communication and scope threading. Covers DB polling delivery loops, cross-service metadata enrichment via another service ARQ queue, fail-open enrichment, the scope param passthrough invariant, and extracting expensive input once for reuse. Use when wiring two services together or threading a scoping parameter through a route."
---

# Cross-Service Patterns

5 instincts. Inter-service communication, enrichment, scope threading.

## DB Polling Delivery Loop

- Writer inserts events w/ `delivered_at = NULL`. Pusher owns polling loop.
  Partial index on `delivered_at IS NULL`. Mark delivered even w/ zero sessions — clients replay via `?since=`.
  Poll interval: 5s for interactive alerts, 30-60s for audit/reports.
  Don't use `SELECT FOR UPDATE SKIP LOCKED` — single delivery loop, partial index simpler.
  See: `.agents/skills/learned/references/cross-service-delivery-loop.md`

## Cross-Service Metadata Enrichment

- Service A (API) creates row sync. Enqueues ARQ job on Service B's queue for metadata.
  Service B worker UPDATEs row's JSONB directly. Frontend shows primary data immediately.
  Fail-open: social service down = assessment works without metadata.
  Queue name must match worker's actual queue — grep `WorkerSettings` for `queue_name`.
  See: `.agents/skills/learned/references/cross-service-metadata-enrichment.md`

## Fail-Open Enrichment

- Pipeline A->B->C->D where C = optional enrichment. C fails = A->B->D, not crash.
  Wrap in try/except: structured log warning + safe defaults (empty list/dict).
  Downstream must use `if data:` guards. Do NOT apply when step produces required data (RAG chunks, content_hash).
  See: `.agents/skills/learned/references/fail-open-enrichment-steps.md`

## Scope Param Passthrough Invariant

- Route accepts scoping param (`topic_id`, `source_id`) = EVERY code path must pass it to DB layer.
  Invariant: `route accepts param` -> `all branches pass param` -> `SQL uses param`.
  Bug invisible w/ one topic per org — exposed when second topic added.
  Check all if/elif/else branches, especially time-range queries w/ separate SQL.
  See: `.agents/skills/learned/references/scope-param-passthrough-invariant.md`

## Extract Once, Reuse Across Steps

- Shared expensive input (frame extraction, embedding, API fetch) = extract ONCE, pass to all steps.
  Video: extract keyframes once, pass to deepfake/YOLO/CLIP/pHash.
  Cap frames w/ `video_max_analysis_frames` + even sampling for temporal coverage.
  Each step needs different aggregation: deepfake=max, YOLO=union-dedup, CLIP=best-per-category, pHash=first.
  See: `.agents/skills/learned/references/extract-once-reuse-across-steps.md`
