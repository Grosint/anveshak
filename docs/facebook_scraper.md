# Facebook Adapter — Research & Implementation Plan

## Research Summary (2026-06-20)

### Why Facebook is Hard

1. **Official Graph API useless for OSINT** — post-Cambridge Analytica (2018), `page_public_content_access` requires app review Meta won't approve for OSINT/LEA
2. **CrowdTangle dead** — shut down Aug 2024. Replacement (Meta Content Library) only for vetted academics
3. **No public post search endpoint** — removed in 2018
4. **Every scraper breaks regularly** — Facebook changes DOM structure frequently
5. **Account bans near-certain at scale** — aggressive scraping triggers bans within hours
6. **Login wall expanding** — most content now requires authentication

### API Marketplace Options (REJECTED — sovereignty violation)

Sending monitored page URLs to external APIs leaks surveillance targets. CLAUDE.md rule 10: intelligence data never leaves deployment boundary.

| Provider | Cost | Verdict |
|----------|------|---------|
| Apify | $29/mo | Python SDK, best ecosystem — but leaks targets |
| SociaVault | $29/mo | 25+ platforms, 6K credits — but leaks targets |
| Social Fetch | ~$4/mo | Cheapest — but leaks targets |
| RapidAPI (various) | Varies | Variable quality — but leaks targets |

### Recommended: Self-Hosted facebook-scraper

**Library:** `facebook-scraper` (kevinzg, 3200+ GitHub stars)
- HTTP-based scraper targeting `mbasic.facebook.com` (mobile endpoints, simple HTML)
- No browser automation needed
- Cookie-based auth with burner accounts
- Returns structured dicts: text, url, timestamp, reactions, comments, shares, images

**Install:** `pip install facebook-scraper>=0.2.60`

### Post Dict Shape (from library)

```python
{
    "post_id": "123456789",
    "text": "Post content here...",
    "post_url": "https://www.facebook.com/page/posts/123456789",
    "time": datetime(2026, 6, 20, 12, 0),
    "likes": 42,
    "reactions": {"like": 30, "love": 8, "wow": 4},
    "comments": 7,
    "shares": 3,
    "images": ["https://scontent.xx.fbcdn.net/..."],
    "video": "https://video.xx.fbcdn.net/...",
    "username": "PageName",
}
```

## Implementation Plan

### Settings

```python
# services/social/anveshak/social/settings.py
facebook_adapter_enabled: bool = False
facebook_cookies_json: str = ""          # JSON exported browser cookies
facebook_hourly_call_cap: int = 30       # ultra-conservative
facebook_max_posts_per_page: int = 10
facebook_proxy: str = ""                 # optional SOCKS5/HTTP proxy
```

### Adapter Design

```python
# services/social/anveshak/social/adapters/facebook.py

FACEBOOK_CIRCUIT_BREAKER_THRESHOLD = 10
FACEBOOK_CIRCUIT_BREAKER_COOLDOWN_S = 86400  # 24h

class FacebookRateLimitGuard:
    # Same Redis INCR pattern as InstagramRateLimitGuard
    # Hourly key, 30 req/hr cap

class FacebookAdapter(SourceAdapterBase):
    adapter_id = "facebook-v1"
    platform = "facebook"
    adapter_version = "1.0.0"

    authenticate():
        - Parse cookies JSON, set on facebook_scraper
        - Optional proxy from settings

    collect(topic_keywords, source_handles, topic_id):
        - Page monitoring: get_posts(page_name, pages=1, cookies=...)
        - Map post dicts to RawItem with engagement
        - Also extract page info (followers, about) as separate RawItem
        - Rate guard before every call
        - Per-page try/except, continue on failure

    _normalise_handle():
        - Strip facebook.com URL prefix, m.facebook.com, www
        - Return bare page name lowercase

    _post_to_raw_item():
        - engagement: {reactions, comments, shares, likes}
        - media_urls from images[] + video
        - author_handle = source_handle
```

### Wiring

- Add to `jobs.py` startup, `_REQUIRED_CREDENTIALS`, adapter factory
- Circuit breaker: 10 threshold, 86400s cooldown
- Add `"facebook"` to conformance suite allowed platforms

### Environment

```yaml
# infra/compose.yml (social service)
FACEBOOK_ADAPTER_ENABLED: ${FACEBOOK_ADAPTER_ENABLED:-false}
FACEBOOK_COOKIES_JSON: ${FACEBOOK_COOKIES_JSON:-}
FACEBOOK_HOURLY_CALL_CAP: ${FACEBOOK_HOURLY_CALL_CAP:-30}
FACEBOOK_PROXY: ${FACEBOOK_PROXY:-}
```

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| facebook-scraper breaks when FB changes DOM | HIGH | Circuit breaker + DEGRADED health; pin version; fork if abandoned |
| Cookie/account ban from Meta | HIGH | Burner cookies, 30 req/hr cap, 24h circuit breaker cooldown |
| Library abandoned | MEDIUM | Pin version; mbasic.facebook.com is simple HTML, maintainable |
| Cookies expire frequently | MEDIUM | refresh_credentials() + health check warns |
| mbasic.facebook.com login wall expands | MEDIUM | Cookies provide session; degrade gracefully |

## Key Decisions

- **Sovereignty preserved** — all scraping inside Docker, no external API calls
- **Cookie-based auth** — burner accounts only, never real analyst accounts
- **30 req/hr cap** — ultra-conservative (Instagram is 100/hr)
- **Best-effort adapter** — degrades gracefully, never crashes pipeline
- **Same patterns as Instagram** — rate guard, circuit breaker, health, session

## LEA Note

For **evidence collection**, use Meta's Law Enforcement Portal (`facebook.com/records/login`). India is #1 globally in data requests (99,000+ in H1 2024). This adapter is for **monitoring/intelligence**, not evidence.

## Files to Create/Modify

| File | Change |
|------|--------|
| `services/social/anveshak/social/adapters/facebook.py` | NEW |
| `services/social/anveshak/social/adapters/__init__.py` | Export |
| `services/social/anveshak/social/settings.py` | facebook_* settings |
| `services/social/anveshak/social/jobs.py` | Wire adapter |
| `services/social/pyproject.toml` | facebook-scraper dep |
| `infra/compose.yml` | FACEBOOK_* env vars |
| `.env.example` | Document vars |
| `tests/unit/test_facebook_adapter.py` | NEW |
| `tests/unit/test_social_conformance.py` | Add facebook conformance |
