# Sidecar Bridge + Redis Buffer Pattern

## Pattern
When a platform SDK only exists in a different language (Baileys = Node.js,
Anveshak = Python), use a sidecar bridge:

```
Platform API → Sidecar (Node.js) → RPUSH Redis buffer → Python adapter LPOP
```

The Python adapter implements the same `SourceAdapterBase.collect()` contract —
drains the buffer instead of calling the platform API directly.

## Key design decisions
1. **RPUSH + LTRIM**: buffer capped to prevent unbounded growth when worker is down.
   `LTRIM key -MAX -1` keeps newest, drops oldest.
2. **Logout sentinel**: bridge pushes `{"_type": "logout"}` on disconnect reason=loggedOut.
   Adapter reads sentinel from buffer → raises AdapterAuthError → circuit breaker opens →
   signal fired to topic dashboard.
3. **No credentials in Python**: auth is QR/pairing code on the bridge. Python adapter
   only needs bridge URL. `_REQUIRED_CREDENTIALS["whatsapp"] = []`.
4. **Pre-collect health check**: adapter GETs bridge `/health` before LPOP to detect
   logout early (don't silently drain empty buffer forever).
5. **Pydantic validation on buffer messages**: parse every LPOP'd JSON through a strict
   model before yielding RawItem. Prevents injection via Redis.

## Pitfalls
- **Stale sentinels**: old logout sentinels from failed pairing attempts stay in buffer.
  Flush buffer after re-pairing: `redis-cli DEL anveshak:whatsapp:buffer`
- **Sequential adapter loop**: poll_social_topic iterates adapters sequentially.
  If YouTube/Telegram hangs, WhatsApp never gets a turn. Consider per-adapter timeouts.
- **Volume permissions**: sidecar runs as root, Python service as non-root user.
  Files need world-readable permissions (umask 0o022, directories 755).

## Where
- `services/whatsapp-bridge/` — Node.js Baileys sidecar
- `services/social/anveshak/social/adapters/whatsapp.py` — Python adapter
- `services/social/anveshak/social/jobs.py` — registration + logout signal
