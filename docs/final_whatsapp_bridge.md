# WhatsApp Adapter — Baileys Sidecar + Group Monitoring

## Context

Anveshak has social adapters for Telegram, Reddit, Bluesky, and X/Twitter. The user wants to add WhatsApp group monitoring using a self-hosted Baileys (WhatsApp Web) bridge as a Docker sidecar. This keeps the system fully sovereign — no Meta Business API dependency, no cloud callbacks. Analysts join WhatsApp groups of interest with their phone, and the system automatically ingests all messages.

## Architecture: Baileys Sidecar + Redis Buffer + Poll-Based Adapter

```
Analyst's Phone (QR pairing)
        │
        ▼
┌─────────────────────┐     RPUSH to Redis      ┌──────────────┐
│ whatsapp-bridge     │ ──────────────────────► │ Redis        │
│ (Node.js + Baileys) │                          │ anveshak:    │
│ Port 3002           │                          │ whatsapp:    │
│ /health, /qr, /groups                          │ buffer       │
└─────────────────────┘                          └──────┬───────┘
                                                        │ LPOP
                                                        ▼
                                              ┌──────────────────┐
                                              │ WhatsAppAdapter   │
                                              │ (Python, in       │
                                              │  social service)  │
                                              └────────┬─────────┘
                                                       │ ingest_raw_item()
                                                       ▼
                                              ┌──────────────────┐
                                              │ content_items    │
                                              │ (PostgreSQL)     │
                                              └──────────────────┘
```

**Why this design:**
- No Python WhatsApp Web library exists — Node.js Baileys is the standard
- Sidecar pushes to Redis buffer; Python adapter drains it via `collect()` — identical contract to all other adapters
- No webhook endpoint needed on the social service (unlike Meta Business API)
- Bridge is stateless except for auth session file (Docker volume)

## Implementation Steps

### Step 1: WhatsApp Bridge Sidecar (Node.js)

**Create: `services/whatsapp-bridge/`**

```
services/whatsapp-bridge/
├── package.json          # @whiskeysockets/baileys, ioredis, express
├── Dockerfile            # node:20-slim, npm ci --no-audit
├── src/
│   ├── index.js          # Express server + Baileys client
│   ├── redis.js          # Redis connection + RPUSH to buffer
│   └── health.js         # /health, /qr, /groups endpoints
└── auth/                 # .gitignore'd — session auth state (volume-mounted)
```

**Core behavior:**
- On startup, connects to WhatsApp Web via Baileys multi-device auth
- First run: generates QR code, serves at `GET /qr` (analyst scans with phone)
- Subsequent runs: restores session from `auth/` volume
- Listens for `messages.upsert` events on all groups
- For each message: serializes `{group_jid, sender, text, timestamp, media_keys}` as JSON, `RPUSH` to `anveshak:whatsapp:buffer`
- Media: downloads to shared `/data/media` volume (same as Telegram adapter)
- `GET /health` — returns `{status: "connected"|"disconnected", groups: N}`
- `GET /groups` — lists joined group names + JIDs (for source mapping)

**Env vars:**
- `REDIS_URL` — same Redis as Anveshak
- `WHATSAPP_BRIDGE_PORT=3002`
- `WHATSAPP_AUTH_DIR=/app/auth`
- `WHATSAPP_MEDIA_DIR=/data/media`
- `WHATSAPP_BUFFER_MAX=10000` — LTRIM cap to prevent unbounded growth

### Step 2: Python WhatsApp Adapter

**Create: `services/social/anveshak/social/adapters/whatsapp.py`**

```python
class WhatsAppAdapter(SourceAdapterBase):
    adapter_id = "whatsapp-v1"
    platform = "whatsapp"
    adapter_version = "1.0.0"
```

- **`authenticate()`**: HTTP GET to `{bridge_url}/health`. Raises `AdapterAuthError` if bridge is down or disconnected. Logs disabled warning if `whatsapp_adapter_enabled=False`.
- **`collect(topic_keywords, source_handles, topic_id)`**: Drains `anveshak:whatsapp:buffer` via `LPOP` (up to `whatsapp_buffer_drain_max` per cycle, default 100). Parses each JSON entry. Filters to only groups matching `source_handles` (group JID or name). Yields `RawItem` per message.
- **`health()`**: Checks bridge `/health` endpoint + Redis buffer key freshness.

**RawItem mapping:**
- `raw_text` = message body
- `url` = `https://wa.me/group/{group_jid}/{message_id}` (synthetic, for dedup/display)
- `platform` = `"whatsapp"`
- `captured_at` = message timestamp (UTC)
- `source_handle` = group JID (matches `sources.url_or_handle`)
- `media_urls` = local paths after bridge downloads to shared volume
- `language` = None (detect in analyst pipeline)

### Step 3: Settings

**Modify: `services/social/anveshak/social/settings.py`**

Add after X/Twitter block:
```python
# WhatsApp (Baileys bridge sidecar)
whatsapp_adapter_enabled: bool = False
whatsapp_bridge_url: str = "http://whatsapp-bridge:3002"
whatsapp_buffer_drain_max: int = 100    # max messages per poll cycle
```

No API keys needed — auth is via QR code on the bridge sidecar.

### Step 4: Registration in jobs.py

**Modify: `services/social/anveshak/social/jobs.py`**

1. Add to `_REQUIRED_CREDENTIALS`:
```python
"whatsapp": []  # no env var credentials — auth is QR-based via bridge
```

2. Add to `adapter_configs` in `startup()`:
```python
(settings.whatsapp_adapter_enabled, "whatsapp", lambda: WhatsAppAdapter(ctx["arq_pool"])),
```

3. Import inside `startup()`:
```python
from .adapters.whatsapp import WhatsAppAdapter
```

### Step 5: Main loop update

**Modify: `services/social/anveshak/social/main.py`**

Add to enabled adapters log (line ~50):
```python
if settings.whatsapp_adapter_enabled:
    enabled.append("whatsapp")
```

Update the `hint=` string in the no-adapters warning.

### Step 6: Docker Compose

**Modify: `infra/compose.yml`**

1. Add `whatsapp-bridge` service:
```yaml
whatsapp-bridge:
  build: ../services/whatsapp-bridge
  ports: ["3002:3002"]
  environment:
    REDIS_URL: redis://redis:6379
    WHATSAPP_BRIDGE_PORT: 3002
    WHATSAPP_AUTH_DIR: /app/auth
    WHATSAPP_MEDIA_DIR: /data/media
  volumes:
    - whatsapp-auth:/app/auth        # persist session across restarts
    - media-data:/data/media         # shared with vision service
  depends_on:
    redis: { condition: service_healthy }
  profiles: ["whatsapp"]              # only starts when explicitly enabled
  healthcheck:
    test: ["CMD", "wget", "-q", "--spider", "http://localhost:3002/health"]
    interval: 30s
    timeout: 5s
    retries: 3
```

2. Add env vars to `social` service environment block:
```yaml
WHATSAPP_ADAPTER_ENABLED: ${WHATSAPP_ADAPTER_ENABLED:-false}
WHATSAPP_BRIDGE_URL: ${WHATSAPP_BRIDGE_URL:-http://whatsapp-bridge:3002}
```

3. Add `whatsapp-auth` volume.

### Step 7: Conformance Tests

**Modify: `tests/unit/test_social_conformance.py`**

1. Update valid platforms set to include `"whatsapp"`
2. Add `TestWhatsAppAdapterConformance` class (5 conformance assertions + adapter-specific tests)

### Step 8: Unit Tests

**Create: `tests/unit/test_whatsapp_adapter.py`**

- `collect()` drains Redis buffer, yields correct RawItems
- `collect()` filters by source_handles (only matching groups)
- `collect()` respects `buffer_drain_max` limit
- `collect()` returns empty on empty buffer
- `authenticate()` raises `AdapterAuthError` when bridge is down
- `health()` returns correct status
- Message JSON parsing edge cases (no text, media-only, etc.)

### Step 9: Environment & Docs

**Modify: `.env.example`** — add WhatsApp section with setup instructions

**Create: `docs/whatsapp_setup.md`** — step-by-step:
1. Enable with `WHATSAPP_ADAPTER_ENABLED=true`
2. Start bridge: `docker compose --profile whatsapp up -d`
3. Scan QR: open `http://localhost:3002/qr` in browser, scan with phone
4. List groups: `curl http://localhost:3002/groups`
5. Create sources: `POST /api/v1/sources` with `platform: "whatsapp"`, `url_or_handle: "<group_jid>"`
6. Link to topic: `POST /api/v1/topics/{id}/sources/{source_id}`

### Step 10: Platform value updates

**Modify: `services/social/anveshak/social/adapters/base.py`** — update RawItem platform docstring to include `whatsapp`

**Modify: `sdk/anveshak/models/source.py`** — update platform docstring comment

## Files Summary

| Action | File | Purpose |
|--------|------|---------|
| Create | `services/whatsapp-bridge/package.json` | Node.js deps (baileys, ioredis, express) |
| Create | `services/whatsapp-bridge/Dockerfile` | node:20-slim container |
| Create | `services/whatsapp-bridge/src/index.js` | Baileys client + message listener |
| Create | `services/whatsapp-bridge/src/redis.js` | RPUSH buffer logic |
| Create | `services/whatsapp-bridge/src/health.js` | Express health/QR/groups endpoints |
| Create | `services/social/anveshak/social/adapters/whatsapp.py` | Python adapter (poll Redis buffer) |
| Create | `tests/unit/test_whatsapp_adapter.py` | Adapter unit tests |
| Create | `docs/whatsapp_setup.md` | Operator setup guide |
| Modify | `services/social/anveshak/social/settings.py` | Add 3 WhatsApp settings |
| Modify | `services/social/anveshak/social/jobs.py` | Register adapter in startup |
| Modify | `services/social/anveshak/social/main.py` | Add to enabled list |
| Modify | `infra/compose.yml` | Add bridge service + env vars |
| Modify | `.env.example` | Document new env vars |
| Modify | `tests/unit/test_social_conformance.py` | Add whatsapp to valid platforms + conformance class |
| Modify | `services/social/anveshak/social/adapters/base.py` | Update platform docstring |

## Verification

1. `make test-unit` — conformance + adapter tests pass
2. `docker compose --profile whatsapp up -d` — bridge starts healthy
3. Open `http://localhost:3002/qr` — QR code renders
4. Scan QR with phone — bridge logs `"connected"`
5. `curl http://localhost:3002/groups` — lists joined groups
6. Create source + link to topic via API
7. Send a test message in a monitored group
8. Check `redis-cli LLEN anveshak:whatsapp:buffer` — message buffered
9. Wait for poll cycle — message appears in `content_items`
10. `make ps` — all containers healthy
