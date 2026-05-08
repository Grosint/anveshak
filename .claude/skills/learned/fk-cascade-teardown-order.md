# FK Cascade Teardown Order

## Problem
Test fixtures that only delete their own table (e.g., `DELETE FROM topics WHERE id=$1`)
fail silently when FK-dependent rows exist, leaving orphaned data across the schema.
The `make_topic` fixture originally cleaned 5 tables but missed 8 others.

## Correct delete order for Anveshak's schema

When deleting by **topic_id**:
```
1. vision_results      (via media_assets → content_items)
2. media_assets        (via content_items)
3. extracted_entities   (via content_items)
4. report_source_warnings (via reports)
5. reports
6. near_duplicates     (via content_items — both a_id and b_id)
7. signals
8. UPDATE content_items SET narrative_cluster_id = NULL  ← circular FK!
9. narrative_clusters
10. topic_content_items
11. content_items
12. topic_sources
13. analysis_jobs
14. topics
```

When deleting by **source_id**:
```
1. credibility_audit_log
2. report_source_warnings
3. sources
```

## Circular FK trap
`content_items.narrative_cluster_id → narrative_clusters.id` creates a cycle:
you can't delete clusters before content_items (FK violation), and you can't
delete content_items before clusters (FK violation). Solution: NULL the FK first:
```sql
UPDATE content_items SET narrative_cluster_id = NULL WHERE topic_id = $1;
DELETE FROM narrative_clusters WHERE topic_id = $1;
DELETE FROM content_items WHERE topic_id = $1;
```

## Rule
When adding a new table with an FK to topics/sources/content_items, immediately
update the teardown in `tests/conftest.py` `make_topic` / `make_source` fixtures
AND `scripts/cleanup_test_data.sql`. Otherwise tests will silently leak rows.
