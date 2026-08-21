import { useState, useMemo } from 'react'
import type { IntelSignal } from '../../api/intelligence'
import { inferSeverityFromISC, SEVERITY_VARIANT, type SeverityLevel } from '../../lib/domain'
import { Badge } from '../ui/Badge'
import { formatDistanceToNow } from 'date-fns'

const SEVERITY_ORDER: Record<string, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 }

const SEVERITY_CHIPS: SeverityLevel[] = ['HIGH', 'MEDIUM', 'LOW']

const TYPE_LABELS: Record<string, string> = {
  narrative: 'Narrative',
  identifier_convergence: 'Identifier',
  source_health: 'Source',
}

/** Max signals shown inline before "View all" */
const INLINE_LIMIT = 5

interface SignalCardsProps {
  signals: IntelSignal[]
  onSelect: (signal: IntelSignal) => void
  onShowAll?: () => void
}

export function SignalCards({ signals, onSelect, onShowAll }: SignalCardsProps) {
  const [severityFilter, setSeverityFilter] = useState<Set<SeverityLevel>>(new Set())
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set())

  // Count signals per severity for summary bar
  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = { HIGH: 0, MEDIUM: 0, LOW: 0 }
    for (const sig of signals) {
      const sev = inferSeverityFromISC(sig.isc)
      counts[sev] = (counts[sev] ?? 0) + 1
    }
    return counts
  }, [signals])

  // Unique signal types present
  const signalTypes = useMemo(() => {
    const types = new Set<string>()
    for (const sig of signals) types.add(sig.signal_type)
    return Array.from(types)
  }, [signals])

  // Filter + sort: HIGH first, then MED, then LOW
  const filtered = useMemo(() => {
    let list = signals
    if (severityFilter.size > 0) {
      list = list.filter((s) => severityFilter.has(inferSeverityFromISC(s.isc)))
    }
    if (typeFilter.size > 0) {
      list = list.filter((s) => typeFilter.has(s.signal_type))
    }
    return [...list].sort((a, b) => {
      const sa = SEVERITY_ORDER[inferSeverityFromISC(a.isc)] ?? 9
      const sb = SEVERITY_ORDER[inferSeverityFromISC(b.isc)] ?? 9
      if (sa !== sb) return sa - sb
      return new Date(b.fired_at).getTime() - new Date(a.fired_at).getTime()
    })
  }, [signals, severityFilter, typeFilter])

  const toggleSeverity = (sev: SeverityLevel) => {
    setSeverityFilter((prev) => {
      const next = new Set(prev)
      if (next.has(sev)) next.delete(sev)
      else next.add(sev)
      return next
    })
  }

  const toggleType = (type: string) => {
    setTypeFilter((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  if (signals.length === 0) return null

  const inline = filtered.slice(0, INLINE_LIMIT)
  const hasMore = filtered.length > INLINE_LIMIT

  return (
    <section>
      {/* Summary header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[11px] font-bold text-text-muted uppercase tracking-widest">
          Signals
        </h2>
        <div className="flex items-center gap-2">
          {severityCounts.HIGH > 0 && (
            <span className="text-[10px] font-bold text-signal-high">
              {severityCounts.HIGH} HIGH
            </span>
          )}
          {severityCounts.MEDIUM > 0 && (
            <span className="text-[10px] font-bold text-signal-med">
              {severityCounts.MEDIUM} MED
            </span>
          )}
          <span className="text-[10px] text-text-muted">
            {severityCounts.LOW} LOW
          </span>
          <span className="text-[10px] text-text-muted">
            · {signals.length} total
          </span>
        </div>
      </div>

      {/* Filter chips */}
      <div className="flex flex-wrap items-center gap-1.5 mb-3">
        {SEVERITY_CHIPS.map((sev) => {
          const count = severityCounts[sev] ?? 0
          const active = severityFilter.has(sev)
          return (
            <button
              key={sev}
              onClick={() => toggleSeverity(sev)}
              disabled={count === 0}
              className={`px-2.5 py-1 rounded-full text-[10px] font-medium transition-colors ${
                active
                  ? 'bg-anveshak-accent text-white'
                  : count === 0
                    ? 'bg-anveshak-muted/50 text-text-muted/50 cursor-not-allowed'
                    : 'bg-anveshak-muted text-text-secondary hover:bg-anveshak-card hover:text-text-primary'
              }`}
            >
              {sev} ({count})
            </button>
          )
        })}

        {signalTypes.length > 1 && (
          <>
            <span className="mx-0.5 text-anveshak-border text-[10px]">|</span>
            {signalTypes.map((type) => {
              const active = typeFilter.has(type)
              return (
                <button
                  key={type}
                  onClick={() => toggleType(type)}
                  className={`px-2.5 py-1 rounded-full text-[10px] font-medium transition-colors ${
                    active
                      ? 'bg-anveshak-accent text-white'
                      : 'bg-anveshak-muted text-text-secondary hover:bg-anveshak-card hover:text-text-primary'
                  }`}
                >
                  {TYPE_LABELS[type] ?? type.replace(/_/g, ' ')}
                </button>
              )
            })}
          </>
        )}
      </div>

      {/* Signal cards (inline, max 5) */}
      {inline.length === 0 ? (
        <p className="text-xs text-text-muted py-3">No signals match current filters.</p>
      ) : (
        <div className="space-y-3">
          {inline.map((sig) => {
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
      )}

      {/* View all button */}
      {(hasMore || onShowAll) && (
        <div className="mt-3 text-center">
          <button
            onClick={onShowAll}
            className="text-[11px] text-anveshak-accent hover:underline"
          >
            View all {filtered.length} signals →
          </button>
        </div>
      )}
    </section>
  )
}
