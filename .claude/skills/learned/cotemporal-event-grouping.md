# Co-Temporal Event Grouping on Timelines

## Problem
Batch-created events (scheduler cycle, seed script) share identical
timestamps. Timeline visualization stacks dots on same pixel — user
sees 1 dot instead of 8.

## Fix
Group events within proximity threshold before rendering:
```typescript
const grouped: { items: T[]; pct: number }[] = []
for (const dot of sorted) {
  const last = grouped[grouped.length - 1]
  if (last && Math.abs(last.pct - dot.pct) < 1.5) {
    last.items.push(dot.item)
  } else {
    grouped.push({ items: [dot.item], pct: dot.pct })
  }
}
```

Render grouped dot with:
- Larger size proportional to count
- Count badge inside dot
- Tooltip: "N events"
- Click expands ALL items in group (not just first)

## Gotcha
First implementation only expanded first item on click. Must pass
array of IDs, not single ID, when selecting a group.
