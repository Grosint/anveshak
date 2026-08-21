# Pattern: Additive Backfill via Join Table (preserving UNIQUE constraints)

## When to load: adding many-to-many topic/content relationships, or backfilling existing data into new contexts

---

## Problem

You have `content_items` with `UNIQUE(content_hash)` — one row per unique piece of content.
A new topic wants to "claim" semantically related items that already belong to other topics.

Two naive approaches break things:
- **Copy rows**: `ON CONFLICT(content_hash) DO NOTHING` silently drops the insert. The item never appears in the new topic.
- **Change `topic_id`**: Breaks the owning topic's queries. Data loss.

## Solution: Join table for secondary membership

### Migration (additive — no existing queries break)

```sql
CREATE TABLE topic_content_items (
    topic_id         TEXT NOT NULL REFERENCES topics(id)        ON DELETE CASCADE,
    content_item_id  TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    similarity_score FLOAT NOT NULL DEFAULT 0.0,
    assigned_at      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (topic_id, content_item_id)   -- natural PK, also the dedup key
);
CREATE INDEX idx_tci_topic ON topic_content_items(topic_id);
```

### Backfill job (idempotent)

```python
SQL_SIMILAR_ITEMS = """
    SELECT ci.id, 1 - (ci.embedding <=> $2::vector) AS similarity_score
    FROM content_items ci
    LEFT JOIN topic_content_items tci
        ON tci.content_item_id = ci.id AND tci.topic_id = $1
    WHERE ci.topic_id != $1           -- exclude already-owned items
      AND ci.embedding IS NOT NULL
      AND tci.topic_id IS NULL         -- exclude already-backfilled items
      AND 1 - (ci.embedding <=> $2::vector) >= $3
    ORDER BY ci.embedding <=> $2::vector
    LIMIT 500
"""

SQL_UPSERT = """
    INSERT INTO topic_content_items (topic_id, content_item_id, similarity_score, assigned_at)
    VALUES ($1, $2, $3, $4)
    ON CONFLICT (topic_id, content_item_id) DO NOTHING
"""
```

### Surface in list query (UNION ALL — not UNION, to avoid hash dedup overhead)

```python
SQL_TOPIC_CONTENT = """
    SELECT ci.id, ci.url, ..., FALSE AS backfilled
    FROM content_items ci
    WHERE ci.topic_id = $1

    UNION ALL

    SELECT ci.id, ci.url, ..., TRUE AS backfilled
    FROM topic_content_items tci
    JOIN content_items ci ON ci.id = tci.content_item_id
    WHERE tci.topic_id = $1

    ORDER BY captured_at DESC
    LIMIT $2 OFFSET $3
"""
```

### Dispatch from topic creation (fire-and-forget)

```python
# In POST /topics handler — non-fatal: backfill failure must not block creation
try:
    redis = await arq_create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job("backfill_topic_job", topic_id)
except Exception as exc:
    log.warning("topics.backfill_enqueue_failed", topic_id=topic_id, error=str(exc))
```

## Key invariants preserved

- `UNIQUE(content_hash)` on `content_items` — unchanged, dedup still works
- Owning topic_id on each content_item — unchanged, Phase 1 queries unaffected
- `backfilled=True` flag in list response — analyst knows provenance
- `ON CONFLICT DO NOTHING` — backfill is idempotent, safe to re-run

## Threshold configuration

```
BACKFILL_SIMILARITY_THRESHOLD=0.85   # cosine similarity floor
```
Lower → more items surfaced, higher noise. 0.85 is a safe default for OSINT.
Make it an env var — never hardcode.
