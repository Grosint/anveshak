import { useNavigate } from 'react-router-dom'
import { Signal } from '../../api/signals'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { formatDistanceToNow } from 'date-fns'

const severityVariantMap: Record<string, 'danger' | 'warning' | 'success' | 'default'> = {
  HIGH:   'danger',
  MEDIUM: 'warning',
  MED:    'warning',
  LOW:    'success',
}

function inferSeverity(signal: Signal): string {
  // signal_type or description may contain severity hint
  const t = signal.signal_type.toUpperCase()
  if (t.includes('HIGH') || t.includes('CRITICAL')) return 'HIGH'
  if (t.includes('MED')) return 'MED'
  if (t.includes('LOW')) return 'LOW'
  return 'HIGH' // default — an alert is always significant
}

interface SignalCardProps {
  signal: Signal
  onAcknowledge: (id: string) => void
  onDismiss: (id: string) => void
  isActioning?: boolean
}

export function SignalCard({ signal, onAcknowledge, onDismiss, isActioning }: SignalCardProps) {
  const navigate = useNavigate()
  const severity = inferSeverity(signal)
  const severityVariant = severityVariantMap[severity] ?? 'default'
  const isNew = signal.status === 'new'

  function handleCardClick() {
    navigate(`/topics/${signal.topic_id}/feed`)
  }

  return (
    <article
      className={`h-full bg-anveshak-card border rounded-lg p-4 transition-all animate-fade-in cursor-pointer hover:border-anveshak-accent/50 ${
        isNew
          ? 'border-anveshak-accent/60 shadow-[0_0_0_1px_rgba(59,130,246,0.2)]'
          : 'border-anveshak-border'
      }`}
      aria-label={`Signal: ${signal.signal_type} — click to view topic feed`}
      onClick={handleCardClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && handleCardClick()}
    >
      <div className="flex items-start justify-between gap-3">
        {/* Left: content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            {isNew && <span className="w-2 h-2 rounded-full bg-anveshak-accent shrink-0" aria-label="Unread" />}
            <Badge variant={severityVariant}>{severity}</Badge>
            <Badge variant="ghost">{signal.signal_type.replace(/_/g, ' ')}</Badge>
            {signal.status !== 'new' && (
              <Badge variant="default">{signal.status}</Badge>
            )}
          </div>

          <p className="text-sm text-text-primary font-medium line-clamp-2">
            {signal.description || 'Signal triggered — review cluster for details.'}
          </p>

          {signal.cluster_label && (
            <p className="text-xs text-anveshak-accent mt-1 truncate" title={signal.cluster_label}>
              Cluster: {signal.cluster_label}
              {signal.independent_source_count != null && (
                <span className="ml-2 text-text-muted">
                  ({signal.independent_source_count} independent sources)
                </span>
              )}
            </p>
          )}

          <p className="text-xs text-text-muted mt-1">
            {formatDistanceToNow(new Date(signal.created_at), { addSuffix: true })}
          </p>
        </div>

        {/* Right: actions — stop propagation so clicks don't navigate */}
        {signal.status !== 'dismissed' && (
          <div className="flex items-center gap-1.5 shrink-0" onClick={(e) => e.stopPropagation()}>
            {signal.status === 'new' && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onAcknowledge(signal.id)}
                disabled={isActioning}
                aria-label="Acknowledge signal"
              >
                Ack
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onDismiss(signal.id)}
              disabled={isActioning}
              aria-label="Dismiss signal"
            >
              Dismiss
            </Button>
          </div>
        )}
      </div>
    </article>
  )
}
