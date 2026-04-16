# Frontend Patterns

## When to load: any task involving React, TypeScript, Vite, Tailwind, or the analyst workbench

> See also: `learned/css-variable-theming.md` — dark/light theme with CSS vars + html.light class toggle
> See also: `learned/react-infinite-scroll-hook.md` — IntersectionObserver + React Query useInfiniteQuery
> See also: `learned/optimistic-ui-mutations.md` — onMutate/onError rollback for list mutations
> See also: `learned/react-lazy-heavy-chunks.md` — React.lazy + Suspense for MapLibre and other heavy libs
> See also: `learned/npm-lockfile-docker-ci.md` — npm ci in Docker fails with stale lockfile; wipe node_modules + lockfile to regenerate
> See also: `learned/jwt-expiry-countdown.md` — JWT expiry countdown with 5-min warning toast
> See also: `learned/vitest-vite-setup.md` — Vitest + jsdom + tsconfig exclusion for Vite projects
> See also: `learned/phase-check-pitfalls.md` — pitfalls 12–14 (postcss CJS, missing SQL JOINs, vitest tsconfig)
> See also: `learned/time-filter-bar-pattern.md` — preset chip + custom date range filter with React Query, UTC ISO strings, conditional pickers

---

## Stack

| Layer | Library | Version |
|-------|---------|---------|
| Framework | React 18 | 18.3 |
| Language | TypeScript | 5.4 |
| Build | Vite | 5.2 |
| Styling | Tailwind CSS | 3.4 |
| Routing | react-router-dom | 6.x |
| Data fetching | @tanstack/react-query | 5.x |
| HTTP | axios | 1.7 |
| Map | maplibre-gl | 4.x (lazy-loaded) |
| Markdown | react-markdown + rehype-sanitize | 9.x + 6.x |
| Date | date-fns | 3.x |
| Tests | Vitest + jsdom + @testing-library/react | 1.6 |

---

## Architecture

```
frontend/src/
  api/           # One file per backend service; typed API functions only
  components/
    ui/          # Primitives: Button, Badge, Spinner, EmptyState, Modal
    content/     # ContentCard, ContentDetail, FilterBar, CredibilityBadge, PlatformBadge
    signals/     # SignalCard
    topics/      # CreateTopicModal
    vision/      # DropZone, DeepfakeMeter, YoloCanvas, ExifTable
    reports/     # SourceWarningsBanner
    sources/     # AddSourceModal, AuditLogTable
    map/         # GeoMap (MapLibre, lazy-loaded)
  contexts/      # AuthContext, ThemeContext, WSContext (singletons)
  hooks/         # useInfiniteContent
  pages/         # One file per route
  test/          # Vitest test files (excluded from prod tsconfig)
```

## WebSocket real-time push

The `WSContext` is a singleton. It:
1. Connects with `?token=JWT&since=lastDisconnectISO` on mount
2. On message, calls `queryClient.invalidateQueries(['signals'])` + notifies subscribers
3. Reconnects with exponential backoff (1s, 2s, 4s, 8s max)

See `learned/websocket-auth-pattern.md` for the backend WS auth pattern.

## API module convention

```ts
// api/signals.ts — all API calls in one place, typed
export const signalsApi = {
  list: (status: SignalStatus = 'new') =>
    api.get<Signal[]>('/api/v1/signals', { params: { status } }).then((r) => r.data),

  acknowledge: (signalId: string) =>
    api.patch<...>(`/api/v1/signals/${signalId}/acknowledge`).then((r) => r.data),
}
```

Never `axios.get(...)` inline in a component. Always go through the API module.

## Polling pattern for async jobs

```ts
// Poll every 5s while status === 'queued'; stop when done
useQuery({
  queryKey: ['report', reportId],
  queryFn: () => reportsApi.get(reportId!),
  enabled: !!reportId,
  refetchInterval: (query) => {
    const status = query.state.data?.generation_status
    if (!status || status === 'queued') return 5000
    return false
  },
})
```

## Theme token naming convention

| Token | Usage |
|-------|-------|
| `bg-anveshak-bg` | Page background |
| `bg-anveshak-card` | Card background |
| `border-anveshak-border` | Standard border |
| `text-anveshak-accent` | Primary brand blue (#3b82f6) |
| `text-text-primary` | Body text |
| `text-text-muted` | Secondary text |
| `bg-cred-high` / `mid` / `low` | Credibility score colours |
| `bg-signal-high` | Alert/danger red |
