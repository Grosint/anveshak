import { lazy, Suspense } from 'react'
import { useQuery } from '@tanstack/react-query'
import { intelligenceApi } from '../../api/intelligence'
import { Spinner } from '../ui/Spinner'
import { EmptyState } from '../ui/EmptyState'

const GeoMap = lazy(() => import('../map/GeoMap'))

interface Props {
  topicId: string
}

export default function LocationMap({ topicId }: Props) {
  const { data: geojson, isLoading, isError } = useQuery({
    queryKey: ['location-map', topicId],
    queryFn: () => intelligenceApi.locationMap(topicId, 2, 100),
    staleTime: 300_000,
  })

  if (isLoading) return <div className="p-8 flex justify-center"><Spinner label="Loading location data..." /></div>
  if (isError) return <div className="p-4 text-red-400 text-xs">Failed to load location map.</div>
  if (!geojson || geojson.features.length === 0) {
    return <EmptyState icon="🗺️" title="No locations yet" description="Location entities will appear after content is analyzed by the NLP pipeline." />
  }

  return (
    <div className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs text-text-muted">
          {geojson.features.length} location{geojson.features.length !== 1 ? 's' : ''} mentioned across content
        </p>
      </div>
      <Suspense fallback={<Spinner label="Loading map..." />}>
        <div className="h-[500px] rounded-lg overflow-hidden border border-anveshak-border">
          <GeoMap geojson={geojson} sizeProperty="mention_count" />
        </div>
      </Suspense>
    </div>
  )
}
