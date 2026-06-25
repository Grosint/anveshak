# Frontend Patterns

10 instincts. React + TypeScript analyst workbench.

## Theming

- Dark-first: colors as CSS custom properties on `:root`, light mode via `html.light` class
  Tailwind reads via `var(--...)`. ThemeProvider context w/ localStorage persistence.
  Never Tailwind `dark:` prefixes — CSS variable swapping instead
  See: `learned/css-variable-theming.md`

- Recharts `fill`/`stroke` props don't resolve CSS `var(--...)` — hardcode hex in const object w/ comments noting which CSS variable each mirrors
  See: `learned/recharts-css-variable-limitation.md`

## Auth Lifecycle

- JWT expiry countdown: 1s timer warns 5min before expiry
  Decode JWT without libraries, auto-logout at expiry, rollback pending mutations
  Toast inside AuthProvider for persistent visibility
  Validate on load — reject expired tokens immediately
  See: `learned/jwt-expiry-countdown.md`

## Data Mutations

- Optimistic UI: cancel in-flight queries, snapshot state, apply immediately, restore on error, refetch on settled
  Guard buttons w/ `isPending` — prevent double-submit
  Covers remove ops (dismiss/delete) and field updates (acknowledge)
  See: `learned/optimistic-ui-mutations.md`

## Performance

- Lazy-load >100KB libs behind tabs/modals w/ `React.lazy()` + `Suspense`
  MapLibre, charts, PDF renderers — fetched on navigate only
  Gate React Query `enabled` to prevent premature API calls
  See: `learned/react-lazy-heavy-chunks.md`

## Pagination & Filtering

- Infinite scroll: `useInfiniteQuery` + `IntersectionObserver` w/ `threshold: 0.1`
  Client-side filtering after fetch — `queryKey` excludes filters to avoid refetch storms
  Server-side filtering for large datasets or low cardinality
  See: `learned/react-infinite-scroll-hook.md`

- Time filtering: preset chips (Today/7d/30d) + custom date range
  Always `T00:00:00Z`/`T23:59:59Z` suffix when converting `YYYY-MM-DD`
  Derived UTC ISO strings in React Query key for per-range caching
  Prefix match for WebSocket invalidation, full key for optimistic mutations
  See: `learned/time-filter-bar-pattern.md`

## Component Reuse

- Embedded prop: `embedded?: boolean` (default `false`) on page components rendering inside another page. When embedded, skip page header/h1; parent provides own. Content identical.
  See: `learned/embedded-prop-page-reuse.md`

- Kill standalone route for topic-scoped pages needing UUID. Keep embedded tab in TopicWorkspace, add global action (search button, command palette) in Layout sidebar. No topic picker dropdown.
  See: `learned/kill-standalone-add-global-action.md`

## Cross-Page Modal Communication

- URL-param modal trigger: open Layout-level modal from child page via `?search=X` query param. Layout reads param, opens modal prefilled, clears w/ `{ replace: true }`. Modal needs `initialQuery` prop.
  See: `learned/url-param-modal-trigger.md`

## Domain Logic Extraction

- Extract business logic (severity, credibility labels, confidence variants) into pure functions in `lib/domain.ts` — testable without React
  Components thin: render + call domain functions, never inline business rules
  See: `learned/frontend-domain-logic-extraction.md`

## Seam Testing

- Test React Query cache boundaries: `queryKey` prefix matching for WebSocket invalidation, full key for optimistic mutations, `enabled` gate conditions
  Mock API factories return unwrapped shape matching `.then(r => r.data)`
  Test both desktop sidebar and mobile bottom nav (jsdom sees both)
  See: `learned/frontend-seam-testing.md`

## Testing

- jsdom renders both desktop sidebar and mobile bottom nav (no CSS media queries).
  Use `getAllByRole` not `getByRole` for nav links — handles duplicates.
  See: `learned/jsdom-dual-nav-testing.md`

- `vi.useFakeTimers()` + React Query: queries fire on mount, use `vi.advanceTimersByTime` to settle. Never mix real and fake timers in same test.
  See: `learned/fake-timers-react-query-trap.md`