import { useQuery } from '@tanstack/react-query'
import { provenanceApi } from '../../api/provenance'
import { useProvenance } from '../../contexts/ProvenanceContext'
import { Spinner } from '../ui/Spinner'
import { Badge } from '../ui/Badge'
import { EmptyState } from '../ui/EmptyState'
import { formatDistanceToNow } from 'date-fns'

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

  return (
    <div className="divide-y divide-anveshak-border/30">
      {/* Header */}
      <div className="px-4 py-3">
        <p className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-1">Narrative Cluster</p>
        <p className="text-sm font-semibold text-text-primary">{data.label || 'Unclassified'}</p>
        <div className="flex items-center gap-2 mt-2">
          <Badge variant="accent">{data.item_count} items</Badge>
          <span className="text-[10px] text-text-muted">{data.isc} independent sources</span>
        </div>
        {data.executive_summary && (
          <p className="text-[11px] text-text-secondary leading-relaxed mt-2">{data.executive_summary}</p>
        )}
      </div>

      {/* Signal status */}
      {data.signal && (
        <div className="px-4 py-3">
          <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">Signal</h3>
          <button
            className="w-full flex items-center justify-between text-left p-2 bg-anveshak-card/50 border border-anveshak-border rounded hover:border-anveshak-accent/40 transition-colors"
            onClick={() => push({ entityType: 'signal', entityId: data.signal!.id, topicId, label: `Signal ${data.signal!.status}` })}
          >
            <Badge variant={data.signal.status === 'new' ? 'danger' : data.signal.status === 'acknowledged' ? 'warning' : 'default'}>
              {data.signal.status}
            </Badge>
            <span className="text-[9px] text-text-muted">
              {formatDistanceToNow(new Date(data.signal.fired_at), { addSuffix: true })}
            </span>
          </button>
        </div>
      )}

      {/* Member items */}
      <Section title={`Member Items (${data.items.length})`}>
        {data.items.length === 0 ? (
          <p className="text-[11px] text-text-muted">No items in this cluster.</p>
        ) : (
          <div className="space-y-1.5">
            {data.items.map((item) => (
              <button
                key={item.id}
                className="w-full text-left p-2 bg-anveshak-card/50 border border-anveshak-border rounded hover:border-anveshak-accent/40 transition-colors"
                onClick={() => push({ entityType: 'content', entityId: item.id, topicId, label: item.title || item.clean_text?.slice(0, 30) })}
              >
                <div className="flex items-center justify-between mb-0.5">
                  <div className="flex items-center gap-2 min-w-0">
                    {item.platform && (
                      <span className="text-[9px] font-bold text-text-muted">{item.platform.toUpperCase()}</span>
                    )}
                    {item.source_name && (
                      <span className="text-[9px] text-text-muted truncate">{item.source_name}</span>
                    )}
                  </div>
                  <span className="text-[9px] text-text-muted shrink-0">
                    {formatDistanceToNow(new Date(item.captured_at), { addSuffix: true })}
                  </span>
                </div>
                {item.title && (
                  <p className="text-[11px] font-medium text-text-primary line-clamp-1">{item.title}</p>
                )}
                <p className="text-[10px] text-text-secondary/70 line-clamp-2">{item.clean_text}</p>
              </button>
            ))}
          </div>
        )}
      </Section>

      {/* Key identifiers */}
      {data.identifiers.length > 0 && (
        <Section title={`Key Identifiers (${data.identifiers.length})`}>
          <div className="flex flex-wrap gap-1.5">
            {data.identifiers.map((id, i) => (
              <button
                key={i}
                className="text-[10px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-md px-2 py-0.5 hover:bg-amber-500/20 transition-colors"
                onClick={() => push({ entityType: 'identifier', entityId: id.entity_text, topicId, label: id.entity_text })}
              >
                {id.entity_text}
                <span className="text-[8px] text-text-muted ml-1">{id.mention_count}×</span>
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
