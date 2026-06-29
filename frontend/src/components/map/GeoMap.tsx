/**
 * Lazy-loaded MapLibre GL map component with dark tiles, clustering,
 * hover tooltips, rich click popups, and legend overlay.
 *
 * Import via: const GeoMap = React.lazy(() => import('../components/map/GeoMap'))
 * This file is only loaded when the GIS tab is opened — saves ~700KB from initial bundle.
 */
import { useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

// MapLibre can't resolve CSS var() — hardcode hex matching theme tokens
const MAP_COLORS = {
  dotDefault: '#3b82f6',   // --anveshak-accent (blue)
  dotHigh: '#f59e0b',      // --signal-med (amber) for high-mention locations
  clusterBg: '#374151',    // --anveshak-muted
  clusterText: '#f1f5f9',  // --text-primary
  stroke: '#1a1f2e',       // --anveshak-card
  popupBg: '#1a1f2e',
  popupText: '#f1f5f9',
  popupMuted: '#94a3b8',
  selectedRing: '#f59e0b',
}

const ENTITY_TYPE_LABELS: Record<string, string> = {
  GPE: 'Country / State',
  LOC: 'Place',
  FAC: 'Facility',
}

// Dark map tiles — CartoDB dark-matter GL style
// Configurable via window.__ANVESHAK_MAP_TILE_URL__ for sovereign/air-gapped deploys
const DEFAULT_TILE_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

function getTileStyleUrl(): string {
  const w = window as any
  return w.__ANVESHAK_MAP_TILE_URL__ || DEFAULT_TILE_STYLE
}

function formatTimeAgo(iso: string | null): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

interface GeoMapProps {
  geojson: GeoJSON.FeatureCollection
  /** When set, circle radius scales by this numeric feature property. */
  sizeProperty?: string
  /** Called when a feature is clicked with its properties. */
  onFeatureClick?: (properties: Record<string, unknown>) => void
  /** Name of the currently selected feature — shows a highlight ring. */
  selectedFeature?: string | null
}

export interface GeoMapHandle {
  flyTo: (lng: number, lat: number) => void
}

const GeoMap = forwardRef<GeoMapHandle, GeoMapProps>(function GeoMap(
  { geojson, sizeProperty, onFeatureClick, selectedFeature },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const hoverPopupRef = useRef<maplibregl.Popup | null>(null)
  const clickPopupRef = useRef<maplibregl.Popup | null>(null)

  const flyTo = useCallback((lng: number, lat: number) => {
    mapRef.current?.flyTo({ center: [lng, lat], zoom: 6, duration: 800 })
  }, [])

  useImperativeHandle(ref, () => ({ flyTo }), [flyTo])

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: getTileStyleUrl(),
      center: [78, 22], // Center on India
      zoom: 3,
      attributionControl: { compact: true },
    })

    mapRef.current.addControl(new maplibregl.NavigationControl(), 'top-right')

    return () => {
      hoverPopupRef.current?.remove()
      clickPopupRef.current?.remove()
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [])

  // Add / update GeoJSON source when data changes
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    function addLayers() {
      if (!map) return

      // If source already exists, update data
      if (map.getSource('locations')) {
        (map.getSource('locations') as maplibregl.GeoJSONSource).setData(geojson)
        return
      }

      // Clustered GeoJSON source
      map.addSource('locations', {
        type: 'geojson',
        data: geojson,
        cluster: true,
        clusterMaxZoom: 14,
        clusterRadius: 50,
      })

      // ── Cluster circles ──
      map.addLayer({
        id: 'clusters',
        type: 'circle',
        source: 'locations',
        filter: ['has', 'point_count'],
        paint: {
          'circle-color': MAP_COLORS.clusterBg,
          'circle-radius': ['step', ['get', 'point_count'], 18, 10, 24, 30, 32],
          'circle-stroke-color': MAP_COLORS.dotDefault,
          'circle-stroke-width': 2,
          'circle-opacity': 0.9,
        },
      })

      // ── Cluster count labels ──
      map.addLayer({
        id: 'cluster-count',
        type: 'symbol',
        source: 'locations',
        filter: ['has', 'point_count'],
        layout: {
          'text-field': '{point_count_abbreviated}',
          'text-size': 13,
          'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
        },
        paint: {
          'text-color': MAP_COLORS.clusterText,
        },
      })

      // ── Unclustered individual markers ──
      map.addLayer({
        id: 'unclustered-point',
        type: 'circle',
        source: 'locations',
        filter: ['!', ['has', 'point_count']],
        paint: {
          'circle-radius': sizeProperty
            ? ['interpolate', ['linear'], ['get', sizeProperty], 1, 6, 5, 9, 15, 13, 30, 18]
            : 8,
          'circle-color': [
            'step', ['get', 'mention_count'],
            MAP_COLORS.dotDefault,  // default: blue
            10, MAP_COLORS.dotHigh, // 10+ mentions: amber
          ],
          'circle-opacity': 0.9,
          'circle-stroke-color': MAP_COLORS.stroke,
          'circle-stroke-width': 1.5,
        },
      })

      // ── Selected feature highlight ring ──
      map.addLayer({
        id: 'selected-ring',
        type: 'circle',
        source: 'locations',
        filter: ['==', ['get', 'name'], ''],
        paint: {
          'circle-radius': sizeProperty
            ? ['interpolate', ['linear'], ['get', sizeProperty], 1, 10, 5, 13, 15, 17, 30, 22]
            : 12,
          'circle-color': 'transparent',
          'circle-stroke-color': MAP_COLORS.selectedRing,
          'circle-stroke-width': 3,
          'circle-opacity': 1,
        },
      })

      // ── Cluster click → zoom ──
      map.on('click', 'clusters', (e) => {
        const features = map!.queryRenderedFeatures(e.point, { layers: ['clusters'] })
        const clusterId = features[0]?.properties?.cluster_id
        if (clusterId == null) return
        const source = map!.getSource('locations') as maplibregl.GeoJSONSource
        source.getClusterExpansionZoom(clusterId).then((zoom) => {
          const geom = features[0].geometry
          if (geom.type !== 'Point') return
          map!.easeTo({ center: geom.coordinates as [number, number], zoom })
        })
      })

      // ── Hover tooltip on unclustered points ──
      map.on('mouseenter', 'unclustered-point', (e) => {
        map!.getCanvas().style.cursor = 'pointer'
        const feature = e.features?.[0]
        if (!feature || feature.geometry.type !== 'Point') return
        const props = feature.properties as Record<string, unknown>
        const name = props?.name ?? 'Unknown'
        const type = ENTITY_TYPE_LABELS[(props?.entity_type as string) ?? ''] ?? ''
        const mentions = props?.mention_count ?? 0
        const sources = props?.source_count ?? 0

        hoverPopupRef.current?.remove()
        hoverPopupRef.current = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: false,
          offset: 12,
          className: 'anveshak-map-tooltip',
        })
          .setLngLat(feature.geometry.coordinates as [number, number])
          .setHTML(
            `<div style="background:${MAP_COLORS.popupBg};color:${MAP_COLORS.popupText};padding:6px 10px;border-radius:6px;font-size:12px;line-height:1.4;border:1px solid #2d3748;">` +
            `<strong>${name}</strong>` +
            (type ? ` <span style="color:${MAP_COLORS.popupMuted};font-size:11px;">(${type})</span>` : '') +
            `<br/><span style="color:${MAP_COLORS.popupMuted};">${mentions} mentions · ${sources} sources</span>` +
            `</div>`
          )
          .addTo(map!)
      })

      map.on('mouseleave', 'unclustered-point', () => {
        map!.getCanvas().style.cursor = ''
        hoverPopupRef.current?.remove()
        hoverPopupRef.current = null
      })

      // ── Rich click popup ──
      map.on('click', 'unclustered-point', (e) => {
        const feature = e.features?.[0]
        if (!feature || feature.geometry.type !== 'Point') return
        const coords = feature.geometry.coordinates.slice() as [number, number]
        const props = feature.properties as Record<string, unknown>
        const name = String(props?.name ?? 'Unknown')
        const entityType = String(props?.entity_type ?? 'GPE')
        const typeLabel = ENTITY_TYPE_LABELS[entityType] ?? entityType
        const mentions = Number(props?.mention_count ?? 0)
        const sources = Number(props?.source_count ?? 0)
        const latest = formatTimeAgo(props?.latest_mention as string | null)

        // Remove hover popup when click popup opens
        hoverPopupRef.current?.remove()
        clickPopupRef.current?.remove()

        clickPopupRef.current = new maplibregl.Popup({
          closeButton: true,
          closeOnClick: true,
          offset: 14,
          maxWidth: '260px',
        })
          .setLngLat(coords)
          .setHTML(
            `<div style="background:${MAP_COLORS.popupBg};color:${MAP_COLORS.popupText};padding:10px 14px;border-radius:8px;font-size:12px;line-height:1.6;border:1px solid #2d3748;">` +
            `<div style="font-size:14px;font-weight:600;margin-bottom:4px;">${name}</div>` +
            `<div style="margin-bottom:6px;">` +
            `<span style="display:inline-block;background:#3b82f620;color:#3b82f6;padding:1px 6px;border-radius:4px;font-size:11px;font-weight:500;">${typeLabel}</span>` +
            `</div>` +
            `<div style="color:${MAP_COLORS.popupMuted};">` +
            `${mentions} mentions · ${sources} sources` +
            (latest ? `<br/>Latest: ${latest}` : '') +
            `</div>` +
            `<div style="margin-top:8px;border-top:1px solid #2d3748;padding-top:6px;">` +
            `<a href="?entity=${encodeURIComponent(name)}" style="color:#3b82f6;text-decoration:none;font-size:11px;font-weight:500;">View content →</a>` +
            `</div>` +
            `</div>`
          )
          .addTo(map!)

        // Notify parent
        onFeatureClick?.(props as Record<string, unknown>)
      })

      // Cluster hover cursor
      map.on('mouseenter', 'clusters', () => { map!.getCanvas().style.cursor = 'pointer' })
      map.on('mouseleave', 'clusters', () => { map!.getCanvas().style.cursor = '' })

      // ── Fit bounds ──
      if (geojson.features.length > 0) {
        const bounds = new maplibregl.LngLatBounds()
        geojson.features.forEach((f) => {
          if (f.geometry.type === 'Point') {
            bounds.extend(f.geometry.coordinates as [number, number])
          }
        })
        if (!bounds.isEmpty()) {
          map.fitBounds(bounds, { padding: 60, maxZoom: 8 })
        }
      }
    }

    if (map.isStyleLoaded()) {
      addLayers()
    } else {
      map.once('load', addLayers)
    }
  }, [geojson, sizeProperty, onFeatureClick])

  // Update selected feature highlight
  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) return
    if (map.getLayer('selected-ring')) {
      map.setFilter('selected-ring', [
        '==', ['get', 'name'], selectedFeature ?? '',
      ])
    }
  }, [selectedFeature])

  return (
    <div className="relative w-full h-full">
      <div
        ref={containerRef}
        className="w-full h-full rounded-lg overflow-hidden"
        role="img"
        aria-label="Geographic map of mentioned locations"
      />
      {/* Legend overlay */}
      <div
        className="absolute bottom-3 left-3 bg-anveshak-card/90 backdrop-blur-sm border border-anveshak-border rounded-lg px-3 py-2 text-xs text-text-muted pointer-events-none"
        aria-label="Map legend"
      >
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: MAP_COLORS.dotDefault }} />
            Few mentions
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-4 rounded-full" style={{ background: MAP_COLORS.dotHigh }} />
            Many mentions
          </span>
        </div>
      </div>
    </div>
  )
})

export default GeoMap
