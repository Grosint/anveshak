import { useNavigate } from 'react-router-dom'
import { Signal, SignalSource } from '../../api/signals'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { severityMeasurement, signalTitle, SEVERITY_VARIANT } from '../../lib/domain'
import { formatDistanceToNow } from 'date-fns'
import { ManufacturedNarrativeBody, type ManufacturedEvidence } from './ManufacturedNarrativeBody'
import { MobilizationBody, type MobilizationEvidence } from './MobilizationBody'

const platformIcons: Record<string, string> = {
  web: 'WEB',
  rss: 'RSS',
  telegram: 'TG',
  reddit: 'RDT',
  bluesky: 'BSK',
  x: 'X',
}

/**
 * Shorten a source name for a chip.
 *
 * Only a URL is reduced to its host. A handle such as "r/india" is left
 * alone: splitting it on "/" left the chip reading "r", which is evidence
 * the analyst cannot check.
 */
function displaySourceName(name: string): string {
  if (!/^https?:\/\//i.test(name)) return name
  return name.replace(/^https?:\/\/(www\.)?/i, '').split('/')[0]
}

function SourceChip({ source }: { source: SignalSource }) {
  const credColor =
    source.credibility_score >= 70 ? 'text-cred-high' :
    source.credibility_score >= 40 ? 'text-signal-med' :
    'text-signal-high'

  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-anveshak-muted text-[11px]">
      <span className="font-semibold text-text-secondary">
        {platformIcons[source.platform] ?? source.platform.toUpperCase()}
      </span>
      <span className="text-text-muted truncate max-w-[120px]" title={source.source_name}>
        {displaySourceName(source.source_name)}
      </span>
      <span className={`font-mono font-semibold ${credColor}`}>
        {Math.round(source.credibility_score)}
      </span>
    </span>
  )
}

interface SignalCardProps {
  signal: Signal
  onAcknowledge: (id: string) => void
  onDismiss: (id: string) => void
  isActioning?: boolean
}

export function SignalCard({ signal, onAcknowledge, onDismiss, isActioning }: SignalCardProps) {
  const navigate = useNavigate()
  const measurement = severityMeasurement(signal)
  const severityVariant = SEVERITY_VARIANT[measurement.level] ?? 'ghost'
  const title = signalTitle(signal)
  const isNew = signal.status === 'new'
  const sources = signal.sources ?? []
  const itemCount = signal.cluster_item_count ?? 0

  function handleCardClick() {
    navigate(`/topics/${signal.topic_id}`)
  }

  const timelineText = (() => {
    if (!signal.first_seen) return null
    const first = formatDistanceToNow(new Date(signal.first_seen), { addSuffix: true })
    if (!signal.last_seen || signal.first_seen === signal.last_seen) {
      return `First seen ${first}`
    }
    const last = formatDistanceToNow(new Date(signal.last_seen), { addSuffix: true })
    return `${first} — latest ${last}`
  })()

  return (
    <article
      className={`h-full bg-anveshak-card border rounded-lg transition-all animate-fade-in cursor-pointer hover:border-anveshak-accent/50 ${
        isNew
          ? 'border-anveshak-accent/60 shadow-[0_0_0_1px_rgba(59,130,246,0.2)]'
          : 'border-anveshak-border'
      }`}
      aria-label={`Signal: ${signal.cluster_label || signal.signal_type} — click to view topic feed`}
      onClick={handleCardClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && handleCardClick()}
    >
      {/* Header row */}
      <div className="flex items-center justify-between gap-2 px-4 pt-3 pb-2">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          {isNew && <span className="w-2 h-2 rounded-full bg-anveshak-accent shrink-0" aria-label="Unread" />}
          <Badge variant="ghost">{signal.signal_type.replace(/_/g, ' ')}</Badge>
          {signal.status !== 'new' && (
            <Badge variant="default">{signal.status}</Badge>
          )}
          {signal.topic_name && (
            <span className="text-xs text-text-muted truncate" title={signal.topic_name}>
              {signal.topic_name}
            </span>
          )}
        </div>

        {/* Actions */}
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

      {/* Evidence leads: the narrative the analyst reads, then what was
          measured about it. ADR 0001 — a title states what was measured,
          never what it means, and any score is secondary. */}
      <div className="px-4 pb-1">
        <p className="text-sm text-text-primary font-medium leading-snug">
          {signal.cluster_label || signal.description || 'Cluster under review'}
        </p>
        <p className="text-xs text-text-secondary mt-0.5 leading-snug">{title}</p>
      </div>

      {/* Type-specific body. A timeline, an evidence list and an extracted
          date cannot share one generic card. Issue #31. */}
      {signal.signal_type === 'manufactured_narrative' && (
        <ManufacturedNarrativeBody
          evidence={signal.evidence as ManufacturedEvidence | null}
        />
      )}

      {signal.signal_type === 'mobilization_call' && (
        <MobilizationBody evidence={signal.evidence as MobilizationEvidence | null} />
      )}

      {/* Executive summary — the key intelligence */}
      {signal.executive_summary && (
        <div className="px-4 pb-2">
          <p className="text-xs text-text-secondary leading-relaxed line-clamp-3">
            {signal.executive_summary}
          </p>
        </div>
      )}

      {/* Source breakdown */}
      {sources.length > 0 && (
        <div className="px-4 pb-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] text-text-muted font-medium">
              {signal.independent_source_count ?? sources.length} platforms:
            </span>
            {sources.map((src, i) => (
              <SourceChip key={i} source={src} />
            ))}
          </div>
        </div>
      )}

      {/* Footer: timeline + item count */}
      <div className="flex items-center justify-between gap-3 px-4 pb-3 pt-1 border-t border-anveshak-border/50">
        <div className="flex items-center gap-3 text-[11px] text-text-muted">
          {timelineText && <span>{timelineText}</span>}
          {itemCount > 0 && (
            <span className="flex items-center gap-1">
              <span className="font-semibold text-text-secondary">{itemCount}</span> items in cluster
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[11px] text-text-muted">{measurement.statement}</span>
          <Badge
            variant={severityVariant}
            className="font-mono"
            aria-label={`Magnitude ${measurement.level}`}
          >
            {measurement.level}
          </Badge>
          <span className="text-[11px] text-text-muted">
            {formatDistanceToNow(new Date(signal.created_at), { addSuffix: true })}
          </span>
        </div>
      </div>
    </article>
  )
}
