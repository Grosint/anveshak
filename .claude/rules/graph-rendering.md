# Graph & Visualization Rendering

Consolidated from 4 learned instincts. These apply to Cytoscape, MapLibre, and any data visualization.

## Render Guard: OR Not AND

When a visualization combines multiple independent data sources (identifier clusters + entity graph),
trigger rendering when ANY source has data, not when ALL have data.

```typescript
// BAD — requires both sources
if (details.length > 0) initGraph()

// GOOD — renders when either has data
const hasData = details.length > 0 || (entityGraph?.nodes?.length ?? 0) > 0
if (hasData) initGraph()
```

Empty state should be the logical inverse: show "no data" only when ALL sources are empty.
See: `learned/graph-render-guard-or-condition.md`

## Label Declutter

Graph labels from raw data are noisy. Clean before display:
- Normalize URLs (strip protocol, truncate path)
- Truncate long labels at word boundaries with ellipsis
- Hide low-priority labels by default, show on hover/click
- Edge labels: use short format (`4x` not `co-occurs 4 times`)
See: `learned/cytoscape-label-declutter.md`

## Social Media URLs → Handles

Social media URL domains (t.me, instagram.com, twitter.com) are not useful as
graph entities — they appear in every message and create giant hub nodes.
Extract the username/handle from the path instead:
- `https://t.me/username` → TELEGRAM_HANDLE `username`
- Skip noise paths: `share`, `joinchat`, `addstickers`, `s`
See: `learned/telegram-url-to-handle.md`

## Nullable FK Fallback Queries

When a graph query uses a nullable FK (e.g., content can belong to a cluster
or not), provide fallback query paths. Don't assume the FK is always populated.
Use LEFT JOIN or UNION to cover both paths.
See: `learned/fallback-null-fk-query.md`
