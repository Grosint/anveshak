---
name: Redis URL dedup with SHA256 keys and TTL
description: Skip re-fetching recently scraped URLs using Redis SET with sha256(url) key and 24h TTL; fail-open on errors
type: pattern
confidence: high
---

## Problem

The scraper re-fetched the same article URLs every cycle. Content-hash dedup in PostgreSQL (`ON CONFLICT(content_hash) DO NOTHING`) prevented duplicate rows, but the HTTP request still happened — wasting bandwidth, risking rate-limit blocks, and increasing latency.

## Solution

Redis key per URL with auto-expiry:

```python
_URL_SEEN_PREFIX = "scraper:seen:"

def _url_seen_key(url: str) -> str:
    return f"{_URL_SEEN_PREFIX}{hashlib.sha256(url.encode()).hexdigest()}"

async def _is_url_seen(redis, url: str) -> bool:
    try:
        return await redis.get(_url_seen_key(url)) is not None
    except Exception:
        return False  # fail open — fetch rather than silently skip

async def _mark_url_seen(redis, url: str) -> None:
    try:
        await redis.set(_url_seen_key(url), "1", ex=settings.scraper_url_seen_ttl_s)
    except Exception:
        pass  # logged, not fatal
```

## Design decisions

1. **SHA256 key** — raw URLs can be 500+ chars, exceeding Redis key best practices. SHA256 is fixed 64 chars.
2. **Per-URL keys with TTL** (not per-domain SETs) — each URL expires independently, no set-size growth, no manual cleanup.
3. **Fail-open** — if Redis is down, URLs are fetched normally. Content-hash dedup in PostgreSQL is the safety net. Never silently skip content.
4. **Feature flag** — `scraper_url_seen_enabled=True` allows disabling for testing/debugging.
5. **Mark AFTER insert** — `_mark_url_seen` is called after `_insert_content` succeeds, not before fetch. This ensures a URL is only marked seen if it was actually processed.
6. **`SET` not `SETNX`** — refreshes TTL on re-encounter within a job, preventing edge-case expiry.

## Impact

Steady-state: ~85% fewer HTTP requests per cycle (3,900 → ~585 for 39 sources × 100 links).
