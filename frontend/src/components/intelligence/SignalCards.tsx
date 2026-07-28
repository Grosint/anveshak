import type { IntelSignal } from '../../api/intelligence'
import { inferSeverityFromISC, SEVERITY_VARIANT } from '../../lib/domain'
import { Badge } from '../ui/Badge'
import { formatDistanceToNow } from 'date-fns'

interface SignalCardsProps {
  signals: IntelSignal[]
  onSelect: (signal: IntelSignal) => void
}

export function SignalCards({ signals, onSelect }: SignalCardsProps) {
  if (signals.length === 0) return null

  return (
    <section>
      <h2 className="text-[11px] font-bold text-text-muted uppercase tracking-widest mb-3">
        Signals
        <span className="ml-2 text-signal-high bg-signal-high/20 rounded-full px-1.5 py-0.5 text-[9px]">
          {signals.length} new
        </span>
      </h2>
      <div className="space-y-3">
        {signals.map((sig) => {
          const sev = inferSeverityFromISC(sig.isc)
          return (
            <button
              key={sig.id}
              onClick={() => onSelect(sig)}
              className="w-full text-left bg-anveshak-card border border-anveshak-accent/60 rounded-lg p-3 hover:border-anveshak-accent transition-all shadow-[0_0_0_1px_rgba(59,130,246,0.2)]"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="w-2 h-2 rounded-full bg-anveshak-accent shrink-0" />
                <Badge variant={SEVERITY_VARIANT[sev] ?? 'default'} className="text-[9px] px-1.5 py-0">
                  {sev}
                </Badge>
                <span className="text-[9px] text-text-muted truncate">
                  {sig.signal_type.replace(/_/g, ' ')}
                </span>
              </div>
              <p className="text-xs text-text-primary font-medium leading-snug line-clamp-2 mb-1.5">
                {sig.cluster_label || sig.description}
              </p>
              <div className="flex items-center justify-between text-[10px] text-text-muted">
                <span>{sig.isc} independent sources</span>
                <span>{formatDistanceToNow(new Date(sig.fired_at), { addSuffix: true })}</span>
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}
