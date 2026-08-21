---
name: Source consolidation can silently break downstream metrics
description: Moving sources from one platform to another (web→RSS) changes platform distribution which can break any metric counting distinct platforms
type: pitfall
confidence: high
---

## Problem

When consolidating duplicate sources (e.g. NDTV web + NDTV RSS → single NDTV RSS), the platform distribution changes. Any downstream metric that counts distinct platforms is silently affected:

- ISC (independent_source_count) — collapsed from ISC=2 to ISC=1
- Signal engine — stopped firing signals that required ISC ≥ 2
- Credibility cross-verification — boost logic checked for "multi-platform clusters"

The consolidation itself was correct (eliminating homepage garbage), but the downstream breakage was invisible — no error, no log, no test failure.

## Prevention checklist

Before any source platform change (web→rss, consolidating duplicates, removing sources):

1. **Check what counts distinct platforms** — grep for `DISTINCT.*platform`, `set(platforms)`, `independent_source_count`
2. **Simulate the ISC impact** — query: `SELECT topic, COUNT(DISTINCT platform) FROM content_items GROUP BY topic` before and after
3. **Verify signal engine still fires** — if max ISC drops below signal_threshold, signals stop silently
4. **Consider whether the metric SHOULD count platforms or sources** — the answer is almost always sources (see `isc-count-sources-not-platforms.md`)

## Broader lesson

Any "cleanup" operation that changes data distribution can break metrics downstream. The fix may be correct in isolation but wrong in context. Always trace the impact chain:

```
Source change → platform distribution → ISC calculation → signal threshold → signal engine → analyst alerts
```

If any link in this chain is platform-dependent, the cleanup breaks it.
