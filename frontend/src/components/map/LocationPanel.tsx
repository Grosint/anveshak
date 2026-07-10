/**
 * Location sidebar panel — sparklines + content drill-down.
 * Replaces inline location list from LocationMap.tsx with richer UI.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { intelligenceApi } from '../../api/intelligence'
import { Badge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'

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

interface SparklineProps {
  data: { week: string; count: number }[]
  width?: number
  height?: number
}

function Sparkline({ data, width = 80, height = 24 }: SparklineProps) {
  if (data.length < 2) return null
  const max = Math.max(...data.map((d) => d.count), 1)
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - (d.count / max) * (height - 2)
    return `${x},${y}`
  })
  const areaPoints = [...points, `${width},${height}`, `0,${height}`]

  return (
    <svg width={width} height={height} className="inline-block" aria-label="Mention trend">
      <polygon points={areaPoints.join(' ')} fill="rgba(59,130,246,0.15)" />
      <polyline points={points.join(' ')} fill="none" stroke="#3b82f6" strokeWidth="1.5" />
    </svg>
  )
}

interface ContentItem {
  id: string
  title: string
  url: string
  captured_at: string | null
  source_name: string
  platform: string
  sentiment_compound: number | null
}

function sentimentBadge(compound: number | null) {
  if (compound == null) return null
  if (compound >= 0.05) return <Badge variant="accent">Pos</Badge>
  if (compound <= -0.05) return <Badge variant="warning">Neg</Badge>
  return <Badge variant="default">Neu</Badge>
}

interface LocationPanelProps {
  topicId: string
  features: GeoJSON.Feature[]
  selectedLocation: string | null
  onSelectLocation: (name: string) => void
  onFlyTo: (lng: number, lat: number) => void
  unresolvedNames: string[]
}

export default function LocationPanel({
  topicId,
  features,
  selectedLocation,
  onSelectLocation,
  onFlyTo,
  unresolvedNames,
}: LocationPanelProps) {
  const [drillDownEntity, setDrillDownEntity] = useState<string | null>(null)

  // Timeline data
  const { data: timelineData } = useQuery({
    queryKey: ['location-timeline', topicId],
    queryFn: () => intelligenceApi.locationTimeline(topicId),
    staleTime: 300_000,
  })

  // Drill-down content
  const { data: drillContent, isLoading: drillLoading } = useQuery({
    queryKey: ['location-content', topicId, drillDownEntity],
    queryFn: () => intelligenceApi.locationContent(topicId, drillDownEntity!),
    enabled: !!drillDownEntity,
    staleTime: 60_000,
  })

  // Build timeline lookup by name
  const timelineByName: Record<string, { week: string; count: number }[]> = {}
  if (timelineData) {
    for (const loc of timelineData.locations) {
      timelineByName[loc.name] = loc.timeline
    }
  }

  const handleItemClick = (feature: GeoJSON.Feature) => {
    if (feature.geometry.type !== 'Point') return
    const [lng, lat] = feature.geometry.coordinates
    const name = String((feature.properties as any)?.name ?? '')
    onSelectLocation(name)
    onFlyTo(lng, lat)
  }

  const handleDrillDown = (name: string) => {
    setDrillDownEntity(drillDownEntity === name.toLowerCase() ? null : name.toLowerCase())
  }

  return (
    <div className="w-80 border-l border-anveshak-border bg-anveshak-bg flex flex-col min-h-0">
      {/* Location list with sparklines */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-3 py-2 border-b border-anveshak-border/50">
          <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wide">
            Locations ({features.length})
          </h3>
        </div>

        {features.map((feature, i) => {
          const props = feature.properties as Record<string, any>
          const name = props?.name ?? 'Unknown'
          const entityType = props?.entity_type ?? 'GPE'
          const mentions = props?.mention_count ?? 0
          const sources = props?.source_count ?? 0
          const isSelected = selectedLocation === name
          const timeline = timelineByName[name] ?? []

          return (
            <div key={`${name}-${i}`}>
              <button
                onClick={() => handleItemClick(feature)}
                className={`w-full text-left px-3 py-2.5 border-b border-anveshak-border/30 hover:bg-anveshak-muted/30 transition-colors ${
                  isSelected ? 'bg-anveshak-accent/10 border-l-2 border-l-anveshak-accent' : ''
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-primary font-medium truncate mr-2">{name}</span>
                  <span className="text-sm font-bold text-text-primary tabular-nums">{mentions}</span>
                </div>
                <div className="flex items-center justify-between mt-1">
                  <div className="flex items-center gap-2">
                    <Badge variant={ENTITY_TYPE_BADGE_VARIANT[entityType] ?? 'default'}>
                      {ENTITY_TYPE_LABELS[entityType] ?? entityType}
                    </Badge>
                    <span className="text-xs text-text-muted">{sources} src</span>
                  </div>
                  {timeline.length >= 2 && <Sparkline data={timeline} />}
                </div>
              </button>

              {/* Drill-down toggle */}
              {isSelected && (
                <div className="px-3 py-1 border-b border-anveshak-border/30 bg-anveshak-muted/10">
                  <button
                    onClick={() => handleDrillDown(name)}
                    className="text-xs text-anveshak-accent hover:underline"
                  >
                    {drillDownEntity === name.toLowerCase() ? 'Hide content' : 'View content'}
                  </button>
                </div>
              )}

              {/* Drill-down content */}
              {drillDownEntity === name.toLowerCase() && (
                <div className="px-3 py-2 bg-anveshak-muted/20 border-b border-anveshak-border/30 max-h-64 overflow-y-auto">
                  {drillLoading ? (
                    <Spinner label="Loading..." />
                  ) : drillContent && drillContent.length > 0 ? (
                    drillContent.map((item: ContentItem) => (
                      <div key={item.id} className="py-1.5 border-b border-anveshak-border/20 last:border-0">
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-text-primary hover:text-anveshak-accent line-clamp-2"
                        >
                          {item.title || item.url}
                        </a>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[10px] text-text-muted">{item.source_name}</span>
                          <span className="text-[10px] text-text-muted">{item.platform}</span>
                          {sentimentBadge(item.sentiment_compound)}
                          {item.captured_at && (
                            <span className="text-[10px] text-text-muted">
                              {new Date(item.captured_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-text-muted">No content found.</p>
                  )}
                </div>
              )}
            </div>
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
  )
}
