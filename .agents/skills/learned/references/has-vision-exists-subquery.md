# has_vision Flag via EXISTS Subquery

## Pattern
When the frontend needs to know if a content item has related data in a child table
(media_assets + vision_results), use an EXISTS subquery in the list SQL rather than
N+1 API calls from the client.

```sql
SELECT ci.*,
       EXISTS (
           SELECT 1 FROM media_assets ma
           JOIN vision_results vr ON vr.media_asset_id = ma.id
           WHERE ma.content_item_id = with_counts.id
       ) AS has_vision
FROM with_counts
```

## Why not LEFT JOIN + count?
- EXISTS short-circuits on first match — faster than COUNT(*)
- No GROUP BY needed — doesn't change the row cardinality
- Returns boolean directly — no post-processing in Python

## Pitfall: relevance gate hides results
Items with `has_vision=true` may be invisible in the feed because they're filtered
out by `topic_relevance_score < threshold`. Media-only messages (e.g. `[media:image] /path`)
have near-zero relevance to the topic query. The badge exists but the item doesn't
show in the feed.

## Where
- `services/api/anveshak/api/db/topics.py` — `get_topic_content()` SQL
- `frontend/src/api/content.ts` — `has_vision?: boolean` on ContentItem
- `frontend/src/components/content/ContentCard.tsx` — camera badge
