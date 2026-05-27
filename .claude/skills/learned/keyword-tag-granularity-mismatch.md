# Keyword-Tag Granularity Mismatch

## Problem

When matching user-facing keywords against a curated taxonomy using PostgreSQL
array overlap (`&&`), zero results are returned silently if the granularity differs.

**Example:** Topic keywords are multi-word phrases:
```
{"PLA Navy", "Indian Ocean", "Line of Actual Control"}
```

Catalog domain_tags are single lowercase words:
```
{"china", "military", "maritime", "ior"}
```

`ARRAY['PLA Navy'] && ARRAY['china','military']` → **false** (no exact match).
No error, no warning — just an empty result set.

## Solution

Normalize keywords before the overlap query:

```python
# Split multi-word phrases into individual lowercase words, skip short words
normalized_tags = set()
for kw in keywords:
    for word in kw.lower().split():
        if len(word) >= 3:  # skip "of", "in", etc.
            normalized_tags.add(word)
```

This turns `["PLA Navy", "Indian Ocean"]` into `{"pla", "navy", "indian", "ocean"}`,
which overlaps with `{"military", "navy", "maritime", "ior"}`.

Also add a text-search fallback in SQL for cases where tags don't capture everything:

```sql
WHERE domain_tags && $1
   OR EXISTS (
       SELECT 1 FROM unnest($1) AS kw
       WHERE LOWER(name) LIKE '%' || kw || '%'
          OR LOWER(description) LIKE '%' || kw || '%'
   )
```

## Why this matters

Silent empty results are the worst failure mode — the feature appears to work
but returns nothing. The analyst sees "No suggestions" and assumes the catalog
is empty, not that the matching logic is broken.

## When to apply

Any time you join user-generated text (keywords, tags, labels) against a curated
taxonomy (domain tags, category codes, enum values). Always check: are both sides
at the same granularity? If not, normalize before matching.
