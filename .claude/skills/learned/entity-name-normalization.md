# Entity Name Normalization — SQL Case-Folding + Python Alias Merging

## When to load: any feature aggregating NER entities by name (location map, entity graph, reports)

---

## The Problem

spaCy NER extracts entity text as-is from source content. Same entity appears as
multiple variants: "India"/"india"/"INDIA", "US"/"the United States"/"USA".
SQL `GROUP BY entity_text` treats these as separate entities — inflated counts,
duplicate map pins, fragmented analytics.

## The Solution

Two-layer normalization at the **query/aggregation layer** (not at NER/insert time):

### Layer 1: SQL LOWER() in GROUP BY

```sql
SELECT LOWER(ee.entity_text) AS entity_key,
       ee.entity_type,
       COUNT(DISTINCT ee.content_item_id) AS mention_count
FROM extracted_entities ee
GROUP BY LOWER(ee.entity_text), ee.entity_type
```

Merges case variants at DB level. Zero migration needed. Returns lowercase `entity_key`.

### Layer 2: Python alias merging

Post-query merge using `_normalize_location()` alias table:
- "us" → "united states"
- "bombay" → "mumbai"
- "the united states" → "united states"

Merge rules:
- `mention_count`: SUM (additive across variants)
- `source_count`: MAX (sources overlap — sum would overcount)
- `latest_mention`: MAX (keep most recent)
- Different `entity_type` for same name → keep separate (GPE "Delhi" ≠ FAC "Delhi")

### Layer 3: Display name

`_location_display_name()` converts normalized lowercase key to proper title case.
Known names in `_DISPLAY_NAMES` dict ("united states" → "United States"),
fallback to `.title()`.

## Why not normalize at insert time?

- Would require migration + backfill of all existing entities
- Raw entity text used by other features (co-occurrence, identifier extraction)
- Normalization at query time is non-destructive and immediate
- Different features may need different normalization rules

## Files

- `services/api/anveshak/api/routes/intelligence.py` — `_merge_location_rows()`, `_ALIASES`, `SQL_TOPIC_LOCATION_MAP`
- `tests/unit/test_location_normalization.py` — 17 tests covering merge logic
