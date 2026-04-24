# Chinese Source Access via Proxy Routing — Feature Plan

## Status: PLANNED (not yet implemented)

## Problem Statement

An IAF analyst wants to track Chinese open sources (Xinhua, Weibo, Baidu News,
CCTV, Bilibili, Zhihu, etc.), but many Chinese websites geo-restrict or throttle
non-Chinese IP addresses. The current scraper has only a single global
`tor_proxy_url` — Tor exit nodes are actively blocked by Chinese services, and
there is no per-source routing or proxy rotation.

**Key insight:** The Great Firewall blocks Chinese users from accessing *outside*
sites. Our problem is the *reverse* — Chinese site operators blocking/throttling
*foreign* IPs via geo-fencing, CDN routing, and anti-bot measures.

## Operational Prerequisite: CN Exit Node Proxies

Anveshak's code will be **provider-agnostic** — it accepts any SOCKS5 or HTTP
proxy URL. But IAF must procure at least one proxy with a Chinese exit IP.

### What "CN exit node proxy" means

A proxy server physically located in China (or with a Chinese IP) that forwards
requests on behalf of Anveshak:

```
Anveshak (India) → Proxy Server (China) → weibo.com
                                          ↑
                              weibo sees a Chinese IP
                              serves full content
```

**SOCKS5** and **HTTP** are the two common proxy protocols:
- SOCKS5 — lower level, works with any TCP traffic
- HTTP proxy — works at HTTP level

Both are configured as a URL: `socks5://1.2.3.4:1080` or `http://1.2.3.4:8080`.

### Proxy Sourcing Options

| Option | What it is | Cost | Reliability |
|--------|-----------|------|-------------|
| Residential proxy provider | Companies like BrightData, Oxylabs, SmartProxy sell access to rotating Chinese residential IPs | ~$10-15/GB | High — looks like real Chinese users |
| Datacenter proxy | Cheaper servers in Chinese datacenters | ~$2-5/GB | Medium — some sites block datacenter IPs |
| VPS in China | Rent a server from Alibaba Cloud / Tencent Cloud, run your own SOCKS5 proxy (e.g., `dante`, `3proxy`) | ~$5-20/month | High — you control it, but single IP |
| Embassy/liaison asset | A machine physically in China on a trusted network | Operational cost | Highest — sovereign control |

**Minimum starting point:** A self-hosted VPS on Alibaba Cloud running `dante`
(~$5/month). For production, 2-3 proxies for rotation and redundancy.

## Risks

| Risk | Level | Mitigation |
|------|-------|------------|
| CN residential proxy procurement | HIGH | IAF must source SOCKS5/HTTP proxies with CN exit nodes. Design is provider-agnostic — any proxy URL works |
| Anti-bot detection on Weibo/Douyin | HIGH | Crawl4AI stealth mode + CN headers + rate limiting. Some platforms may remain inaccessible without API keys |
| Proxy latency increases timeouts | MEDIUM | Separate `PROXY_CN_TIMEOUT_S` env var for CN-routed requests |
| Proxy cost | LOW | Only CN-domain-matched traffic goes through paid proxies; everything else stays direct |
| WeChat access | HIGH | Requires Chinese phone + API registration. Out of scope — document as future capability |

## Implementation Plan — 4 Phases

### Phase 1: Proxy Routing Infrastructure (Core)

**1a. New settings** — `services/scraper/anveshak/scraper/settings.py`

New env vars:
```
PROXY_ROUTES=cn:socks5://cn-proxy-1:1080,socks5://cn-proxy-2:1080;tor:socks5://tor:9050
PROXY_CN_DOMAINS=weibo.com,weibo.cn,baidu.com,sina.com.cn,xinhuanet.com,people.com.cn,cctv.com,bilibili.com,zhihu.com,douyin.com,sohu.com,qq.com,163.com,81.cn
PROXY_CN_TIMEOUT_S=60
PROXY_ROTATION_STRATEGY=round_robin
```

Backward compat: if only `TOR_PROXY_URL` is set and no `PROXY_ROUTES`, behavior
is identical to today.

**1b. New module** — `services/scraper/anveshak/scraper/proxy.py`

- `ProxyPool`: holds proxy URLs per group, round-robin rotation, per-proxy
  success/failure tracking
- `ProxyRouter`: given a URL, matches domain against patterns and returns the
  appropriate `ProxyPool` (or None for direct access)
- Circuit breaker: 3 consecutive failures = skip proxy for 5 minutes
- `report_success()` / `report_failure()` called after each fetch

**1c. Modify fetch.py** — `services/scraper/anveshak/scraper/fetch.py`

- `fetch_url(url, proxy_url=None)` — proxy_url parameter overrides global setting
- New `fetch_url_with_routing(url, proxy_router)` — resolves proxy, tries pool,
  falls back to direct
- Apply CN-specific headers when routing through `cn` group:
  ```python
  _CN_HEADERS = {
      "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
      "Accept-Encoding": "gzip, deflate, br",
  }
  ```

**1d. Wire into jobs** — `services/scraper/anveshak/scraper/jobs.py`

- Initialize `ProxyRouter` in ARQ `on_startup`, store in `ctx["proxy_router"]`
- Replace `fetch_url(url)` calls with `fetch_url_with_routing(url, proxy_router)`

**1e. Metrics** — `services/scraper/anveshak/scraper/metrics.py`

- `scraper_proxy_requests_total` (proxy_group, result)
- `scraper_proxy_pool_healthy_total` (proxy_group) gauge

### Phase 2: Health Check + DB Integration

**2a. Migration** — `007_source_geo_zone.py`

```sql
ALTER TABLE sources ADD COLUMN geo_zone TEXT;
CREATE INDEX idx_sources_geo_zone ON sources(geo_zone) WHERE geo_zone IS NOT NULL;
```

`geo_zone` values: `cn`, `ru`, `ir`, etc. Nullable. Metadata for operators —
proxy routing uses domain matching, not this column.

**2b. Health checks** — `services/scraper/anveshak/scraper/health.py`

- Route CN-domain health checks through proxy pool
- Add Chinese-specific block patterns (WeChat redirect, mobile-app-only, CN login walls)

**2c. API routes** — `services/api/anveshak/api/routes/sources.py` + `db/sources.py`

- Add `geo_zone` to create/list source endpoints
- Auto-detect geo_zone from domain on source creation

### Phase 3: Weibo Social Adapter

**3a. New adapter** — `services/social/anveshak/social/adapters/weibo.py`

- Uses Weibo mobile API endpoints (less restricted than desktop)
- Routes through CN proxy pool
- Chinese text flows through existing NLLB translation pipeline
- Implements `SourceAdapterBase` contract

**3b. Social settings** — add `WEIBO_ADAPTER_ENABLED`, `SOCIAL_PROXY_ROUTES`

### Phase 4: Extract Shared Proxy SDK

Move `ProxyPool` + `ProxyRouter` to `sdk/anveshak/proxy.py` so both scraper and
social services can reuse it.

## Files Modified/Created

| File | Action | Phase |
|------|--------|-------|
| `services/scraper/anveshak/scraper/settings.py` | Modify — add proxy settings | 1 |
| `services/scraper/anveshak/scraper/proxy.py` | **Create** — ProxyPool, ProxyRouter | 1 |
| `services/scraper/anveshak/scraper/fetch.py` | Modify — proxy param, CN headers, fallback chain | 1 |
| `services/scraper/anveshak/scraper/jobs.py` | Modify — wire proxy_router | 1 |
| `services/scraper/anveshak/scraper/metrics.py` | Modify — proxy metrics | 1 |
| `.env.example` | Modify — document proxy env vars | 1 |
| `migrations/.../007_source_geo_zone.py` | **Create** — add geo_zone column | 2 |
| `services/scraper/anveshak/scraper/health.py` | Modify — proxy-aware CN health checks | 2 |
| `services/api/anveshak/api/routes/sources.py` | Modify — geo_zone support | 2 |
| `services/api/anveshak/api/db/sources.py` | Modify — geo_zone in SQL | 2 |
| `services/social/anveshak/social/adapters/weibo.py` | **Create** — Weibo adapter | 3 |
| `sdk/anveshak/proxy.py` | **Create** — shared proxy lib | 4 |

## Testing Strategy

- **Unit tests**: Proxy pool rotation, domain matching, circuit breaker, CN header
  injection, backward compat with `TOR_PROXY_URL` alone
- **Integration tests**: Mock httpx transports simulating CN-blocked then
  proxy-success scenarios
- **Manual test**: Add a Chinese source (e.g., xinhuanet.com), verify it routes
  through configured proxy, content deduplicates, and flows through NLLB translation
- **Health check test**: Verify CN sources show correct health status when checked
  via proxy
