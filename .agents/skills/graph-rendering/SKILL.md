---
name: graph-rendering
description: "Cytoscape graph and MapLibre map rendering. Covers sovereign boundary overlay for Indian borders, render guards across multiple data sources, label declutter, social-URL handle nodes, and nullable-FK fallback queries. Use when editing graph visualisation, map layers, Cytoscape layouts, or MapLibre styles."
---

# Graph & Visualization Rendering

5 instincts. Cytoscape, MapLibre, data visualization.

## Sovereign Boundary Overlay

Third-party tiles (CartoDB, OSM) show borders per UN standards — wrong for defence products.
Fix: GeoJSON polygon overlay filled with exact tile land color (`#0e0e0e` for dark-matter) at 100% opacity.
Layers: territory-fill → boundary-line → lac-line, all BELOW data point layers.
Module-level cache for fetch. Graceful degradation via try/catch.
Source boundary from datameet/maps (CC-0). Simplify with mapshaper to <100KB.
See: `.agents/skills/learned/references/sovereign-boundary-overlay.md`

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
See: `.agents/skills/learned/references/graph-render-guard-or-condition.md`

## Label Declutter

Raw data labels noisy. Clean before display:
- Normalize URLs (strip protocol, truncate path)
- Truncate long labels at word boundaries w/ ellipsis
- Hide low-priority labels default, show on hover/click
- Edge labels: short format (`4x` not `co-occurs 4 times`)
See: `.agents/skills/learned/references/cytoscape-label-declutter.md`

## Social Media URLs → Handles

Social URL domains (t.me, instagram.com, twitter.com) useless as graph entities — every message links same domain, creates hub nodes.
Extract username/handle from path:
- `https://t.me/username` → TELEGRAM_HANDLE `username`
- Skip noise paths: `share`, `joinchat`, `addstickers`, `s`
See: `.agents/skills/learned/references/telegram-url-to-handle.md`

## Nullable FK Fallback Queries

Graph query w/ nullable FK (content may/may not belong to cluster) → provide fallback query paths. Never assume FK populated.
Use LEFT JOIN or UNION to cover both paths.
See: `.agents/skills/learned/references/fallback-null-fk-query.md`