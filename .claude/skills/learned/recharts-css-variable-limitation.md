# Recharts Cannot Use CSS Variables for Colors

## Problem
Recharts `fill`, `stroke`, and color props are passed directly to SVG attributes.
SVG attributes in Recharts don't resolve CSS `var(--...)` custom properties —
the chart renders with no color (transparent).

## What fails
```tsx
// WRONG — renders invisible
<Bar dataKey="count" fill="var(--anveshak-accent)" />
<Cell fill="var(--credibility-high)" />
```

## What works
```tsx
// CORRECT — hardcoded hex values
const ACCENT_COLOR = '#3b82f6'
const HEALTH_COLORS: Record<string, string> = {
  healthy: '#10b981',   // mirrors --credibility-high
  degraded: '#f59e0b',
  down: '#ef4444',      // mirrors --signal-high
  unverified: '#6b7280',
}

<Bar dataKey="count" fill={ACCENT_COLOR} />
```

## Mitigation
- Keep hardcoded hex values in a const object at the top of the file
- Add a comment noting which CSS variable each color mirrors
- If the theme changes, these constants must be updated manually
- Tooltip backgrounds can use Tailwind classes (`className="bg-[#0f172a]"`)
  since those are rendered as HTML, not SVG attributes

## Applies to
All Recharts components: PieChart, BarChart, LineChart, Cell, Area, etc.
Also applies to Cytoscape.js stylesheet colors (SignalGraph).
