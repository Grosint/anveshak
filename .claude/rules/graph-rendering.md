# Graph & Visualization Rendering

4 instincts. Cytoscape, MapLibre, data visualization.

## Render Guard: OR Not AND

Multiple independent data sources → trigger render when ANY has data, not ALL.

```typescript
// BAD — requires both sources
if (details.length > 0) initGraph()

// GOOD — renders when either has data
const hasData = details.length > 0 || (entityGraph?.nodes?.length ?? 0) > 0
if (hasData) initGraph()
```

Empty state = inverse: "no data" only when ALL sources empty.
See: `learned/graph-render-guard-or-condition.md`

## Label Declutter

Raw data labels noisy. Clean before display:
- Normalize URLs (strip protocol, truncate path)
- Truncate long labels at word boundaries w/ ellipsis
- Hide low-priority labels default, show on hover/click
- Edge labels: short format (`4x` not `co-occurs 4 times`)
See: `learned/cytoscape-label-declutter.md`

## Social Media URLs → Handles

Social URL domains (t.me, instagram.com, twitter.com) useless as graph entities — every message links same domain, creates hub nodes.
Extract username/handle from path:
- `https://t.me/username` → TELEGRAM_HANDLE `username`
- Skip noise paths: `share`, `joinchat`, `addstickers`, `s`
See: `learned/telegram-url-to-handle.md`

## Nullable FK Fallback Queries

Graph query w/ nullable FK (content may/may not belong to cluster) → provide fallback query paths. Never assume FK populated.
Use LEFT JOIN or UNION to cover both paths.
See: `learned/fallback-null-fk-query.md`