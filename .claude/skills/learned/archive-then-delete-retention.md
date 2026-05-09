# Pattern: Archive to JSONL.gz Before Deleting from PostgreSQL

## When to load: implementing data retention, cleanup jobs, or cold storage for any table

---

## Problem

Defence deployments can't lose data, but PostgreSQL tables can't grow unbounded.
Deleting old rows loses auditability. Keeping everything degrades performance.

## Pattern: Archive → Record → Delete

1. **Query expired rows** (batch of 500, oldest first, only processed items)
2. **Write to compressed JSONL** (`{root}/{partition_key}/YYYY-MM.jsonl.gz`)
3. **Record in tracking table** (topic_id, month, file_path, item_count)
4. **Delete from PostgreSQL** (only after successful write)
5. **If write fails → skip delete** (retry next cycle, idempotent)

```python
# Archive succeeds → delete
path = write_archive_batch(topic_id, month, items, archive_root)
await conn.execute("DELETE FROM content_items WHERE id = ANY($1)", ids)

# Archive fails → items survive in DB, retry next cycle
```

## Key design decisions

- **JSONL not CSV/Parquet** — grep-able with `gunzip | grep`, no special libraries
- **Gzipped** — ~10x compression on text data
- **One file per partition per month** — append-safe, corrupt-line-safe
- **Tracking table with UPSERT** — `ON CONFLICT (topic_id, month) DO UPDATE item_count += N`
- **Disabled by default** (`=0`) — operator enables via env var at deployment
- **Only delete processed items** — `WHERE narrative_cluster_id IS NOT NULL` ensures
  unclustered items survive (they might still form clusters)

## Future: MinIO/S3 swap

Same file format, same path structure. Change `CONTENT_ARCHIVE_ROOT` to a FUSE mount
or add `ARCHIVE_STORAGE_BACKEND=minio` with MinIO client. No archive format change.

## Files

- `services/analyst/anveshak/analyst/scheduler.py` — `archive_and_delete_expired()`, `write_archive_batch()`
- `services/api/migrations/versions/003_content_archives.py` — tracking table
