import { useState, lazy, Suspense } from 'react'
import { useQuery } from '@tanstack/react-query'
import { provenanceApi } from '../../api/provenance'
import { useProvenance } from '../../contexts/ProvenanceContext'
import { Spinner } from '../ui/Spinner'
import { Badge } from '../ui/Badge'
import { EmptyState } from '../ui/EmptyState'
import { format, formatDistanceToNow } from 'date-fns'
import { TimelineItems } from './TimelineItems'

const FlowGraph = lazy(() => import('./FlowGraph'))

interface ClusterDetailProps {
  clusterId: string
  topicId: string
}

export default function ClusterDetail({ clusterId, topicId }: ClusterDetailProps) {
  const { push } = useProvenance()
  const [flowExpanded, setFlowExpanded] = useState(false)

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

      {/* Source spread narrative */}
      {sourceSpread.length > 0 && (
        <Section title="Source Spread">
          <p className="text-[11px] text-text-secondary leading-relaxed mb-2">
            {sourceSpread.map((s, i) => (
              <span key={s.source_id}>
                {i > 0 && ' → '}
                <span className="font-semibold text-text-primary">{s.platform.toUpperCase()}/{s.source_name}</span>
              </span>
            ))}
          </p>
          <div className="space-y-1">
            {sourceSpread.map((src) => (
              <div key={src.source_id} className="flex items-center justify-between text-[10px]">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-bold text-text-secondary shrink-0">{src.platform.toUpperCase()}</span>
                  <span className="text-text-muted truncate">{src.source_name}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0 text-[9px] text-text-muted">
                  <span>{src.item_count} items</span>
                  <span>{format(new Date(src.first_seen), 'MMM d HH:mm')}</span>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Vertical content timeline */}
      <Section title={`Timeline (${data.items.length})`}>
        <TimelineItems items={data.items} topicId={topicId} maxHeight="400px" />
      </Section>

      {/* Key identifiers — ranked by mention count */}
      {data.identifiers.length > 0 && (
        <Section title={`Key Identifiers (${data.identifiers.length})`}>
          <div className="space-y-1">
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

      {/* Information flow graph — lazy-loaded, expandable */}
      <div className="px-4 py-3">
        <button
          className="w-full flex items-center justify-between text-left"
          onClick={() => setFlowExpanded(!flowExpanded)}
        >
          <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest">
            Information Flow
          </h3>
          <svg
            viewBox="0 0 20 20"
            fill="currentColor"
            className={`w-3.5 h-3.5 text-text-muted transition-transform ${flowExpanded ? 'rotate-180' : ''}`}
          >
            <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
          </svg>
        </button>
        {flowExpanded && (
          <div className="mt-2">
            <Suspense fallback={<Spinner label="Loading flow graph..." />}>
              <FlowGraph clusterId={clusterId} topicId={topicId} />
            </Suspense>
          </div>
        )}
      </div>
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
