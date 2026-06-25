# WhatsApp Adapter Setup Guide

## Prerequisites

- Docker Compose running (Anveshak stack)
- A WhatsApp account (ideally dedicated for monitoring)
- Phone with WhatsApp installed

## 1. Generate Bridge Token

```bash
openssl rand -hex 32
```

Copy the output — this secures the bridge endpoints.

## 2. Configure Environment

Add to your `.env` file:

```bash
WHATSAPP_ADAPTER_ENABLED=true
WHATSAPP_BRIDGE_TOKEN=<paste-token-here>
```

## 3. Start the Bridge

```bash
docker compose -p anveshak --env-file .env --profile whatsapp up -d
```

Check status:
```bash
make ps
```

The `whatsapp-bridge` container should appear as healthy.

## 4. Pair Your Phone

Open in your browser:
```
http://localhost:3002/qr
```

In WhatsApp on your phone:
1. Go to **Settings** > **Linked Devices**
2. Tap **Link a Device**
3. Scan the QR code on screen

The page auto-refreshes. Once paired, it shows "Already connected".

## 5. Verify Connection

```bash
curl -H "Authorization: Bearer $WHATSAPP_BRIDGE_TOKEN" http://localhost:3002/health
```

Expected: `{"status":"connected","groups":N,...}`

## 6. List Joined Groups

```bash
curl -H "Authorization: Bearer $WHATSAPP_BRIDGE_TOKEN" http://localhost:3002/groups
```

Returns a list of groups with JIDs:
```json
[
  {"jid": "120363001234567890@g.us", "name": "OSINT Watch", "participants_count": 42}
]
```

Copy the `jid` value for the groups you want to monitor.

## 7. Create Sources

For each group to monitor:

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_TOKEN" \
  -d '{
    "name": "OSINT Watch Group",
    "platform": "whatsapp",
    "url_or_handle": "120363001234567890@g.us"
  }'
```

## 8. Link Sources to Topic

```bash
curl -X POST http://localhost:8000/api/v1/topics/{topic_id}/sources/{source_id} \
  -H "Authorization: Bearer $API_TOKEN"
```

## 9. Verify Ingestion

1. Send a test message in a monitored WhatsApp group
2. Check Redis buffer: `redis-cli LLEN anveshak:whatsapp:buffer`
3. Wait for the next poll cycle (default 15 minutes)
4. Check content_items table for new entries with `platform = 'whatsapp'`

## Troubleshooting

### Session expired / "logged_out" signal appears
The bridge lost its WhatsApp session (phone unlinked device, or WhatsApp forced re-auth).

Fix:
1. Restart the bridge: `docker compose -p anveshak --env-file .env --profile whatsapp restart whatsapp-bridge`
2. Re-scan QR at `http://localhost:3002/qr`

### Bridge container not starting
Check logs: `docker compose -p anveshak --env-file .env logs whatsapp-bridge`

Common causes:
- Redis not healthy (bridge depends on Redis)
- Port 3002 already in use

### Messages not appearing in content_items
1. Verify source JID ends with `@g.us` (group JID, not personal)
2. Verify source is linked to the topic
3. Check `redis-cli LLEN anveshak:whatsapp:buffer` — if 0, bridge may not be receiving messages
4. Check social worker logs for errors

### Media not analyzed by vision
1. Check `media_assets` table for new rows
2. Verify shared volume: bridge and social service must both mount `vision_media:/app/media`
3. Check vision worker logs for `run_vision_analysis` jobs

## Architecture

```
Phone (QR) → whatsapp-bridge (Baileys/Node.js)
                    ↓ RPUSH
              Redis buffer (anveshak:whatsapp:buffer)
                    ↓ LPOP
              WhatsAppAdapter (Python, social service)
                    ↓ ingest_raw_item()
              content_items (PostgreSQL)
                    ↓ media_urls
              download_media_asset() → media_assets
                    ↓ enqueue
              run_vision_analysis (YOLO, CLIP, deepfake)
```

## Limits

- WhatsApp allows max 4 linked devices — bridge uses 1 slot
- Buffer caps at 10,000 messages (oldest dropped if worker is down)
- Baileys is unofficial — WhatsApp protocol changes may require bridge updates
