import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { signalsApi, Signal } from '../../api/signals'
import { Badge } from '../ui/Badge'
import { inferSeverity } from '../../lib/domain'
import { formatDistanceToNow } from 'date-fns'

const severityVariant: Record<string, 'danger' | 'warning' | 'success' | 'default'> = {
  HIGH: 'danger', MEDIUM: 'warning', LOW: 'success',
}

interface SignalsSidebarProps {
  topicId: string
  onSelectSignal: (signal: Signal) => void
}

export function SignalsSidebar({ topicId, onSelectSignal }: SignalsSidebarProps) {
  const qc = useQueryClient()

  const { data: signalsPage, isLoading } = useQuery({
    queryKey: ['signals-topic', topicId, 'new'],
    queryFn: () => signalsApi.listByTopic(topicId, 'new'),
    refetchInterval: 120_000,
    refetchOnWindowFocus: false,
  })
  const signals = signalsPage?.items ?? []

  const ackMut = useMutation({
    mutationFn: signalsApi.acknowledge,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['signals-topic', topicId] }),
  })

  const dismissMut = useMutation({
    mutationFn: signalsApi.dismiss,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['signals-topic', topicId] }),
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest">
          Signals
        </h3>
        {signals.length > 0 && (
          <span className="text-[10px] font-bold text-signal-high bg-signal-high/20 rounded-full px-1.5 py-0.5">
            {signals.length} new
          </span>
        )}
      </div>

      {isLoading ? (
        <p className="text-[11px] text-text-muted">Loading...</p>
      ) : signals.length === 0 ? (
        <p className="text-[11px] text-text-muted">No new signals</p>
      ) : (
        <div className="space-y-1.5">
          {signals.slice(0, 10).map((sig) => {
            const sev = inferSeverity(sig)
            return (
              <button
                key={sig.id}
                onClick={() => onSelectSignal(sig)}
                className="w-full text-left bg-anveshak-card border border-anveshak-border rounded p-2 hover:border-anveshak-accent/40 transition-all"
              >
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-anveshak-accent shrink-0" />
                  <Badge variant={severityVariant[sev] ?? 'default'} className="text-[8px] px-1 py-0">
                    {sev}
                  </Badge>
                  <span className="text-[9px] text-text-muted truncate">
                    {sig.signal_type.replace(/_/g, ' ')}
                  </span>
                </div>
                <p className="text-[11px] text-text-primary leading-tight line-clamp-2">
                  {sig.cluster_label || sig.description}
                </p>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-[9px] text-text-muted">
                    {formatDistanceToNow(new Date(sig.created_at), { addSuffix: true })}
                  </span>
                  <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => ackMut.mutate(sig.id)}
                      className="text-[8px] text-anveshak-accent hover:underline"
                      disabled={ackMut.isPending}
                    >
                      Ack
                    </button>
                    <button
                      onClick={() => dismissMut.mutate(sig.id)}
                      className="text-[8px] text-text-muted hover:underline"
                      disabled={dismissMut.isPending}
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
