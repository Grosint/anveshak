import { lazy, Suspense, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { topicsApi } from '../../api/topics'
import { SourceDiscoveryTab } from '../discovery/SourceDiscoveryTab'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'

const SourceAssessmentPanel = lazy(() => import('./SourceAssessmentPanel'))

const HEALTH_VARIANT: Record<string, 'success' | 'warning' | 'danger' | 'default'> = {
  healthy: 'success', degraded: 'warning', down: 'danger', unverified: 'default',
}

interface SourcesTabProps {
  topicId: string
}

export default function SourcesTab({ topicId }: SourcesTabProps) {
  const qc = useQueryClient()
  const [view, setView] = useState<'linked' | 'discover'>('linked')
  const [assessSource, setAssessSource] = useState<{ id: string; name: string } | null>(null)

  const { data: linkedSources = [], isLoading } = useQuery({
    queryKey: ['topic-sources', topicId],
    queryFn: () => topicsApi.listSources(topicId),
  })

  const unlinkMut = useMutation({
    mutationFn: (sourceId: string) => topicsApi.unlinkSource(topicId, sourceId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['topic-sources', topicId] }),
  })

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-2 border-b border-anveshak-border flex items-center gap-2">
        <Button size="sm" variant={view === 'linked' ? 'primary' : 'secondary'} onClick={() => setView('linked')}>
          Linked Sources ({linkedSources.length})
        </Button>
        <Button size="sm" variant={view === 'discover' ? 'primary' : 'secondary'} onClick={() => setView('discover')}>
          Discover Sources
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {view === 'linked' ? (
          isLoading ? (
            <Spinner label="Loading sources..." />
          ) : linkedSources.length === 0 ? (
            <p className="text-sm text-text-muted">No sources linked to this topic.</p>
          ) : (
            <div className="space-y-2">
              {linkedSources.map((src) => (
                <div
                  key={src.id}
                  className="flex items-center justify-between p-3 bg-anveshak-card border border-anveshak-border rounded-lg"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Badge variant="ghost" className="text-[9px] shrink-0">{src.platform.toUpperCase()}</Badge>
                    <Badge variant={HEALTH_VARIANT[src.health_status] ?? 'default'} className="text-[9px] shrink-0">
                      {src.health_status}
                    </Badge>
                    <span className="text-sm text-text-primary truncate">{src.name}</span>
                    <span className="text-[10px] text-text-muted">{src.item_count} items</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => setAssessSource({ id: src.id, name: src.name })}
                    >
                      Assess
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => unlinkMut.mutate(src.id)}
                      disabled={unlinkMut.isPending}
                    >
                      Unlink
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : (
          <SourceDiscoveryTab topicId={topicId} />
        )}
      </div>

      {/* Source Assessment slide-over */}
      {assessSource && (
        <div className="border-t border-anveshak-border bg-anveshak-card">
          <Suspense fallback={<Spinner label="Loading assessment..." />}>
            <SourceAssessmentPanel
              topicId={topicId}
              sourceId={assessSource.id}
              sourceName={assessSource.name}
              onClose={() => setAssessSource(null)}
            />
          </Suspense>
        </div>
      )}
    </div>
  )
}
