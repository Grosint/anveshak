# Frontend Patterns

Consolidated from 6 learned instincts. These apply to the React + TypeScript analyst workbench.

## Theming

- Dark-first: all colors as CSS custom properties on `:root`, light mode via `html.light` class
  Tailwind reads values via `var(--...)`. ThemeProvider context with localStorage persistence.
  Never use Tailwind `dark:` prefixes — use CSS variable swapping instead
  See: `learned/css-variable-theming.md`

- Recharts `fill`/`stroke` props don't resolve CSS `var(--...)` — hardcode hex values in a
  const object with comments noting which CSS variable each mirrors
  See: `learned/recharts-css-variable-limitation.md`

## Auth Lifecycle

- JWT expiry countdown: 1-second timer warns analysts 5 minutes before token expiry
  Decode JWT without libraries, auto-logout at expiry, rollback pending mutations
  Toast warning rendered inside AuthProvider for persistent visibility
  Validate on initial load — reject already-expired tokens immediately
  See: `learned/jwt-expiry-countdown.md`

## Data Mutations

- Optimistic UI: cancel in-flight queries, snapshot current state, apply update immediately,
  restore snapshot on error, always refetch on settled
  Guard buttons with `isPending` to prevent double-submit
  Covers both remove operations (dismiss/delete) and field updates (acknowledge)
  See: `learned/optimistic-ui-mutations.md`

## Performance

- Lazy-load libraries >100KB gzipped behind tabs/modals with `React.lazy()` + `Suspense`
  MapLibre, chart libraries, PDF renderers — only fetched when user navigates to them
  Gate React Query `enabled` conditions to prevent premature API calls
  See: `learned/react-lazy-heavy-chunks.md`

## Pagination & Filtering

- Infinite scroll: `useInfiniteQuery` + `IntersectionObserver` with `threshold: 0.1`
  Client-side filtering applied after fetch — `queryKey` excludes filters to avoid refetch storms
  Use server-side filtering instead for large datasets or low cardinality filters
  See: `learned/react-infinite-scroll-hook.md`

- Time filtering: preset chips (Today/7d/30d) + custom date range inputs
  Always use `T00:00:00Z`/`T23:59:59Z` suffix when converting `YYYY-MM-DD`
  Include derived UTC ISO strings in React Query key for per-range caching
  Use prefix match for WebSocket invalidation, full key for optimistic mutations
  See: `learned/time-filter-bar-pattern.md`

## Component Reuse

- Embedded prop pattern: add `embedded?: boolean` (default `false`) to page components
  that need to render inside another page (e.g. Settings tabs). When embedded, skip the
  page-level header/h1; parent provides its own. Functional content stays identical.
  See: `learned/embedded-prop-page-reuse.md`

## Testing

- jsdom renders both desktop sidebar and mobile bottom nav (no CSS media queries).
  Use `getAllByRole` not `getByRole` for nav link assertions to handle duplicates.
  See: `learned/jsdom-dual-nav-testing.md`
