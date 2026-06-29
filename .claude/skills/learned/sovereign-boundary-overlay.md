# Sovereign Boundary Overlay — GeoJSON over Third-Party Tiles

## When to load: any map rendering where political boundaries must match a specific country's official view

---

## The Problem

Third-party map tile providers (CartoDB, OpenStreetMap, MapTiler) render international
boundaries per UN standards or their own editorial policy. For defence/government products,
this creates boundary discrepancies (e.g., PoJK shown as Pakistan, Aksai Chin as China).

Tile boundaries are baked into vector/raster tiles — cannot be modified client-side.

## The Solution

GeoJSON polygon overlay rendered ABOVE base tiles but BELOW data point layers:

1. **Territory fill** — polygon matching the official boundary, filled with the
   tile provider's exact land color at 100% opacity. Masks incorrect base tile borders.
2. **Boundary line** — correct international boundary as a line layer.
3. **Disputed/LAC line** — dashed line for lines of actual control.

### Key implementation details

- **Color must exactly match base tiles.** CartoDB dark-matter land = `#0e0e0e`.
  Wrong color (even close like `#1a1a2e`) creates a visible tinted overlay.
  Fetch the style.json to extract exact paint values.

- **Opacity must be 1.0** for territory fill — partial opacity lets incorrect
  borders bleed through.

- **Layer z-order critical:** territory-fill → boundary-line → lac-line → clusters → points.
  MapLibre renders in addLayer() order.

- **Module-level cache** for the GeoJSON fetch — file loaded once, reused across re-renders.

- **Graceful degradation** — try/catch around fetch + addLayer. Map works without overlay,
  just shows incorrect borders.

- **Static asset in public/** — ships inside Docker image, works air-gapped.
  No runtime external fetch needed.

### GeoJSON sourcing

- datameet/maps (github.com/datameet/maps) — CC-0, Survey of India standard
- Simplify with mapshaper: `mapshaper input.geojson -simplify dp 0.005 keep-shapes -o output.geojson`
- 10MB raw → 50-100KB simplified. Verify key boundary points survive simplification.

### Verification checklist

For India: check coordinates exist for PoJK (73-77°E, 33-37°N), Aksai Chin (78-81°E, 34-35°N),
Arunachal Pradesh (93-97°E, 26-29°N), Siachen/Karakoram (76-78°E, 35°N+).

## Files

- `frontend/public/geo/india-sovereign-boundary.geojson` — boundary data
- `frontend/src/components/map/GeoMap.tsx` — overlay layers (lines 40-50, 126-170)
