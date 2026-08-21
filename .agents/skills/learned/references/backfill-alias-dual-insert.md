# Backfill with Alias Normalization Requires Dual Insert

## Problem

Backfill SQL uses `NOT EXISTS (WHERE entity_text_normalized = LOWER(entity_text))` to skip already-processed rows. But Python alias normalization maps "us" → "united states". The geocoded_locations row stores "united states", not "us". So the NOT EXISTS check never finds "us" → re-fetches it every batch → infinite loop.

## Solution

Insert geocoded_locations rows under BOTH the original lowered text AND the normalized alias:
```python
# Insert canonical form
await upsert("united states", "GPE", lat, lon, ...)
# Also insert alias source form so NOT EXISTS skips it next batch
await upsert("us", "GPE", lat, lon, ...)
```

Use `ON CONFLICT DO NOTHING` for idempotency.

For unresolved entities (can't geocode), insert with `geocode_source='unresolved'` and `lat=0, lon=0` so they're also skipped.

## Rule

When backfill SQL checks "already processed?" via a normalized key, and Python normalization changes the key (aliases, case folding), the SQL will never see the original key as processed. Either:
1. Insert under both original AND normalized keys, or
2. Track processed entities in a separate table/column
3. Use OFFSET pagination instead of NOT EXISTS

## See Also
- `learned/idempotent-cron-insert.md` (ON CONFLICT pattern)
- `rules/arq-jobs.md` (replay safety)
