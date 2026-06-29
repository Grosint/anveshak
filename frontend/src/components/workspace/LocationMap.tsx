import { lazy, Suspense, useState, useCallback, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { intelligenceApi } from '../../api/intelligence'
import { Spinner } from '../ui/Spinner'
import { EmptyState } from '../ui/EmptyState'
import { Badge } from '../ui/Badge'

import type { GeoMapHandle } from '../map/GeoMap'

const GeoMap = lazy(() => import('../map/GeoMap'))

const ENTITY_TYPE_LABELS: Record<string, string> = {
  GPE: 'Country / State',
  LOC: 'Place',
  FAC: 'Facility',
}

const ENTITY_TYPE_BADGE_VARIANT: Record<string, 'accent' | 'default' | 'warning'> = {
  GPE: 'accent',
  LOC: 'default',
  FAC: 'warning',
}

interface Props {
  topicId: string
}

interface LocationMetadata {
  total_extracted: number
  geocoded: number
  unresolved: string[]
}

export default function LocationMap({ topicId }: Props) {
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null)
  const [listCollapsed, setListCollapsed] = useState(false)
  const geoMapRef = useRef<GeoMapHandle>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['location-map', topicId],
    queryFn: () => intelligenceApi.locationMap(topicId, 2, 100),
    staleTime: 300_000,
  })

  const geojson = data as (GeoJSON.FeatureCollection & { metadata?: LocationMetadata }) | undefined
  const metadata = (data as any)?.metadata as LocationMetadata | undefined

  const handleFeatureClick = useCallback((props: Record<string, unknown>) => {
    setSelectedLocation(String(props.name ?? ''))
  }, [])

  const handleListItemClick = useCallback((feature: GeoJSON.Feature) => {
    if (feature.geometry.type !== 'Point') return
    const [lng, lat] = feature.geometry.coordinates
    const name = String((feature.properties as any)?.name ?? '')
    setSelectedLocation(name)
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
          onClick={() => setListCollapsed(!listCollapsed)}
          className="text-xs text-text-secondary hover:text-text-primary transition-colors px-2 py-1 rounded hover:bg-anveshak-muted/50"
          aria-label={listCollapsed ? 'Show location list' : 'Hide location list'}
        >
          {listCollapsed ? '◀ Show list' : 'Hide list ▶'}
        </button>
      </div>

      {/* Map + List split */}
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
            />
          </Suspense>
        </div>

        {/* Location list panel */}
        {!listCollapsed && (
          <div className="w-72 border-l border-anveshak-border bg-anveshak-bg flex flex-col min-h-0">
            {/* Scrollable location list */}
            <div className="flex-1 overflow-y-auto">
              <div className="px-3 py-2 border-b border-anveshak-border/50">
                <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wide">
                  Locations ({sortedFeatures.length})
                </h3>
              </div>

              {sortedFeatures.map((feature, i) => {
                const props = feature.properties as Record<string, any>
                const name = props?.name ?? 'Unknown'
                const entityType = props?.entity_type ?? 'GPE'
                const mentions = props?.mention_count ?? 0
                const sources = props?.source_count ?? 0
                const isSelected = selectedLocation === name

                return (
                  <button
                    key={`${name}-${i}`}
                    onClick={() => handleListItemClick(feature)}
                    className={`w-full text-left px-3 py-2.5 border-b border-anveshak-border/30 hover:bg-anveshak-muted/30 transition-colors ${
                      isSelected ? 'bg-anveshak-accent/10 border-l-2 border-l-anveshak-accent' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-text-primary font-medium truncate mr-2">{name}</span>
                      <span className="text-sm font-bold text-text-primary tabular-nums">{mentions}</span>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant={ENTITY_TYPE_BADGE_VARIANT[entityType] ?? 'default'}>
                        {ENTITY_TYPE_LABELS[entityType] ?? entityType}
                      </Badge>
                      <span className="text-xs text-text-muted">{sources} src</span>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Unresolved section */}
            {unresolvedNames.length > 0 && (
              <div className="border-t border-anveshak-border">
                <div className="px-3 py-2 border-b border-anveshak-border/50">
                  <h3 className="text-xs font-medium text-signal-med uppercase tracking-wide">
                    Unresolved ({unresolvedNames.length})
                  </h3>
                </div>
                <div className="max-h-32 overflow-y-auto">
                  {unresolvedNames.map((name) => (
                    <div key={name} className="px-3 py-1.5 text-xs text-text-muted">
                      {name}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
