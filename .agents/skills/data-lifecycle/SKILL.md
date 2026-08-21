---
name: data-lifecycle
description: "Retention, archival, dedup, and orphan recovery. Covers archive-to-JSONL before delete, media retention that nulls storage_path but keeps the row, the orphan sweep as a secondary safety net, in-memory per-job URL dedup, and Redis cross-job URL dedup. Use when working on retention policy, archival, purge jobs, or deduplication."
---

# Data Lifecycle

5 instincts. Retention, archival, dedup, orphan recovery.

## Archive Then Delete

- Defence deployments can't lose data. Pattern: query expired rows -> write JSONL.gz -> record in tracking table -> DELETE from PostgreSQL.
  Archive fails = skip delete, retry next cycle (idempotent).
  JSONL (grep-able), gzipped (~10x), one file per partition per month.
  Only delete processed items (`WHERE narrative_cluster_id IS NOT NULL`). Disabled by default (`=0`).
  See: `.agents/skills/learned/references/archive-then-delete-retention.md`

## Media Retention: Delete File, Keep Metadata

- Set `storage_path = NULL` after file deletion — signals "file cleaned up".
  All metadata (pHash, EXIF, deepfake_score, YOLO) stays intact in DB.
  Only delete files w/ completed vision analysis (JOIN on results table).
  Never DELETE the `media_assets` row — cascades destroy all computed analysis.
  See: `.agents/skills/learned/references/media-retention-metadata-preserve.md`

## Orphan Sweep Safety Net

- Insert + enqueue not atomic (Redis non-transactional). Sweep catches missed jobs.
  Query rows w/ null completion columns from last 1hr, every 5min, batches of 100.
  Runs in scheduler (not workers). SECONDARY to direct enqueue — not primary mechanism.
  Every insert-then-enqueue pair needs corresponding sweep query.
  See: `.agents/skills/learned/references/orphan-sweep-safety-net.md`

## URL-Level Media Dedup (In-Memory)

- Job-scoped `set[str]` for media URLs — zero latency, no coordination.
  Check before download, add after. GC'd when job returns (intentional — URLs may change between runs).
  Module-level set = memory leak. Redis SISMEMBER = overkill. DB pre-check = defeats bandwidth saving.
  See: `.agents/skills/learned/references/url-level-media-dedup.md`

## Redis URL Dedup (Cross-Job)

- SHA-256 key per URL, 24hr TTL, fail-open on Redis errors.
  Mark AFTER successful insert (not before fetch) — avoids missing content on retry.
  `SET` not `SETNX` — refreshes TTL. Content-hash dedup in PostgreSQL = safety net.
  See: `.agents/skills/learned/references/redis-url-dedup-sha256-ttl.md`
