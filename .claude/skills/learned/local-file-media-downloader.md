# Local File Path Support in Media Downloader

## Pattern
`download_media_asset()` was HTTP-only. Adapters that pre-download media to disk
(Telegram, WhatsApp bridge) passed local paths like `/app/media/topic/date/hash.jpg`
which httpx silently failed on with "URL missing http:// protocol".

## Fix
Add early return for local paths at the top of `download_media_asset()`:
```python
if url.startswith("/"):
    return await _handle_local_file(url, topic_id, storage_root)
```

`_handle_local_file()` validates path is inside `storage_root` using
`Path.resolve().relative_to()`, reads bytes, computes hash, copies to canonical path.

## Key pitfalls discovered
1. **Double "media" in path**: `storage_root / "media"` when `storage_root` IS `/app/media`
   creates `/app/media/media`. Validate against `storage_root` directly, not `storage_root / "media"`.
2. **String prefix match is not path-safe**: `path.startswith(root)` allows traversal via
   `../`. Always use `Path.resolve().relative_to()`.
3. **Docker volume permissions**: Bridge (root) writes files, social worker (anveshak user) reads.
   Directories need execute bit (`755`), files need read bit (`644`). `process.umask(0o022)` in
   Node.js, but existing files created under old umask need `chmod -R a+rX`.
4. **Dedup prevents media retry**: Once content_hash is inserted, re-poll skips the item entirely.
   Media download failure on first insert means media is permanently lost for that item.

## Where
- `sdk/anveshak/media/downloader.py` — `_handle_local_file()` function
- `services/social/anveshak/social/ingest.py` — calls `download_media_asset()` for media_urls
