# Frontend Seam Testing (A→Cache→B Pattern)

## Problem
The backend had a critical bug where System A wrote to a table and System B
read from a different column — both had 100% unit test coverage but the seam
was untested. The frontend has the same structural risk with different
"shared state" layers:

- React Query cache (query key mismatch between producer and consumer)
- Context providers (AuthContext writes, multiple consumers read)
- localStorage (API interceptor writes, AuthContext reads on mount)
- WebSocket messages (WSContext dispatches, SignalsInbox subscribes)

## 12 Frontend Seams Identified
1. WS message → `invalidateQueries(['signals'])` → SignalsInbox (prefix key match)
2. Optimistic mutation → cache key with `[status, since, until]` → rollback
3. Login → AuthContext → localStorage → API client Bearer header
4. 401 interceptor → localStorage clear → hard redirect → AuthContext remount
5. Create topic → `invalidateQueries(['topics'])` → list refetch
6. Infinite scroll → client-side filter → display (double-filter risk)
7. `useQueries` by array index → warning counts (re-order risk, R10)
8. Report generate → poll `generation_status` (computed field, not in Pydantic)
9. Source delete 409 → regex parse error message (format coupling, R9)
10. Backend Pydantic → Frontend TypeScript (field mismatch)
11. Auth expiry → WSContext disconnect → reconnect with stale token
12. URL params → topic-scoped queries (stale fetch during transition)

## Testing Pattern
For each seam:
1. Render the full producer→consumer chain (not mocked in between)
2. Mock only the external boundary (API responses)
3. Verify data flows through the shared state layer correctly
4. Test the failure mode (what happens when the seam breaks?)

## Key Insight
React Query's `invalidateQueries({ queryKey: ['signals'] })` uses **prefix
matching** — it invalidates `['signals', 'new', since, until]` too. This is
correct but non-obvious. A seam test verifies this actually works.

## File Organization
```
src/test/
  unit/          ← pure logic (no React)
  component/     ← single component with real context
  integration/   ← A→cache→B seam tests
  contracts/     ← shape verification (factory matches interface)
```
