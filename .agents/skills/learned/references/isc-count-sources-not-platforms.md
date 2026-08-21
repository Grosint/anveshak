---
name: ISC must count distinct sources, not platforms
description: independent_source_count should count distinct source_id values, not distinct platform strings — consolidating sources to one platform (e.g. all RSS) collapses ISC to 1
type: pitfall
confidence: high
---

## Problem

`count_independent_sources()` counted `len(set(platforms))` — distinct platform strings like "rss", "web", "telegram". After consolidating NDTV, Hindu, ToI from web to RSS, all topics had max ISC=2 (rss + web). Three different news organisations confirming the same narrative = ISC 1 because they're all "rss".

This silently broke the signal engine: ISC=3 signals became physically impossible.

## Fix

Count distinct `source_id` values, not `platform` values:

```python
# WRONG — collapses all RSS sources into ISC=1
def count_independent_sources(platforms: list[str]) -> int:
    return len(set(platforms))

# CORRECT — each source is independently counted
def count_independent_sources(source_ids: list[str]) -> int:
    return len(set(source_ids))
```

Also required:
- SQL: `SELECT DISTINCT ci.source_id` instead of `SELECT DISTINCT s.platform`
- `EmbeddingRow` field: `platform` → `source_id`
- `ClusterData` field: `platforms` → `source_ids`
- All 4 embedding SQL queries: `s.platform` → `ci.source_id`
- All test fixtures using `EmbeddingRow(platform=...)` → `EmbeddingRow(source_id=...)`

## Why this matters

ISC is the signal engine's core metric. It answers: "how many independent sources corroborate this narrative?" That's a question about organisations, not protocols. NDTV via RSS and NDTV via web is the same source. NDTV via RSS and The Hindu via RSS are different sources.

## How to detect

If you ever see max ISC = (number of platforms in use), the counting is likely wrong. A healthy system should have ISC values up to (number of distinct sources in topic).
