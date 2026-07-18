# Migration FK Type Must Match Target Table

## Problem

Migration `005_add_analyst_pins` used `topic_id UUID NOT NULL REFERENCES topics(id)` but `topics.id` is `TEXT`, not `UUID`. PostgreSQL error:
```
foreign key constraint "analyst_pins_topic_id_fkey" cannot be implemented
DETAIL: Key columns "topic_id" and "id" are of incompatible types: uuid and text.
```

Same issue for `org_id` and `analyst_id` — all reference TEXT PK tables.

## Solution

Always verify target table column type before writing FK references:
```sql
-- Check before writing migration
\d topics  -- id is TEXT, not UUID
\d organizations  -- id is TEXT
\d users  -- id is TEXT
```

Fix: use `TEXT` to match:
```sql
topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
org_id TEXT NOT NULL REFERENCES organizations(id),
analyst_id TEXT NOT NULL REFERENCES users(id),
```

## Rule

Before writing any migration with REFERENCES:
1. Run `\d target_table` to verify PK column type
2. FK column type MUST exactly match referenced column type
3. In Anveshak: topics, organizations, users all use TEXT PKs (not UUID)
4. geocoded_locations, extracted_entities, content_items use UUID PKs

Mocked unit tests won't catch this — only surfaces at migration runtime in container.

## See Also
- `rules/database.md` (aggregate SQL schema validation)
- `learned/aggregate-sql-schema-validation.md`
