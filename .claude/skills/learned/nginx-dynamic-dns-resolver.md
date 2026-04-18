# Nginx Dynamic DNS Resolution

## When to load: any task involving nginx reverse proxy to Docker services, or debugging 502 errors after container restarts

---

### Problem

Nginx resolves upstream hostnames **once at startup** and caches the IP indefinitely. When a backend container restarts (gets a new IP), nginx keeps sending to the old IP → **502 Bad Gateway**. This is invisible and intermittent — happens any time `docker compose up -d` recreates a service.

### Fix: `resolver` + `set $upstream` pattern

```nginx
# Use Docker's embedded DNS with short TTL
resolver 127.0.0.11 valid=10s ipv6=off;

location /api/ {
    # Variable forces nginx to re-resolve on every request
    set $upstream_api http://api:8000;
    proxy_pass $upstream_api;
    # ... other proxy_set_header directives
}
```

**Why both parts are needed:**
1. `resolver 127.0.0.11 valid=10s` — tells nginx to use Docker DNS and re-check every 10s
2. `set $upstream_api` — forces nginx to treat the hostname as a variable (static `proxy_pass http://api:8000` is resolved at config load time regardless of resolver)

### Without this fix

- `make up` recreates API container → new IP
- Frontend nginx still points to old IP → 502 for all API calls
- Only fix is restarting the frontend container manually
- Especially bad after `make fresh` or partial restarts

### Pitfall: `valid=` TTL

Don't set `valid=` too low (<5s) — it adds DNS overhead to every request. 10s is a good balance: fast enough to recover from restarts, low enough overhead for production.

### Pitfall: WebSocket locations need it too

Apply the same pattern to WebSocket `location` blocks — they're long-lived connections but still need initial resolution to work after restarts.
