import { useQuery } from '@tanstack/react-query'
import { provenanceApi } from '../../api/provenance'
import { useProvenance } from '../../contexts/ProvenanceContext'
import { Spinner } from '../ui/Spinner'
import { Badge } from '../ui/Badge'
import { EmptyState } from '../ui/EmptyState'
import { formatDistanceToNow } from 'date-fns'

interface IdentifierDetailProps {
  identifierValue: string
  topicId: string
}

export default function IdentifierDetail({ identifierValue, topicId }: IdentifierDetailProps) {
  const { push } = useProvenance()

  const { data, isLoading } = useQuery({
    queryKey: ['provenance', 'identifier', identifierValue, topicId],
    queryFn: () => provenanceApi.identifierProvenance(identifierValue, topicId),
    enabled: !!identifierValue && !!topicId,
  })

  if (isLoading) return <div className="p-4"><Spinner label="Loading identifier..." /></div>
  if (!data) return <EmptyState icon="🔍" title="Not found" description="Identifier provenance unavailable." />

  return (
    <div className="divide-y divide-anveshak-border/30">
      {/* Header */}
      <div className="px-4 py-3">
        <p className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-1">Identifier</p>
        <p className="text-sm font-mono font-semibold text-amber-400 break-all">{identifierValue}</p>
      </div>

      {/* Found In — content items with snippet */}
      <Section title={`Found In (${data.content_items.length})`}>
        {data.content_items.length === 0 ? (
          <p className="text-[11px] text-text-muted">No content items found.</p>
        ) : (
          <div className="space-y-2">
            {data.content_items.map((item) => (
              <button
                key={item.id}
                className="w-full text-left bg-anveshak-card/50 border border-anveshak-border rounded-lg p-2.5 hover:border-anveshak-accent/40 transition-colors"
                onClick={() => push({ entityType: 'content', entityId: item.id, topicId, label: item.title || item.snippet.slice(0, 30) })}
              >
                <div className="flex items-center justify-between mb-1">
                  {item.platform && (
                    <span className="text-[9px] font-bold text-text-muted">{item.platform.toUpperCase()}</span>
                  )}
                  <span className="text-[9px] text-text-muted">
                    {formatDistanceToNow(new Date(item.captured_at), { addSuffix: true })}
                  </span>
                </div>
                {item.title && (
                  <p className="text-[11px] font-medium text-text-primary line-clamp-1 mb-0.5">{item.title}</p>
                )}
                <p className="text-[10px] text-text-secondary/70 line-clamp-2">{item.snippet}</p>
              </button>
            ))}
          </div>
        )}
      </Section>

      {/* Sources */}
      <Section title={`Sources (${data.sources.length})`}>
        {data.sources.length === 0 ? (
          <p className="text-[11px] text-text-muted">No sources identified.</p>
        ) : (
          <div className="space-y-1.5">
            {data.sources.map((src) => {
              const credColor = src.credibility_score >= 70 ? 'text-green-400' : src.credibility_score >= 40 ? 'text-amber-400' : 'text-red-400'
              return (
                <button
                  key={src.id}
                  className="w-full flex items-center justify-between text-left p-2 bg-anveshak-card/50 border border-anveshak-border rounded hover:border-anveshak-accent/40 transition-colors"
                  onClick={() => push({ entityType: 'source', entityId: src.id, topicId, label: src.name })}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-[9px] font-bold text-text-muted">{src.platform.toUpperCase()}</span>
                    <span className="text-[11px] text-text-primary truncate">{src.name}</span>
                  </div>
                  <span className={`text-[10px] font-mono font-bold ${credColor}`}>{Math.round(src.credibility_score)}</span>
                </button>
              )
            })}
          </div>
        )}
      </Section>

      {/* Clusters */}
      <Section title={`Clusters (${data.clusters.length})`}>
        {data.clusters.length === 0 ? (
          <p className="text-[11px] text-text-muted">Not yet clustered.</p>
        ) : (
          <div className="space-y-1.5">
            {data.clusters.map((cl) => (
              <button
                key={cl.id}
                className="w-full flex items-center justify-between text-left p-2 bg-anveshak-card/50 border border-anveshak-border rounded hover:border-anveshak-accent/40 transition-colors"
                onClick={() => push({ entityType: 'cluster', entityId: cl.id, topicId, label: cl.label || 'Unclassified' })}
              >
                <span className="text-[11px] text-text-primary truncate">{cl.label || 'Unclassified'}</span>
                <div className="flex items-center gap-2 shrink-0">
                  <Badge variant="accent">{cl.item_count}</Badge>
                  <span className="text-[9px] text-text-muted">{cl.isc} ISC</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </Section>

      {/* Signals */}
      <Section title={`Signals (${data.signals.length})`}>
        {data.signals.length === 0 ? (
          <p className="text-[11px] text-text-muted">No signals triggered.</p>
        ) : (
          <div className="space-y-1.5">
            {data.signals.map((sig) => (
              <button
                key={sig.id}
                className="w-full flex items-center justify-between text-left p-2 bg-anveshak-card/50 border border-anveshak-border rounded hover:border-anveshak-accent/40 transition-colors"
                onClick={() => push({ entityType: 'signal', entityId: sig.id, topicId, label: `Signal ${sig.status}` })}
              >
                <Badge variant={sig.status === 'new' ? 'danger' : sig.status === 'acknowledged' ? 'warning' : 'default'}>
                  {sig.status}
                </Badge>
                <span className="text-[9px] text-text-muted">
                  {formatDistanceToNow(new Date(sig.fired_at), { addSuffix: true })}
                </span>
              </button>
            ))}
          </div>
        )}
      </Section>

      {/* Cross-topic appearances */}
      {data.cross_topic_appearances.length > 0 && (
        <Section title={`Cross-Topic (${data.cross_topic_appearances.length})`}>
          <div className="space-y-1">
            {data.cross_topic_appearances.map((ct) => (
              <div
                key={ct.topic_name}
                className="flex items-center justify-between p-2 bg-cyan-500/[0.04] border border-cyan-500/15 rounded"
              >
                <span className="text-[11px] text-cyan-400 truncate">{ct.topic_name}</span>
                <span className="text-[10px] text-text-muted">{ct.mention_count} mentions</span>
              </div>
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
