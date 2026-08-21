# Media Serving Endpoint — Org Isolation Required

## Pattern
When serving media files (images, videos, documents) to the frontend via API,
ALWAYS verify org access through the ownership chain:

```
media_asset → content_item → topic → org_id → verify_topic_access(user)
```

## Why
Media assets are stored on a shared Docker volume. The media_asset_id is a UUID
that can be guessed or enumerated. Without org isolation, any authenticated user
can view any organization's media by calling:
```
GET /api/v1/content/media/{guessed_asset_id}
```

## Implementation
```python
@router.get("/media/{asset_id}")
async def serve_media(asset_id, db=Depends(get_db), user=Depends(require_role(...))):
    row = await db.fetchrow(SQL_GET_MEDIA_ASSET_PATH, asset_id)
    # SECURITY: verify org access via topic ownership chain
    await topics_db.verify_topic_access(db, row["topic_id"], user)
    return FileResponse(path=row["storage_path"], media_type=content_type)
```

The SQL must JOIN through content_items to get topic_id:
```sql
SELECT ma.storage_path, ci.topic_id
FROM media_assets ma
JOIN content_items ci ON ci.id = ma.content_item_id
WHERE ma.id = $1
```

## Applies to
Any endpoint that serves files from the shared media volume — images, PDFs,
report exports, video thumbnails. Every file serving route needs the topic_id
→ verify_topic_access chain.

## Where
- `services/api/anveshak/api/routes/vision.py` — `serve_media()` endpoint
