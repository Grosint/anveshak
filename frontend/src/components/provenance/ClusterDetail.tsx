import { lazy, Suspense } from 'react'
import { useQuery } from '@tanstack/react-query'
import { provenanceApi } from '../../api/provenance'
import { useProvenance } from '../../contexts/ProvenanceContext'
import { Spinner } from '../ui/Spinner'
import { Badge } from '../ui/Badge'
import { EmptyState } from '../ui/EmptyState'
import { formatDistanceToNow, differenceInHours, differenceInDays } from 'date-fns'
import { TimelineItems } from './TimelineItems'
import { PlatformBadge } from '../content/PlatformBadge'

const FlowGraph = lazy(() => import('./FlowGraph'))

interface ClusterDetailProps {
  clusterId: string
  topicId: string
}

export default function ClusterDetail({ clusterId, topicId }: ClusterDetailProps) {
  const { push } = useProvenance()

  const { data, isLoading } = useQuery({
    queryKey: ['provenance', 'cluster', clusterId, topicId],
    queryFn: () => provenanceApi.clusterProvenance(clusterId, topicId),
    enabled: !!clusterId && !!topicId,
  })

  if (isLoading) return <div className="p-4"><Spinner label="Loading cluster..." /></div>
  if (!data) return <EmptyState icon="📊" title="Not found" description="Cluster not found." />

  const sourceSpread = data.source_spread ?? []
  const growth24h = data.growth_24h ?? 0
  const itemsPerDay = data.item_count > 0 && data.created_at
    ? (data.item_count / Math.max(1, (Date.now() - new Date(data.created_at).getTime()) / 86400000)).toFixed(1)
    : null

  return (
    <div className="divide-y divide-anveshak-border/30">
      {/* Header */}
      <div className="px-4 py-3">
        <p className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-1">Narrative Cluster</p>
        <p className="text-sm font-semibold text-text-primary">{data.label || 'Unclassified'}</p>
        <div className="flex items-center gap-2 mt-2 flex-wrap">
          <Badge variant="accent">{data.item_count} items</Badge>
          <span className="text-[10px] text-text-muted">{data.isc} independent sources</span>
          {growth24h > 0 && (
            <Badge variant="warning">+{growth24h} today</Badge>
          )}
          {data.items.some((it: { deepfake_score?: number | null }) => (it.deepfake_score ?? 0) >= 0.7) && (
            <Badge variant="danger">⚠ Deepfake Detected</Badge>
          )}
        </div>
        {data.executive_summary && (
          <p className="text-[11px] text-text-secondary leading-relaxed mt-2">{data.executive_summary}</p>
        )}

        {/* Growth metrics */}
        <div className="flex items-center gap-4 mt-2 text-[10px] text-text-muted">
          {itemsPerDay && <span>{itemsPerDay} items/day avg</span>}
          {data.created_at && (
            <span>Started {formatDistanceToNow(new Date(data.created_at), { addSuffix: true })}</span>
          )}
        </div>
      </div>

      {/* Signal status — prominently at top if fired */}
      {data.signal && (
        <div className="px-4 py-3">
          <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">Signal Produced</h3>
          <button
            className="w-full flex items-center justify-between text-left p-2 bg-anveshak-card/50 border border-anveshak-border rounded hover:border-anveshak-accent/40 transition-colors"
            onClick={() => push({ entityType: 'signal', entityId: data.signal!.id, topicId, label: `Signal ${data.signal!.status}` })}
          >
            <div className="flex items-center gap-2">
              <Badge variant={data.signal.status === 'new' ? 'danger' : data.signal.status === 'acknowledged' ? 'warning' : 'default'}>
                {data.signal.status}
              </Badge>
              <span className="text-[10px] text-text-secondary">{data.signal.signal_type?.replace(/_/g, ' ')}</span>
            </div>
            <span className="text-[9px] text-text-muted">
              {formatDistanceToNow(new Date(data.signal.fired_at), { addSuffix: true })}
            </span>
          </button>
        </div>
      )}

      {/* Source spread — flow graph + compact stats */}
      {sourceSpread.length > 0 && (
        <div className="px-4 py-3">
          <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">
            Source Spread ({sourceSpread.length} sources)
          </h3>

          {/* Flow graph — primary visualization */}
          <Suspense fallback={<Spinner label="Loading flow..." />}>
            <FlowGraph clusterId={clusterId} topicId={topicId} />
          </Suspense>

          {/* Compact source stats below graph */}
          <div className="mt-3 space-y-1.5">
            {sourceSpread.map((src, i) => {
              const maxItems = Math.max(...sourceSpread.map((s) => s.item_count))
              const barWidth = maxItems > 0 ? Math.max(8, (src.item_count / maxItems) * 100) : 8
              const prevDate = i > 0 ? new Date(sourceSpread[i - 1].first_seen) : null
              const curDate = new Date(src.first_seen)
              const daysDelta = prevDate ? differenceInDays(curDate, prevDate) : 0
              const hoursDelta = prevDate ? differenceInHours(curDate, prevDate) : 0
              const deltaLabel = prevDate
                ? daysDelta >= 1 ? `+${daysDelta}d` : `+${hoursDelta}h`
                : ''

              return (
                <div key={src.source_id} className="flex items-center gap-2 text-[10px]">
                  <PlatformBadge platform={src.platform} />
                  <span className="text-text-primary truncate min-w-0 flex-shrink">{src.source_name}</span>
                  <div className="flex-1 h-1 bg-anveshak-border/20 rounded-full overflow-hidden mx-1">
                    <div className="h-full bg-anveshak-accent/40 rounded-full" style={{ width: `${barWidth}%` }} />
                  </div>
                  <span className="text-[9px] text-text-muted font-mono shrink-0">{src.item_count}</span>
                  {deltaLabel && (
                    <span className="text-[8px] text-anveshak-accent shrink-0">{deltaLabel}</span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Content timeline */}
      <Section title={`Timeline (${data.items.length})`}>
        <TimelineItems items={data.items} topicId={topicId} maxHeight="500px" />
      </Section>

      {/* Key identifiers — ranked by mention count */}
      {data.identifiers.length > 0 && (
        <Section title={`Key Identifiers (${data.identifiers.length})`}>
          <div className="space-y-1 max-h-[200px] overflow-y-auto">
            {data.identifiers.map((id, i) => (
              <button
                key={i}
                className="w-full flex items-center justify-between text-left p-1.5 rounded hover:bg-anveshak-card/30 transition-colors"
                onClick={() => push({ entityType: 'identifier', entityId: id.entity_text, topicId, label: id.entity_text })}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-[9px] text-text-muted shrink-0">{id.entity_type}</span>
                  <span className="text-[10px] font-mono text-amber-400 truncate">{id.entity_text}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0 text-[9px] text-text-muted">
                  <span>{id.mention_count}×</span>
                  <span>{id.source_count} src</span>
                </div>
              </button>
            ))}
          </div>
        </Section>
      )}

    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="px-4 py-3">
      <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">{title}</h3>
      {children}
    </div>
  )
}
