import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { signalsApi } from '../../api/signals'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Spinner } from '../ui/Spinner'
import { inferSeverity } from '../../lib/domain'
import { formatDistanceToNow } from 'date-fns'

const severityVariant: Record<string, 'danger' | 'warning' | 'success' | 'default'> = {
  HIGH: 'danger', MEDIUM: 'warning', LOW: 'success',
}

interface SignalDetailPanelProps {
  signalId: string
  topicId: string
  onShowGraph?: (signalId: string) => void
}

export function SignalDetailPanel({ signalId, topicId, onShowGraph }: SignalDetailPanelProps) {
  const qc = useQueryClient()

  const { data: signalsPage } = useQuery({
    queryKey: ['signals-topic', topicId, 'new'],
    queryFn: () => signalsApi.listByTopic(topicId, 'new'),
  })
  const signals = signalsPage?.items ?? []

  const { data: ackSignalsPage } = useQuery({
    queryKey: ['signals-topic', topicId, 'acknowledged'],
    queryFn: () => signalsApi.listByTopic(topicId, 'acknowledged'),
  })
  const ackSignals = ackSignalsPage?.items ?? []

  const signal = [...signals, ...ackSignals].find((s) => s.id === signalId)

  const ackMut = useMutation({
    mutationFn: signalsApi.acknowledge,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['signals-topic', topicId] }),
  })

  const dismissMut = useMutation({
    mutationFn: signalsApi.dismiss,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['signals-topic', topicId] }),
  })

  if (!signal) {
    return <div className="p-4"><Spinner label="Loading signal..." /></div>
  }

  const sev = inferSeverity(signal)
  const sources = signal.sources ?? []

  return (
    <div className="p-4 space-y-4">
      {/* Header badges */}
      <div className="flex items-center gap-2 flex-wrap">
        <Badge variant={severityVariant[sev] ?? 'default'}>{sev}</Badge>
        <Badge variant="ghost">{signal.signal_type.replace(/_/g, ' ')}</Badge>
        <Badge variant="default">{signal.status}</Badge>
      </div>

      {/* Title */}
      <h3 className="text-sm font-semibold text-text-primary">
        {signal.cluster_label || signal.description}
      </h3>

      {/* Executive summary */}
      {signal.executive_summary && (
        <p className="text-xs text-text-secondary leading-relaxed">
          {signal.executive_summary}
        </p>
      )}

      {/* Timeline */}
      <div className="flex items-center gap-3 text-[11px] text-text-muted">
        {signal.first_seen && (
          <span>First: {formatDistanceToNow(new Date(signal.first_seen), { addSuffix: true })}</span>
        )}
        {signal.last_seen && signal.last_seen !== signal.first_seen && (
          <span>Latest: {formatDistanceToNow(new Date(signal.last_seen), { addSuffix: true })}</span>
        )}
        <span>{signal.cluster_item_count ?? 0} items</span>
      </div>

      {/* Sources */}
      {sources.length > 0 && (
        <div>
          <span className="text-[10px] text-text-muted block mb-1">
            {signal.independent_source_count ?? sources.length} independent sources:
          </span>
          <div className="flex items-center gap-1.5 flex-wrap">
            {sources.map((src, i) => {
              const credColor =
                src.credibility_score >= 70 ? 'text-cred-high' :
                src.credibility_score >= 40 ? 'text-signal-med' :
                'text-signal-high'
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
      <div className="flex gap-2 flex-wrap">
        {onShowGraph && (
          <Button size="sm" variant="primary" onClick={() => onShowGraph(signal.id)}>
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
              <path d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H4.233a.75.75 0 00-.75.75v4a.75.75 0 001.5 0v-2.146l.312.31a7 7 0 0011.712-3.138.75.75 0 00-1.449-.39zm1.436-7.674a.75.75 0 00-.75.75v2.146l-.312-.31A7 7 0 003.974 9.474a.75.75 0 101.449.39A5.5 5.5 0 0114.624 7.61l.312.311h-2.433a.75.75 0 000 1.5h3.999a.75.75 0 00.75-.75v-4a.75.75 0 00-.75-.75z" />
            </svg>
            View Graph
          </Button>
        )}
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
  )
}
