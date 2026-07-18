# MapLibre preserveDrawingBuffer for Canvas Export

## Problem

`map.getCanvas().toDataURL()` returns a blank/transparent PNG. MapLibre clears the drawing buffer after each frame by default for performance.

## Solution

Add `preserveDrawingBuffer: true` to Map init:
```typescript
new maplibregl.Map({
  container: containerRef.current,
  style: getTileStyleUrl(),
  preserveDrawingBuffer: true, // Required for toDataURL / toBlob
})
```

## Trade-off

~10% GPU overhead from keeping the buffer. Acceptable for analyst workstations.

## Also

MapLibre NavigationControl defaults to `'top-right'`. When adding custom controls (mode toggle, export buttons) at top-right, move nav to `'top-left'` to avoid overlap:
```typescript
map.addControl(new maplibregl.NavigationControl(), 'top-left')
```

## See Also
- `rules/frontend.md` (component patterns)
