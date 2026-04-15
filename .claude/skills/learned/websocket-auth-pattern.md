# Pattern: WebSocket JWT Authentication (FastAPI)

## When to load: any WebSocket endpoint that must be authenticated

---

## The trap

FastAPI's `Depends(get_current_user)` does NOT work on WebSocket handlers.
`HTTPBearer` reads the `Authorization` header, which browsers do not send
on WebSocket upgrade requests. The handler silently skips auth if you copy
the REST pattern.

## Correct pattern: token as query parameter

```python
@router.websocket("/ws/{session_id}")
async def my_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(..., description="Bearer JWT token"),
):
    from ..auth.jwt import verify_token
    try:
        verify_token(token)
    except Exception:
        await websocket.close(code=4001)  # 4001 = policy violation / unauthorised
        return

    await websocket.accept()   # accept ONLY after auth passes
    ...
```

## What NOT to do

```python
# WRONG — accept() before auth check
async def bad_websocket(websocket: WebSocket, ...):
    await websocket.accept()   # connection open before we know who this is
    token = await websocket.receive_text()   # too late — connection already logged
    ...

# WRONG — using Depends(get_current_user)
# FastAPI silently ignores Depends on WebSocket handlers in some versions
async def bad_websocket(
    websocket: WebSocket,
    user: dict = Depends(get_current_user),   # MAY NOT FIRE
):
    ...
```

## Client usage

```javascript
// Connect with token in query string
const ws = new WebSocket(
  `ws://api/signals/ws/${sessionId}?token=${jwtToken}&since=${lastSeen}`
);
```

## Close codes

| Code | Meaning |
|------|---------|
| 4001 | Unauthorised (invalid/missing token) |
| 4003 | Forbidden (valid token, wrong role) |
| 1000 | Normal close |

## Phase-check rule

**Every WebSocket handler must call `verify_token()` before `websocket.accept()`.**
This is enforced by the `security-auditor` agent hook on `services/**` writes.
