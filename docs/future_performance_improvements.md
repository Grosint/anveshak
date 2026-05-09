# Future Performance Improvements

Tracked scale concerns for when Anveshak reaches 500+ topics with 100K+ items each.

**What's already fixed (this session, 2026-05-09):**
- Priority 1: Composite index `(topic_id, captured_at DESC)` — migration 002
- Priority 2: Time window on `SQL_GET_TOPIC_ENTITIES` — default 30 days

---

## Priority 3: SQL_LIST_TOPICS Cached Content Count

**Status:** Deferred — not a problem until 500+ topics × 100K+ items
**When to revisit:** If topic listing page takes >2s

**Problem:** `SQL_LIST_TOPICS` runs a correlated UNION subquery per topic to count content items (owned + backfilled). At 100 topics × 100K items, this is 100 subqueries per page load.

**Current mitigation:** Composite index `(topic_id, captured_at DESC)` from migration 002 makes each subquery an index scan. Adequate for current scale.

**Recommended fix:** Add `content_count INT DEFAULT 0` column to `topics` table. Update via scheduler every 5 minutes (already loops through active topics). Topic listing reads one column instead of running subqueries. A few minutes of staleness is fine for a dashboard count.

**Files to modify:**
- `services/api/migrations/versions/NNN_cached_content_count.py` — add column
- `services/analyst/anveshak/analyst/scheduler.py` — update count in cluster loop
- `services/api/anveshak/api/db/topics.py` — simplify `SQL_LIST_TOPICS` to read column

---

## Priority 4: Content Archive + Retention (IMPLEMENTING)

**Status:** Implementing now — ships disabled by default, enabled via `.env`
**Why now:** Deployed to defence sites with no remote access. Must ship with the product.

### Problem

`content_items` rows accumulate forever:
- 50 items/day × 100 topics × 365 days = **1.8M rows/year**
- `extracted_entities` grows 50x (90M rows/year)
- PostgreSQL slows: backups, vacuums, index rebuilds all degrade

### Solution: Archive to Compressed JSONL, Then Delete from PostgreSQL

```
┌─────────────────────────────────┐
│        PostgreSQL (hot)          │
│  content_items < 30 days         │
│  Active clustering, signals,     │
│  analytics, API queries          │
└───────────┬─────────────────────┘
            │ Daily scheduler sweep
            │ (items > CONTENT_RETENTION_DAYS
            │  AND narrative_cluster_id IS NOT NULL)
            v
┌─────────────────────────────────┐
│     Archive Storage (cold)       │
│  media/archive/{topic_id}/       │
│    2026-04.jsonl.gz              │
│    2026-05.jsonl.gz              │
│  One file per topic per month    │
│  Full content + entities as JSON │
└─────────────────────────────────┘
            │
            │ Future: swap local disk → MinIO/S3
            │ (change CONTENT_ARCHIVE_ROOT or add
            │  ARCHIVE_STORAGE_BACKEND=disk|minio)
            v
┌─────────────────────────────────┐
│     MinIO / S3 (future cold)     │
│  Same path structure, same files │
│  No code change needed           │
└─────────────────────────────────┘
```

### How the Archive Process Works (Step by Step)

**Runs:** Daily in analyst-scheduler (alongside cluster_loop, signal_loop, orphan_sweep)
**Disabled by default:** `CONTENT_RETENTION_DAYS=0` means keep everything in PostgreSQL forever

When enabled (e.g., `CONTENT_RETENTION_DAYS=30`):

1. **Query expired items** — find content_items older than 30 days that are already clustered
   (`narrative_cluster_id IS NOT NULL`). Unclustered items are never touched — they might
   still form clusters. Batch of 500, oldest first.

2. **Fetch full data for archive** — for each expired item, fetch:
   - All content_item fields (raw_text, clean_text, url, labels, sentiment, etc.)
   - All extracted_entities (entity_type, entity_text, confidence)
   - Joined in one SQL query

3. **Group by topic + month** — items are grouped by `topic_id` and `YYYY-MM` of `captured_at`.
   Each group writes to one archive file.

4. **Write compressed JSONL** — append to `{archive_root}/{topic_id}/YYYY-MM.jsonl.gz`.
   One JSON object per line. Gzipped for ~10x compression on text data.
   ```json
   {"id":"uuid","topic_id":"uuid","raw_text":"...","url":"...","captured_at":"2026-04-15T...","entities":[{"entity_type":"ORG","entity_text":"PLA","confidence":0.95}]}
   ```

5. **Record in content_archives table** — track what was archived:
   - topic_id, month, file_path, item_count, file_size
   - `ON CONFLICT (topic_id, month) DO UPDATE` — appends to existing month's count

6. **Delete from PostgreSQL** — `DELETE FROM content_items WHERE id = ANY($1)`
   - FK CASCADE automatically removes: extracted_entities, media_assets, vision_results,
     near_duplicates, topic_content_items
   - Only runs AFTER successful archive write
   - If archive write fails → items stay in PostgreSQL, retry next cycle

### What Survives in PostgreSQL After Archival

| Preserved (stays in DB) | Archived (moved to disk) |
|------------------------|------------------------|
| `narrative_clusters` (centroids, ISC, labels, summaries) | `content_items` (raw_text, clean_text, embeddings) |
| `signals` (fired, acknowledged, dismissed) | `extracted_entities` (NER results) |
| `reports` (immutable snapshots with source_snapshot) | `media_assets` + `vision_results` |
| `credibility_audit_log` (full history) | `near_duplicates` pairs |
| `sources` + `topics` (configuration) | `topic_content_items` backfill links |
| `content_archives` (references to archive files) | |

The intelligence output (clusters, signals, reports, credibility trail) stays permanently.
The raw input (articles, entities) moves to cold storage.

### Auditability

Every archived item is traceable:
- `content_archives` table records: which topic, which month, which file, how many items
- Archive files are JSONL — human-readable with `gunzip` + `grep`
- `content_hash` (SHA-256) in archive file matches what was in PostgreSQL
- Forensic recovery: parse JSONL, re-insert into PostgreSQL if needed

### Settings

```
CONTENT_RETENTION_DAYS=0         # 0 = disabled (default). 30 = archive after 30 days.
CONTENT_ARCHIVE_ROOT=/app/media/archive   # Local path. Later: MinIO mount point.
```

### Future: MinIO/S3 Migration

When MinIO is available:
- Mount MinIO bucket at `CONTENT_ARCHIVE_ROOT` (FUSE mount), OR
- Add `ARCHIVE_STORAGE_BACKEND=minio` with MinIO client, OR
- Simply copy existing archive files to MinIO bucket (same path structure)

No archive format change needed — same `.jsonl.gz` files, same `content_archives` references.

---

## Priority 5: Scheduler Throttling (IMPLEMENTING)

**Status:** Implementing now — ships disabled by default
**Why now:** Same reason as Priority 4 — can't push fixes to deployed sites

### Problem

`cluster_loop()` processes ALL active topics every 5 minutes. At 200 topics × clustering per topic, CPU saturates.

### Solution

`MAX_TOPICS_PER_CYCLE=0` (disabled, process all — current behavior). When set to e.g. 50:

1. Query active topics with pending unclustered items
2. Sort by most pending items first (most urgent)
3. Skip topics with zero unclustered items (no work)
4. Process only top N topics per cycle

```sql
SELECT t.id, COUNT(ci.id) FILTER (WHERE ci.narrative_cluster_id IS NULL
                                    AND ci.embedding IS NOT NULL) AS pending
FROM topics t
LEFT JOIN content_items ci ON ci.topic_id = t.id
WHERE t.status = 'active'
GROUP BY t.id
HAVING COUNT(...) > 0
ORDER BY pending DESC
LIMIT $1
```

Topics not processed this cycle get processed in the next 5-minute cycle. Fair rotation happens naturally — once a topic's items are clustered, its pending count drops and it yields priority.

### Settings

```
MAX_TOPICS_PER_CYCLE=0    # 0 = unlimited (default). 50 = process max 50 topics per 5-min cycle.
```
