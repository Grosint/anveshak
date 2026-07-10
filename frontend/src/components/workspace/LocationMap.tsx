import { lazy, Suspense, useState, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { intelligenceApi } from '../../api/intelligence'
import { Spinner } from '../ui/Spinner'
import { EmptyState } from '../ui/EmptyState'
import LocationPanel from '../map/LocationPanel'

import type { GeoMapHandle } from '../map/GeoMap'

const GeoMap = lazy(() => import('../map/GeoMap'))

interface Props {
  topicId: string
  topicName?: string
}

interface LocationMetadata {
  total_extracted: number
  geocoded: number
  unresolved: string[]
}

export default function LocationMap({ topicId, topicName }: Props) {
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null)
  const [panelCollapsed, setPanelCollapsed] = useState(false)
  const geoMapRef = useRef<GeoMapHandle>(null)

  const queryClient = useQueryClient()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['location-map', topicId],
    queryFn: () => intelligenceApi.locationMap(topicId, 2, 100),
    staleTime: 300_000,
  })

  // Analyst pins
  const { data: pinsData } = useQuery({
    queryKey: ['analyst-pins', topicId],
    queryFn: () => intelligenceApi.listPins(topicId),
    staleTime: 60_000,
  })

  const createPinMutation = useMutation({
    mutationFn: (pin: { lat: number; lng: number; label: string }) =>
      intelligenceApi.createPin(topicId, pin.lat, pin.lng, pin.label),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['analyst-pins', topicId] }),
  })

  const handlePinDrop = useCallback((lat: number, lng: number) => {
    const label = window.prompt('Pin label:')
    if (label == null) return // cancelled
    createPinMutation.mutate({ lat, lng, label })
  }, [createPinMutation])

  const geojson = data as (GeoJSON.FeatureCollection & { metadata?: LocationMetadata }) | undefined
  const metadata = (data as any)?.metadata as LocationMetadata | undefined

  const handleFeatureClick = useCallback((props: Record<string, unknown>) => {
    setSelectedLocation(String(props.name ?? ''))
  }, [])

  const handleFlyTo = useCallback((lng: number, lat: number) => {
    geoMapRef.current?.flyTo(lng, lat)
  }, [])

  if (isLoading) return <div className="p-8 flex justify-center"><Spinner label="Loading location data..." /></div>
  if (isError) return <div className="p-4 text-red-400 text-xs">Failed to load location map.</div>
  if (!geojson || geojson.features.length === 0) {
    return <EmptyState icon="🗺️" title="No locations yet" description="Location entities will appear after content is analyzed by the NLP pipeline." />
  }

  // Sort features by mention_count descending
  const sortedFeatures = [...geojson.features].sort((a, b) => {
    const aCount = (a.properties as any)?.mention_count ?? 0
    const bCount = (b.properties as any)?.mention_count ?? 0
    return bCount - aCount
  })

  const unresolvedNames = metadata?.unresolved ?? []
  const totalExtracted = metadata?.total_extracted ?? geojson.features.length
  const geocodedCount = metadata?.geocoded ?? geojson.features.length

  return (
    <div className="flex flex-col h-[calc(100vh-180px)] min-h-[400px]">
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-anveshak-border bg-anveshak-bg/50">
        <p className="text-xs text-text-muted">
          {geocodedCount} of {totalExtracted} locations geocoded
          {unresolvedNames.length > 0 && (
            <span className="text-signal-med ml-1">
              · {unresolvedNames.length} unresolved
            </span>
          )}
        </p>
        <button
          onClick={() => setPanelCollapsed(!panelCollapsed)}
          className="text-xs text-text-secondary hover:text-text-primary transition-colors px-2 py-1 rounded hover:bg-anveshak-muted/50"
          aria-label={panelCollapsed ? 'Show location panel' : 'Hide location panel'}
        >
          {panelCollapsed ? '◀ Show panel' : 'Hide panel ▶'}
        </button>
      </div>

      {/* Map + Panel split */}
      <div className="flex flex-1 min-h-0">
        {/* Map */}
        <div className="flex-1 min-w-0">
          <Suspense fallback={<div className="flex items-center justify-center h-full"><Spinner label="Loading map..." /></div>}>
            <GeoMap
              ref={geoMapRef}
              geojson={geojson}
              sizeProperty="mention_count"
              onFeatureClick={handleFeatureClick}
              selectedFeature={selectedLocation}
              topicName={topicName}
              pins={pinsData}
              onPinDrop={handlePinDrop}
            />
          </Suspense>
        </div>

        {/* Location panel with sparklines + drill-down */}
        {!panelCollapsed && (
          <LocationPanel
            topicId={topicId}
            features={sortedFeatures}
            selectedLocation={selectedLocation}
            onSelectLocation={setSelectedLocation}
            onFlyTo={handleFlyTo}
            unresolvedNames={unresolvedNames}
          />
        )}
      </div>
    </div>
  )
}
