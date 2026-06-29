# Network & External Integration

6 instincts. HTTP, proxies, DNS, Redis dedup/budget, robots.txt.

## httpx SOCKS Proxy Extra

- `httpx>=0.27` does NOT include SOCKS transport. Declare `httpx[socks]>=0.27` in pyproject.toml.
  Unit tests mock HTTP — bug only surfaces in containers against real .onion sites.
  General: when using optional extras (`[socks]`, `[async]`), always declare in pyproject.toml.
  See: `learned/httpx-socks-optional-extra.md`

## Nginx Dynamic DNS

- Nginx resolves upstreams once at startup, caches forever. Container restart (new IP) = 502.
  Fix: `resolver 127.0.0.11 valid=10s ipv6=off;` + `set $upstream` variable per location.
  Both parts required — static `proxy_pass` resolves at config load regardless of resolver.
  Apply to WebSocket locations too.
  See: `learned/nginx-dynamic-dns-resolver.md`

## RSS Paywall Validation

- Validate fetched content BEFORE replacing RSS summary. Paywall pages pass length checks.
  `is_paywall_page()`: count paywall indicators (3+ distinct = flag). Runs on raw text.
  Paywall detected = keep RSS summary, mark source "degraded" (not "down").
  See: `learned/rss-fetch-paywall-validation.md`

## robots.txt Cache with Permissive Default

- Cache parsed `RobotFileParser` per domain, 1hr TTL. Unreachable robots.txt = allow (not block).
  Skip `.onion` URLs entirely. `urllib.robotparser` stdlib — no extra dep.
  Wire into both primary and fallback fetch paths.
  See: `learned/robots-txt-cache-permissive-default.md`

## Redis URL Dedup

- SHA-256 key per URL, 24hr TTL, fail-open on Redis errors. Mark AFTER successful insert (not before fetch).
  `SET` not `SETNX` — refreshes TTL on re-encounter. Feature flag `scraper_url_seen_enabled`.
  Content-hash dedup in PostgreSQL remains safety net. ~85% fewer HTTP requests steady-state.
  See: `learned/redis-url-dedup-sha256-ttl.md`

## Redis Atomic Budget Guard

- `INCR` (atomic) then check — never GET->compare->SET (race condition).
  Over cap: `DECR` to undo, return False. Month-keyed `{prefix}:{YYYY-MM}` with TTL auto-reset.
  TTL set only on first write (`if new_count == 1`). Callers MUST check return value.
  See: `learned/redis-atomic-budget-guard.md`
