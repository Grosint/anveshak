# Graph Render Guard Must Use OR, Not AND

## Pattern
When a visualization component combines multiple independent data sources
(e.g., identifier clusters + entity co-occurrence graph), the render guard
must trigger when ANY source has data, not when ALL have data.

## Context
`EntityGraph.tsx` had:
```typescript
if (!isLoading && details.length > 0) initGraph()
```

This required identifier clusters to exist. After deleting the noisy `t.me`
identifier cluster, no clusters remained → graph showed empty screen, even
though 402 entity co-occurrence edges existed.

## Fix
```typescript
const hasData = details.length > 0 || (entityGraph?.nodes?.length ?? 0) > 0
if (!isLoading && hasData) initGraph()
```

## Rule
When combining independent data sources in a single visualization:
- Render guard: `source1.length > 0 || source2.length > 0` (OR)
- Empty state: `source1.length === 0 && source2.length === 0` (AND)

The render guard and empty state should be logical inverses.
