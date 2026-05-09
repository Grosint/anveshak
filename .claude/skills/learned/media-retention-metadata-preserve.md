---
name: media-retention-metadata-preserve
description: Delete expired media files but preserve DB metadata (pHash, EXIF, scores) by setting storage_path=NULL
type: pattern
confidence: high
source: media retention policy implementation for vision pipeline
---

# Media Retention with Metadata Preservation

When implementing file retention/cleanup for processed media, delete the file
but preserve all computed metadata in the database.

## Pattern

1. Only delete files where processing is **complete** (JOIN on results table)
2. Set `storage_path = NULL` after deletion — signals "file cleaned up"
3. All metadata (pHash, EXIF, deepfake_score, YOLO detections) stays intact
4. pHash reverse search still works (DB-only query on BIGINT column)
5. Credibility scoring still works (reads deepfake_score, not file)

## SQL Safety

```sql
-- Only fetch assets with completed vision analysis
SELECT ma.id, ma.storage_path
FROM media_assets ma
JOIN vision_results vr ON vr.media_asset_id = ma.id
WHERE ma.created_at < $1
  AND ma.storage_path IS NOT NULL  -- skip already-cleaned
LIMIT 100  -- bounded batch
```

## Why storage_path = NULL (not row deletion)

- `media_assets` row is FK'd to `vision_results`, `content_items`
- Deleting the row cascades — destroys all computed analysis
- NULL storage_path means "file gone, metadata alive"
- Re-analysis jobs check for `FileNotFoundError` and handle gracefully

## How to apply

When adding retention/cleanup for any file-backed data, always separate
"file exists on disk" from "metadata exists in DB". Delete files, keep metadata.
Use a nullable path column as the indicator.
