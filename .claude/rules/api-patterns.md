# API Patterns

Consolidated from 3 learned instincts. WebSocket auth, webhooks, and backfill strategy.

## WebSocket JWT Authentication

FastAPI `Depends(get_current_user)` does NOT work on WebSocket handlers.
Browsers don't send `Authorization` header on WebSocket upgrade.

Correct pattern: token as query parameter, verify BEFORE `accept()`:
```python
@router.websocket("/ws/{session_id}")
async def my_websocket(
    websocket: WebSocket, session_id: str,
    token: str = Query(...),
):
    try:
        verify_token(token)
    except Exception:
        await websocket.close(code=4001)
        return
    await websocket.accept()  # ONLY after auth passes
```

**Rule:** Every WebSocket handler must call `verify_token()` before `websocket.accept()`.
See: `learned/websocket-auth-pattern.md`

## Webhook Fire-and-Forget

Secondary notifications (webhook, email) must never block primary delivery (WebSocket).

Pattern: webhook function catches all exceptions AND caller wraps in try/except.
Short timeout (10s). Returns bool, caller ignores result. Delivery marking always runs.
```python
await broadcast_signal(payload)  # primary
try:
    await send_webhook(payload)  # secondary, never raises
except Exception:
    pass
await conn.execute(SQL_MARK_DELIVERED, ...)  # always runs
```
See: `learned/webhook-fire-and-forget.md`

## Additive Backfill via Join Table

When backfilling content into topics/trackers, use a many-to-many join table
(`topic_content_items`, `tracker_content_items`) rather than UPDATE on the
primary table. Preserves UNIQUE constraints and allows an item to belong to
multiple topics/trackers.

Pattern: `INSERT INTO join_table (parent_id, item_id) ... ON CONFLICT DO NOTHING`
See: `learned/additive-backfill-join-table.md`
