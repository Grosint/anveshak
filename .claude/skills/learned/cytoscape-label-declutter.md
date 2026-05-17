---
name: cytoscape-label-declutter
description: Cytoscape graph label overlap fixes — hide low-priority labels, clean URLs, tune layout spacing
type: pattern
---

# Cytoscape Graph Label Declutter

## Problem
Signal connection graph with 20+ nodes has overlapping labels.
Source nodes show raw URLs (`https://reddit.com/r/Kerala`).
Content node labels truncate mid-word.

## Solution

### 1. Clean labels before rendering
```typescript
if (node.type === 'source') {
  label = label.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')
  const rMatch = label.match(/reddit\.com\/r\/(\w+)/)
  if (rMatch) label = `r/${rMatch[1]}`
  const tMatch = label.match(/t\.me\/(.+)/)
  if (tMatch) label = `@${tMatch[1]}`
}
if (label.length > 40) {
  label = label.slice(0, 38).replace(/\s\S*$/, '') + '…'  // word boundary
}
```

### 2. Hide low-priority labels by default
```javascript
{ selector: 'node[nodeType="content"]', style: { 'text-opacity': 0 } }
{ selector: 'node[nodeType="content"].highlighted-node', style: { 'text-opacity': 1 } }
```
Show on hover/click via JS: `e.target.style('text-opacity', 1)`

### 3. Tune layout spacing
```javascript
layout: {
  name: 'cose',
  nodeRepulsion: () => 14000,     // was 8000 — push nodes apart
  idealEdgeLength: () => 160,     // was 120 — longer edges
  gravity: 0.25,                  // was 0.4 — less pull to center
  nodeDimensionsIncludeLabels: true,  // account for label size in layout
}
```

## Key numbers
- `nodeRepulsion`: 8000 (crowded) → 14000 (readable)
- `idealEdgeLength`: 120 (tight) → 160 (spacious)
- `gravity`: 0.4 (dense center) → 0.25 (spread out)
- Content node size: 28→24px (less visual weight when labels hidden)
