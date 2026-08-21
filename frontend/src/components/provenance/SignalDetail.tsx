import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { signalsApi } from '../../api/signals'
import { provenanceApi } from '../../api/provenance'
import { useProvenance } from '../../contexts/ProvenanceContext'
import { Spinner } from '../ui/Spinner'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { inferSeverity } from '../../lib/domain'
import { formatDistanceToNow, format } from 'date-fns'
import { TimelineItems } from './TimelineItems'

const severityVariant: Record<string, 'danger' | 'warning' | 'success' | 'default'> = {
  HIGH: 'danger', MEDIUM: 'warning', LOW: 'success',
}

interface SignalDetailProps {
  signalId: string
  topicId: string
}

export default function SignalDetail({ signalId, topicId }: SignalDetailProps) {
  const { push } = useProvenance()
  const qc = useQueryClient()

  // Fetch signal directly by ID
  const { data: signal, isLoading, isError } = useQuery({
    queryKey: ['signal', signalId],
    queryFn: () => signalsApi.getById(signalId),
  })

  // Fetch cluster provenance for enrichment (timeline, identifiers, source spread)
  const { data: clusterData } = useQuery({
    queryKey: ['provenance', 'cluster', signal?.cluster_id, topicId],
    queryFn: () => provenanceApi.clusterProvenance(signal!.cluster_id!, topicId),
    enabled: !!signal?.cluster_id && !!topicId,
  })

  const ackMut = useMutation({
    mutationFn: signalsApi.acknowledge,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['signal', signalId] })
      qc.invalidateQueries({ queryKey: ['signals-topic', topicId] })
    },
  })

  const dismissMut = useMutation({
    mutationFn: signalsApi.dismiss,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['signal', signalId] })
      qc.invalidateQueries({ queryKey: ['signals-topic', topicId] })
    },
  })

  if (isLoading) return <div className="p-4"><Spinner label="Loading signal..." /></div>
  if (isError || !signal) return <div className="p-4 text-text-muted text-xs">Signal not found</div>

  const sev = inferSeverity(signal)
  const sources = signal.sources ?? []

  // Derive enrichment from cluster data
  const timelineItems = (clusterData?.items ?? []).slice(0, 5)
  const originatingItem = timelineItems[0] ?? null
  const keyIdentifiers = (clusterData?.identifiers ?? []).slice(0, 8)
  const sourceSpread = clusterData?.source_spread ?? []

  return (
    <div className="divide-y divide-anveshak-border/30">
      {/* Header */}
      <div className="px-4 py-3">
        <div className="flex items-center gap-2 flex-wrap mb-2">
          <Badge variant={severityVariant[sev] ?? 'default'}>{sev}</Badge>
          <Badge variant="ghost">{signal.signal_type.replace(/_/g, ' ')}</Badge>
          <Badge variant="default">{signal.status}</Badge>
        </div>

        <h3 className="text-sm font-semibold text-text-primary">
          {signal.cluster_label || signal.description}
        </h3>

        {signal.executive_summary && (
          <p className="text-[11px] text-text-secondary leading-relaxed mt-2">{signal.executive_summary}</p>
        )}

        <div className="flex items-center gap-3 text-[10px] text-text-muted mt-2">
          {signal.first_seen && (
            <span>First: {formatDistanceToNow(new Date(signal.first_seen), { addSuffix: true })}</span>
          )}
          <span>{signal.cluster_item_count ?? 0} items</span>
        </div>
      </div>

      {/* Trigger explanation */}
      <Section title="Why it fired">
        <div className="bg-anveshak-card/50 border border-anveshak-border rounded p-2.5">
          <p className="text-[11px] text-text-primary leading-relaxed">
            ISC crossed threshold{' '}
            <span className="font-bold text-anveshak-accent">
              {(signal.independent_source_count ?? 1) - 1} → {signal.independent_source_count ?? 1}
            </span>
            {signal.first_seen && (
              <> on {format(new Date(signal.first_seen), 'MMM d, yyyy HH:mm')}</>
            )}
          </p>
          {originatingItem && (
            <p className="text-[10px] text-text-muted mt-1.5">
              Originating narrative:{' '}
              <button
                className="text-anveshak-accent hover:underline"
                onClick={() => push({ entityType: 'content', entityId: originatingItem.id, topicId, label: originatingItem.title || 'First item' })}
              >
                {originatingItem.title || originatingItem.clean_text?.slice(0, 60) + '...'}
              </button>
            </p>
          )}
        </div>
      </Section>

      {/* Key identifiers driving this signal */}
      {keyIdentifiers.length > 0 && (
        <Section title={`Key Identifiers (${keyIdentifiers.length})`}>
          <div className="flex flex-wrap gap-1.5">
            {keyIdentifiers.map((id, i) => (
              <button
                key={i}
                className="text-[10px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-md px-2 py-0.5 hover:bg-amber-500/20 transition-colors"
                onClick={() => push({ entityType: 'identifier', entityId: id.entity_text, topicId, label: id.entity_text })}
              >
                {id.entity_text}
                <span className="text-[8px] text-text-muted ml-1">{id.mention_count}× · {id.source_count} src</span>
              </button>
            ))}
          </div>
        </Section>
      )}

      {/* Content timeline — key items that built the narrative */}
      {timelineItems.length > 0 && (
        <Section title="Content Timeline">
          <TimelineItems items={timelineItems} topicId={topicId} />
        </Section>
      )}

      {/* Source spread — ordered by first appearance */}
      {sourceSpread.length > 0 && (
        <Section title={`Source Spread (${sourceSpread.length})`}>
          <div className="space-y-1">
            {sourceSpread.map((src, i) => {
              const arrow = i > 0 ? '→ ' : ''
              return (
                <div key={src.source_id} className="flex items-center gap-2 text-[10px]">
                  <span className="text-text-muted">{arrow}</span>
                  <span className="font-bold text-text-secondary">{src.platform.toUpperCase()}</span>
                  <span className="text-text-muted truncate">{src.source_name}</span>
                  <span className="text-[9px] text-text-muted ml-auto shrink-0">
                    {format(new Date(src.first_seen), 'MMM d HH:mm')}
                  </span>
                </div>
              )
            })}
          </div>
        </Section>
      )}

      {/* Cluster link */}
      {signal.cluster_id && (
        <Section title="Cluster">
          <button
            className="w-full text-left p-2 bg-anveshak-card/50 border border-anveshak-border rounded hover:border-anveshak-accent/40 transition-colors"
            onClick={() => push({
              entityType: 'cluster',
              entityId: signal.cluster_id!,
              topicId,
              label: signal.cluster_label || 'Unclassified',
            })}
          >
            <span className="text-[11px] text-text-primary">{signal.cluster_label || 'Unclassified'}</span>
            <span className="text-[9px] text-text-muted ml-2">{signal.cluster_item_count} items</span>
          </button>
        </Section>
      )}

      {/* Sources (original) */}
      {sources.length > 0 && (
        <Section title={`${signal.independent_source_count ?? sources.length} Independent Sources`}>
          <div className="flex items-center gap-1.5 flex-wrap">
            {sources.map((src, i) => {
              const credColor = src.credibility_score >= 70 ? 'text-green-400' : src.credibility_score >= 40 ? 'text-amber-400' : 'text-red-400'
              return (
                <span key={i} className="text-[10px] bg-anveshak-muted rounded px-1.5 py-0.5">
                  <span className="font-semibold text-text-secondary">{src.platform.toUpperCase()}</span>{' '}
                  <span className="text-text-muted">{src.source_name.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}</span>{' '}
                  <span className={`font-mono font-bold ${credColor}`}>{Math.round(src.credibility_score)}</span>
                </span>
              )
            })}
          </div>
        </Section>
      )}

      {/* Actions */}
      <div className="px-4 py-3">
        <div className="flex gap-2 flex-wrap">
          {signal.status === 'new' && (
            <Button size="sm" variant="secondary" onClick={() => ackMut.mutate(signal.id)} disabled={ackMut.isPending}>
              Acknowledge
            </Button>
          )}
          {signal.status !== 'dismissed' && (
            <Button size="sm" variant="ghost" onClick={() => dismissMut.mutate(signal.id)} disabled={dismissMut.isPending}>
              Dismiss
            </Button>
          )}
        </div>
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
