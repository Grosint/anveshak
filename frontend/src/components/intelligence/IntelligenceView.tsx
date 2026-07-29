import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { intelligenceApi, IntelSignal, IntelCluster, IntelIdentifier, IntelLocation } from '../../api/intelligence'
import { topicsApi } from '../../api/topics'
import { useProvenance } from '../../contexts/ProvenanceContext'
import { SignalCards } from './SignalCards'
import { NarrativeCards } from './NarrativeCards'
import { IdentifierPills } from './IdentifierPills'
import { LocationPills } from './LocationPills'
import { RecentContent } from './RecentContent'
import { SourceHealthStrip } from './SourceHealthStrip'
import { Button } from '../ui/Button'
import { Spinner } from '../ui/Spinner'
import { EmptyState } from '../ui/EmptyState'

interface IntelligenceViewProps {
  topicId: string
  topicStatus?: 'active' | 'paused' | 'archived'
  onNavigateMap?: () => void
  onNavigateContent?: () => void
  onShowAllClusters?: () => void
  onShowAllIdentifiers?: () => void
  onShowAllSignals?: () => void
  onGenerateReport?: () => void
  onManageSources?: () => void
}

export function IntelligenceView({
  topicId,
  topicStatus,
  onNavigateMap,
  onNavigateContent,
  onShowAllClusters,
  onShowAllIdentifiers,
  onShowAllSignals,
  onGenerateReport,
  onManageSources,
}: IntelligenceViewProps) {
  const provenance = useProvenance()
  const qc = useQueryClient()

  const { data: intel, isLoading, isError } = useQuery({
    queryKey: ['topic-intelligence', topicId],
    queryFn: () => intelligenceApi.topicIntelligence(topicId),
    enabled: !!topicId,
    refetchInterval: 120_000,
  })

  const statusMut = useMutation({
    mutationFn: (newStatus: 'active' | 'paused') => topicsApi.updateStatus(topicId, newStatus),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topics', topicId] })
    },
  })

  // ── Click handlers — all push to provenance panel ───────────────────

  const handleSelectSignal = (signal: IntelSignal) => {
    provenance.push({
      entityType: 'signal',
      entityId: signal.id,
      topicId,
      label: signal.cluster_label || signal.description,
    })
  }

  const handleSelectCluster = (cluster: IntelCluster) => {
    provenance.push({
      entityType: 'cluster',
      entityId: cluster.id,
      topicId,
      label: cluster.label || 'Cluster',
    })
  }

  const handleSelectIdentifier = (identifier: IntelIdentifier) => {
    provenance.push({
      entityType: 'identifier',
      entityId: identifier.identifier_value,
      topicId,
      label: identifier.identifier_value,
    })
  }

  const handleSelectLocation = (_location: IntelLocation) => {
    // TODO(#10): pass coordinates to center map on location
    if (onNavigateMap) onNavigateMap()
  }

  const handleSelectContent = (contentId: string, title?: string) => {
    provenance.push({
      entityType: 'content',
      entityId: contentId,
      topicId,
      label: title || contentId.slice(0, 8),
    })
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner label="Loading intelligence..." />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="p-6">
        <EmptyState
          icon="⚠️"
          title="Failed to load intelligence"
          description="Could not fetch topic intelligence data. Try refreshing."
        />
      </div>
    )
  }

  const toggleStatus = topicStatus === 'active' ? 'paused' : 'active'

  return (
    <div className="p-6 max-w-4xl space-y-6 overflow-y-auto">
      {/* Header actions */}
      <div className="flex items-center justify-end gap-2">
        {onGenerateReport && (
          <Button size="sm" variant="primary" onClick={onGenerateReport}>
            Generate Report
          </Button>
        )}
        <Button
          size="sm"
          variant="secondary"
          onClick={() => statusMut.mutate(toggleStatus)}
          disabled={statusMut.isPending}
        >
          {statusMut.isPending ? '...' : toggleStatus === 'paused' ? 'Pause' : 'Resume'}
        </Button>
      </div>

      {/* Section 1: Signals (with summary bar, filters, inline limit) */}
      <SignalCards
        signals={intel?.signals ?? []}
        onSelect={handleSelectSignal}
        onShowAll={onShowAllSignals}
      />

      {/* Section 2: Narratives (with open/closed filters, inline limit) */}
      <NarrativeCards
        clusters={intel?.clusters ?? []}
        onSelect={handleSelectCluster}
        onShowAll={onShowAllClusters}
        totalCount={intel?.stats?.total_clusters}
      />

      {/* Section 3: Key Identifiers (inline limit) */}
      <IdentifierPills
        identifiers={intel?.identifiers ?? []}
        onSelect={handleSelectIdentifier}
        onShowAll={onShowAllIdentifiers}
      />

      {/* Section 4: Location Pills */}
      <LocationPills
        locations={intel?.locations ?? []}
        onSelectLocation={handleSelectLocation}
        onOpenMap={onNavigateMap}
      />

      {/* Section 5: Recent Content */}
      <RecentContent
        topicId={topicId}
        onSelectContent={handleSelectContent}
        onShowAll={onNavigateContent}
      />

      {/* Section 6: Source Health Strip */}
      <SourceHealthStrip
        sources={intel?.source_health ?? []}
        onManage={onManageSources}
      />
    </div>
  )
}
