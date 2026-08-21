# Global Sources with Org-Scoped Visibility

## Pattern

Sources (RSS feeds, websites, Telegram channels) are global entities — a feed is the same feed regardless of who monitors it. Making sources org-scoped creates problems:
- Duplicate source rows for the same URL (two orgs monitoring BBC)
- Duplicate health checks (same URL probed twice)
- Divergent credibility scores for the same real-world source

Instead, use a visibility join table:
```sql
CREATE TABLE org_sources (
    org_id    TEXT NOT NULL REFERENCES organizations(id),
    source_id TEXT NOT NULL REFERENCES sources(id),
    PRIMARY KEY (org_id, source_id)
);
```

The `SQL_LIST_SOURCES` query for non-super-admin JOINs through `org_sources`:
```sql
SELECT s.* FROM sources s
JOIN org_sources os ON os.source_id = s.id
WHERE os.org_id = $1
```

When an org creates a source, it's auto-linked in `org_sources`. A super-admin can grant visibility to additional orgs.

## Why

The architect review identified this: the initial plan made sources fully org-scoped, which would duplicate shared infrastructure. The visibility table decouples ownership from access.

## How to apply

When a resource is shared infrastructure but access must be org-scoped:
1. Keep the resource table global (no org_id, or org_id = creator only)
2. Create a visibility/access join table (`org_<resource>`)
3. Filter list queries via JOIN to the visibility table
4. Use `verify_<resource>_access()` that checks the visibility table
