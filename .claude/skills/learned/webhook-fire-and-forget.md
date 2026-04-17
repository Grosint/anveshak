# Webhook Fire-and-Forget Pattern

## When to load: adding non-blocking notifications alongside primary delivery (WebSocket, email, etc.)

---

## Pattern

Webhook fires after primary delivery succeeds but never blocks or raises. Returns bool, caller ignores result.

```python
# notifications.py
async def send_webhook(payload: dict) -> bool:
    """POST to webhook URL. Returns True on success, False on any failure. Never raises."""
    if not settings.signal_webhook_enabled or not settings.signal_webhook_url:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers={
                "X-Anveshak-Event": "signal",
                "User-Agent": "Anveshak-Signal-Webhook/1.0",
            })
            return resp.status_code < 300
    except Exception:
        return False  # Never raises

# signal_delivery.py — called AFTER WebSocket broadcast
await broadcast_signal(payload)  # primary delivery
try:
    await send_webhook(payload)  # secondary, non-blocking
except Exception:
    pass  # triple-safe
await conn.execute(SQL_MARK_DELIVERED, ...)  # always runs
```

**Why:** Primary delivery (WebSocket) must never be blocked by secondary channels. Short timeout (10s) prevents the delivery loop from stalling. Double try/except ensures delivery marking always happens.

**Key:** The webhook function itself catches all exceptions AND the caller wraps it in try/except. Belt and suspenders — because a stuck delivery loop means signals stop reaching analysts.
