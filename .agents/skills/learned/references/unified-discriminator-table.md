# Unified Discriminator Table for Multi-Source Discovery

## Pattern

When multiple independent processes feed suggestions into a single review queue,
use one table with a `discovery_method` discriminator column instead of per-method tables.

```sql
CREATE TABLE discovered_sources (
    id               TEXT PRIMARY KEY,
    topic_id         TEXT NOT NULL REFERENCES topics(id),
    domain_or_handle TEXT NOT NULL,
    platform         TEXT DEFAULT 'web',
    discovery_method TEXT NOT NULL,  -- snowball | forwarding | entity_search | llm_suggestion
    citation_count   INT DEFAULT 1,
    confidence_score REAL,
    evidence         JSONB DEFAULT '{}',
    status           TEXT DEFAULT 'pending',  -- pending | approved | dismissed
    source_id        TEXT REFERENCES sources(id),
    ...
);
CREATE UNIQUE INDEX idx_discovered_unique
    ON discovered_sources(topic_id, domain_or_handle, discovery_method);
```

## Why one table, not four

1. **One approval flow** — approve/dismiss logic is identical regardless of method
2. **One frontend component** — `DiscoveredSourcesPanel` renders all methods uniformly
3. **One dedup constraint** — `(topic_id, domain_or_handle, discovery_method)` prevents
   the same domain from appearing twice via the same method, but allows it via different
   methods (e.g. snowball AND forwarding both find the same channel)
4. **One status filter** — analyst filters by `status=pending` to see all actionable items
5. **Evidence is method-specific** — JSONB `evidence` column stores method-specific metadata
   (citation_count for snowball, forward_count for forwarding, entity info for entity_search)

## Anti-pattern: separate tables

```sql
-- DON'T: separate tables per method
CREATE TABLE snowball_suggestions (...);
CREATE TABLE forwarding_suggestions (...);
CREATE TABLE entity_suggestions (...);
CREATE TABLE llm_suggestions (...);
```

This multiplies: 4 tables, 4 sets of CRUD functions, 4 API endpoints, 4 frontend panels,
4 approval flows — all doing essentially the same thing.

## When to apply

Any feature where multiple independent producers feed into a shared review/approval
queue. The discriminator column captures the "how it got here" while the rest of the
schema captures "what it is."
