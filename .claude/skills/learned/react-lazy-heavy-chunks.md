# Pattern: Lazy-Loading Heavy Third-Party Chunks (React + Vite)

## When to load: adding any component that wraps a large library (maps, chart, PDF viewer, 3D, etc.)

---

## The pattern

Use `React.lazy()` + `Suspense` to split heavy libraries into separate chunks that only
download when the user actually opens the relevant tab/panel.

```tsx
// WRONG — MapLibre (803KB) lands in the initial bundle for every page load
import GeoMap from '../components/map/GeoMap'

// CORRECT — splits into its own chunk, only fetched when GIS tab opens
const GeoMap = lazy(() => import('../components/map/GeoMap'))

// Usage: wrap with Suspense wherever the lazy component renders
{activeTab === 'gis' && (
  <Suspense fallback={<Spinner label="Loading map…" />}>
    <GeoMap geojson={geojson ?? { type: 'FeatureCollection', features: [] }} />
  </Suspense>
)}
```

## What qualifies as "heavy"

| Library | Size (gzipped) | Lazy? |
|---------|----------------|-------|
| MapLibre GL | ~250KB gz / 803KB raw | Yes |
| react-pdf | ~300KB+ | Yes |
| cytoscape | ~200KB | Yes — only for graph view |
| recharts | ~100KB | Borderline — keep eager if charts are on every page |
| react-markdown | ~20KB | No — cheap enough to keep eager |
| date-fns | ~30KB | No |

Rule of thumb: lazy-load anything >100KB gzipped that's behind a tab/modal/feature flag.

## Vite build output tells you when you've done it right

```
dist/assets/GeoMap-Bx7k2Qmq.js   803.21 kB │ gzip: 249.43 kB
dist/assets/index-ChKZpDXf.js     187.43 kB │ gzip:  61.23 kB
```

The GeoMap chunk is separate. Initial `index.js` stays small.

## Gate the fetch with a condition

Always gate lazy component render behind the condition that would cause the user to need it:

```tsx
// Only fetch geojson when tab is open AND report is done
const { data: geojson } = useQuery({
  queryKey: ['report-geojson', reportId],
  queryFn: () => reportsApi.getGeojson(reportId!),
  enabled: !!reportId && report?.generation_status === 'complete' && activeTab === 'gis',
  staleTime: Infinity,  // geojson is immutable once generated
})
```

This prevents the API call AND the JS download until the user actually clicks the tab.

## MapLibre-specific gotcha

`attributionControl` takes an object, not a boolean:

```tsx
// WRONG — TypeScript error
<Map attributionControl={true} />

// CORRECT
<Map attributionControl={{ compact: true }} />
```

## GeoMap component structure

```tsx
// components/map/GeoMap.tsx
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef } from 'react'

export default function GeoMap({ geojson }: { geojson: GeoJSON.FeatureCollection }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://demotiles.maplibre.org/style.json',  // or self-hosted tiles
      center: [78.9629, 20.5937],  // India centroid for IAF context
      zoom: 4,
      attributionControl: { compact: true },
    })
    // Add GeoJSON source + layer + click popup...
    mapRef.current = map
    return () => { map.remove(); mapRef.current = null }
  }, [])

  // Sync data changes after mount
  useEffect(() => {
    if (!mapRef.current) return
    const source = mapRef.current.getSource('geojson') as maplibregl.GeoJSONSource
    source?.setData(geojson)
  }, [geojson])

  return <div ref={containerRef} className="w-full h-96 rounded border border-anveshak-border" />
}
```
