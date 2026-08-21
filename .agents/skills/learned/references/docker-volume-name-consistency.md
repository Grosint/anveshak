---
name: docker-volume-name-consistency
description: All services sharing a data directory must mount the same named Docker volume — mismatched names create invisible data silos
type: pitfall
confidence: high
source: vision media volume bug (scraper-worker mounted media_store, vision-worker mounted vision_media)
---

# Docker Volume Name Consistency

When multiple services write/read the same data directory, every service MUST mount
the same named volume. Docker named volumes are independent — `media_store:/app/media`
and `vision_media:/app/media` are two **separate** directories on the host.

## The Failure Mode

- Service A writes to `volume_a:/app/media`
- Service B reads from `volume_b:/app/media`
- Both containers see `/app/media` — no error, no log, no crash
- Service B simply never finds Service A's files
- `FileNotFoundError` in downstream jobs is the only symptom

## Why It's Silent

- Both containers start successfully
- Health checks pass (they check process, not data)
- The mount path is identical inside both containers
- Only the Docker volume name differs — invisible from inside the container

## Prevention

1. Use a YAML anchor for shared volume mounts:
   ```yaml
   x-media-volume: &media-volume
     - vision_media:/app/media

   services:
     scraper-worker:
       volumes: *media-volume
     vision-worker:
       volumes: *media-volume
   ```

2. Or grep for the mount path and verify volume name consistency:
   ```bash
   grep -n '/app/media' infra/compose.yml
   ```

3. After any compose change, verify with:
   ```bash
   docker compose config | grep -A2 'volumes:'
   ```

## How to apply

After any change to `infra/compose.yml` volumes, grep for the mount path
across all services and verify they all use the same named volume.
