# React Patterns

## When to load: any task involving React components, React Query, or frontend UI

Consolidated from 5 learned instincts.

---

### Time filter bar

Preset chips (24h, 7d, 30d) + custom date range. Derive ISO strings from presets
at query time — don't store start/end dates for presets.

See: `learned/time-filter-bar-pattern.md`

### JWT expiry countdown

Poll `exp` claim every 30s. Show warning banner at 5 minutes remaining with
countdown. Auto-redirect to login at 0.

See: `learned/jwt-expiry-countdown.md`

### Lazy loading heavy chunks

Any import > 100KB (MapLibre, PDF viewer, chart libs) goes behind `React.lazy()`
with a Suspense boundary. Split by route or tab — never load everything upfront.

See: `learned/react-lazy-heavy-chunks.md`

### Infinite scroll

`useInfiniteQuery` + `IntersectionObserver` on a sentinel div. Apply client-side
filters (search, status) on the accumulated pages. Reset pages on filter change.

See: `learned/react-infinite-scroll-hook.md`

### Optimistic mutations

```
1. Cancel in-flight queries (queryClient.cancelQueries)
2. Snapshot previous data (queryClient.getQueryData)
3. Optimistically update cache (queryClient.setQueryData)
4. onError: restore snapshot
5. onSettled: invalidate to refetch truth from server
```

See: `learned/optimistic-ui-mutations.md`
