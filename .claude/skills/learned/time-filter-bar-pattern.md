---
name: time-filter-bar-pattern
description: Preset chip + custom date range filter pattern for React Query pages — state, derived ISO strings, conditional picker UI
type: feedback
---

# Time Filter Bar Pattern (Preset Chips + Custom Range)

## When to load: adding date/time filtering to any list or inbox page

---

## Pattern

Three presets (Today / Last N days) + a Custom mode with From/To date inputs. Derive UTC ISO strings from state; include them in the React Query key so the cache is keyed per time range.

### State shape

```typescript
type TimePreset = 'today' | '7d' | '30d' | 'custom'

const [preset, setPreset]         = useState<TimePreset>('today')
const [customFrom, setCustomFrom] = useState('')          // YYYY-MM-DD
const [customTo, setCustomTo]     = useState(() => toISODate(new Date()))
```

### Derive `since`/`until` — memoised

```typescript
const { since, until } = useMemo(
  () => resolveRange(preset, customFrom, customTo),
  [preset, customFrom, customTo],
)

function resolveRange(preset, customFrom, customTo): { since: string; until: string } {
  const now = new Date()
  const until = now.toISOString()

  if (preset === 'today') {
    const d = new Date(now); d.setUTCHours(0, 0, 0, 0)
    return { since: d.toISOString(), until }
  }
  if (preset === '7d') {
    const d = new Date(now); d.setUTCDate(d.getUTCDate() - 7)
    return { since: d.toISOString(), until }
  }
  if (preset === '30d') {
    const d = new Date(now); d.setUTCDate(d.getUTCDate() - 30)
    return { since: d.toISOString(), until }
  }
  // custom
  const since = customFrom ? new Date(customFrom + 'T00:00:00Z').toISOString() : ''
  const customUntil = customTo ? new Date(customTo + 'T23:59:59Z').toISOString() : until
  return { since, until: customUntil }
}
```

### React Query key — always include range

```typescript
const rangeReady = preset !== 'custom' || (customFrom !== '' && customTo !== '')

useQuery({
  queryKey: ['things', activeTab, since, until],
  queryFn: () => (rangeReady ? api.list(activeTab, since, until) : Promise.resolve([])),
  enabled: rangeReady,
  refetchInterval: 30_000,
})
```

### Invalidation — use prefix, not full key

```typescript
// WS push should invalidate ALL tab+range combinations
qc.invalidateQueries({ queryKey: ['things'] })   // prefix match — correct
// NOT: qc.invalidateQueries({ queryKey: ['things', 'new'] })  — misses other range keys
```

### Optimistic mutations — use full key

```typescript
// Optimistic update must target the exact cache key the user is looking at
qc.setQueryData<Thing[]>(['things', activeTab, since, until], (old = []) =>
  old.filter((t) => t.id !== id),
)
```

### UI — chips + conditional pickers

```tsx
{/* Preset chips */}
<div className="flex flex-wrap items-center gap-2">
  {TIME_PRESETS.map((p) => (
    <button
      key={p.key}
      onClick={() => setPreset(p.key)}
      className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
        preset === p.key
          ? 'bg-anveshak-accent text-white'
          : 'bg-anveshak-muted text-text-secondary hover:bg-anveshak-card hover:text-text-primary'
      }`}
    >
      {p.label}
    </button>
  ))}
</div>

{/* Custom pickers — only when preset === 'custom' */}
{preset === 'custom' && (
  <div className="flex flex-wrap items-center gap-3 mt-2.5">
    <label className="flex items-center gap-1.5 text-xs text-text-muted">
      From
      <input type="date" value={customFrom} max={customTo || toISODate(new Date())}
        onChange={(e) => setCustomFrom(e.target.value)}
        className="ml-1 px-2 py-1 rounded bg-anveshak-card border border-anveshak-border
                   text-text-primary text-xs focus:outline-none focus:border-anveshak-accent"
      />
    </label>
    <label className="flex items-center gap-1.5 text-xs text-text-muted">
      To
      <input type="date" value={customTo} min={customFrom || undefined}
        max={toISODate(new Date())}
        onChange={(e) => setCustomTo(e.target.value)}
        className="ml-1 px-2 py-1 rounded bg-anveshak-card border border-anveshak-border
                   text-text-primary text-xs focus:outline-none focus:border-anveshak-accent"
      />
    </label>
    {!rangeReady && (
      <span className="text-xs text-text-muted italic">Select a start date to apply filter</span>
    )}
  </div>
)}
```

---

## Backend counterpart

```python
@router.get("")
async def list_things(
    status: str = Query(...),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if since is not None or until is not None:
        _since = since or datetime.min.replace(tzinfo=UTC)
        _until = until or datetime.now(UTC)
        return await db_module.list_filtered(db, status, _since, _until)
    return await db_module.list_all(db, status)
```

SQL constant — separate from the unfiltered one (different LIMIT):
```python
SQL_LIST_FILTERED = """
    SELECT ...
    FROM things t
    WHERE t.status = $1
      AND t.created_at >= $2
      AND t.created_at <= $3
    ORDER BY t.created_at DESC
    LIMIT 200    -- higher than the default 50 for unfiltered
"""
```

---

## Key rules

- Always `T00:00:00Z` / `T23:59:59Z` suffix when converting YYYY-MM-DD to ISO — avoids local-timezone drift
- `max={customTo}` on From input and `min={customFrom}` on To input — browser validates range validity
- Disable query (`enabled: rangeReady`) when custom preset is selected but dates aren't filled — prevents spurious empty-range request
- Use `<input type="date">` — zero dependency, works on mobile, consistent with macOS/iOS date pickers
