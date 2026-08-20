# Job Orchestration

## When to load: any task involving ARQ jobs, background processing, or async pipelines

Consolidated from 5 learned instincts.

---

### Orphan sweep safety net

Insert + enqueue can't be atomic across DB and Redis. Periodically scan for
orphaned rows (embedding IS NULL, created > 5 min ago) and re-enqueue.

```python
# scheduler runs every 5 min
orphans = await conn.fetch(
    "SELECT id FROM content_items WHERE embedding IS NULL AND created_at < NOW() - INTERVAL '5 min'"
)
for row in orphans:
    await arq_pool.enqueue_job("analyse_content", row["id"])
```

See: `.claude/skills/learned/orphan-sweep-safety-net.md`

### Causal job chaining

Enqueue dependent jobs at the END of the parent job, not on a cron timer.
Scope by entity ID. Guard with existence check.

```python
# At end of scrape_topic job:
if items_inserted > 0:
    await arq_pool.enqueue_job("run_clustering", topic_id)
```

See: `.claude/skills/learned/causal-arq-job-chaining.md`

### Additive backfill via join table

When associating existing content with new topics, use a many-to-many join table.
Never UPDATE the primary table — it breaks UNIQUE constraints.

See: `.claude/skills/learned/additive-backfill-join-table.md`

### URL-level media dedup

Maintain a job-scoped `set[str]` of seen media URLs. Check before downloading.
Prevents redundant HTTP requests within a single scrape run.

See: `.claude/skills/learned/url-level-media-dedup.md`

### Cross-service event delivery

When services share a DB but can't call each other, use a `delivered_at IS NULL`
polling pattern. Writer inserts row → poller finds undelivered → pushes via
WebSocket → marks delivered.

See: `.claude/skills/learned/cross-service-delivery-loop.md`
