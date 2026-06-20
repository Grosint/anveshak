/**
 * Lazy-loaded MapLibre GL map component.
 * Import via: const GeoMap = React.lazy(() => import('../components/map/GeoMap'))
 *
 * This file is only loaded when the GIS tab is opened — saves ~700KB from initial bundle.
 */
import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

interface GeoMapProps {
  geojson: GeoJSON.FeatureCollection
  /** When set, circle radius scales by this numeric feature property. */
  sizeProperty?: string
}

export default function GeoMap({ geojson, sizeProperty }: GeoMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://demotiles.maplibre.org/style.json',
      center: [0, 20],
      zoom: 1.5,
      attributionControl: { compact: true },
    })

    mapRef.current.addControl(new maplibregl.NavigationControl(), 'top-right')

    return () => {
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [])

  // Add / update GeoJSON source when data changes
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    function addLayer() {
      if (!map) return
      if (map.getSource('locations')) {
        (map.getSource('locations') as maplibregl.GeoJSONSource).setData(geojson)
        return
      }

      map.addSource('locations', { type: 'geojson', data: geojson })

      map.addLayer({
        id: 'locations-circle',
        type: 'circle',
        source: 'locations',
        paint: {
          'circle-radius': sizeProperty
            ? ['interpolate', ['linear'], ['get', sizeProperty], 1, 6, 5, 10, 20, 18, 50, 24]
            : 8,
          'circle-color': '#3b82f6',
          'circle-opacity': 0.85,
          'circle-stroke-color': '#ffffff',
          'circle-stroke-width': 2,
        },
      })

      // Popup on click
      map.on('click', 'locations-circle', (e) => {
        const feature = e.features?.[0]
        if (!feature || feature.geometry.type !== 'Point') return
        const coords = feature.geometry.coordinates.slice() as [number, number]
        const props = feature.properties as Record<string, unknown>
        const name = props?.name ?? 'Unknown location'
        const count = sizeProperty && props?.[sizeProperty] ? ` <span style="color:#64748b">(${props[sizeProperty]} mentions)</span>` : ''

        new maplibregl.Popup({ closeButton: true, closeOnClick: true })
          .setLngLat(coords)
          .setHTML(`<strong style="color:#0f172a">${name}</strong>${count}`)
          .addTo(map!)
      })

      map.on('mouseenter', 'locations-circle', () => { map!.getCanvas().style.cursor = 'pointer' })
      map.on('mouseleave', 'locations-circle', () => { map!.getCanvas().style.cursor = '' })

      // Fit bounds if features exist
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
      addLayer()
    } else {
      map.once('load', addLayer)
    }
  }, [geojson, sizeProperty])

  return (
    <div
      ref={containerRef}
      className="w-full h-80 rounded-lg overflow-hidden border border-anveshak-border"
      role="img"
      aria-label="Geographic map of mentioned locations"
    />
  )
}
