import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { signalsApi } from '../../api/signals'
import { useProvenance } from '../../contexts/ProvenanceContext'
import { Spinner } from '../ui/Spinner'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { inferSeverity } from '../../lib/domain'
import { formatDistanceToNow } from 'date-fns'

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

  // Fetch from both new + acknowledged pools
  const { data: newPage } = useQuery({
    queryKey: ['signals-topic', topicId, 'new'],
    queryFn: () => signalsApi.listByTopic(topicId, 'new'),
  })
  const { data: ackPage } = useQuery({
    queryKey: ['signals-topic', topicId, 'acknowledged'],
    queryFn: () => signalsApi.listByTopic(topicId, 'acknowledged'),
  })

  const allSignals = [...(newPage?.items ?? []), ...(ackPage?.items ?? [])]
  const signal = allSignals.find((s) => s.id === signalId)

  const ackMut = useMutation({
    mutationFn: signalsApi.acknowledge,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['signals-topic', topicId] }),
  })

  const dismissMut = useMutation({
    mutationFn: signalsApi.dismiss,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['signals-topic', topicId] }),
  })

  if (!signal) return <div className="p-4"><Spinner label="Loading signal..." /></div>

  const sev = inferSeverity(signal)
  const sources = signal.sources ?? []

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

      {/* Cluster link */}
      {signal.cluster_id && (
        <div className="px-4 py-3">
          <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">Cluster</h3>
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
        </div>
      )}

      {/* Sources */}
      {sources.length > 0 && (
        <div className="px-4 py-3">
          <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">
            {signal.independent_source_count ?? sources.length} Independent Sources
          </h3>
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
        </div>
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
