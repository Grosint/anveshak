import { useState, useMemo } from 'react'
import type { IntelCluster } from '../../api/intelligence'
import { Badge } from '../ui/Badge'
import { deepfakeLabel } from '../../lib/domain'

/* Accent bar colors as Tailwind classes — mirrors CSS variable palette.
   Using classes instead of inline hex per theming rules. */
const ACCENT_BAR_CLASSES = [
  'bg-blue-500',    // var(--accent)
  'bg-violet-500',  // var(--accent-secondary)
  'bg-cyan-500',
  'bg-emerald-500',
  'bg-amber-500',
]

type StatusFilter = 'all' | 'open' | 'closed'

/** Max narratives shown inline before "View all" */
const INLINE_LIMIT = 5

interface NarrativeCardsProps {
  clusters: IntelCluster[]
  onSelect: (cluster: IntelCluster) => void
  onShowAll?: () => void
  totalCount?: number
}

export function NarrativeCards({ clusters, onSelect, onShowAll, totalCount }: NarrativeCardsProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')

  // A cluster is "open" if it has recent growth (growth_24h > 0 or growth_rate > 0)
  const isOpen = (c: IntelCluster) => (c.growth_24h ?? 0) > 0 || (c.growth_rate ?? 0) > 0

  const filtered = useMemo(() => {
    if (statusFilter === 'all') return clusters
    if (statusFilter === 'open') return clusters.filter(isOpen)
    return clusters.filter((c) => !isOpen(c))
  }, [clusters, statusFilter])

  const openCount = useMemo(() => clusters.filter(isOpen).length, [clusters])
  const closedCount = clusters.length - openCount

  if (clusters.length === 0) return null

  const inline = filtered.slice(0, INLINE_LIMIT)
  const total = totalCount ?? filtered.length

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[11px] font-bold text-text-muted uppercase tracking-widest">
          Narratives
        </h2>
      </div>

      {/* Filter chips */}
      <div className="flex items-center gap-1.5 mb-3">
        {([
          { key: 'all' as StatusFilter, label: `All (${clusters.length})` },
          { key: 'open' as StatusFilter, label: `Open (${openCount})` },
          { key: 'closed' as StatusFilter, label: `Closed (${closedCount})` },
        ]).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setStatusFilter(key)}
            className={`px-2.5 py-1 rounded-full text-[10px] font-medium transition-colors ${
              statusFilter === key
                ? 'bg-anveshak-accent text-white'
                : 'bg-anveshak-muted text-text-secondary hover:bg-anveshak-card hover:text-text-primary'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Narrative rows (inline, max 5) */}
      {inline.length === 0 ? (
        <p className="text-xs text-text-muted py-3">
          No {statusFilter === 'open' ? 'open' : 'closed'} narratives.
        </p>
      ) : (
        <div className="space-y-2">
          {inline.map((cluster, i) => {
            const barClass = ACCENT_BAR_CLASSES[i % ACCENT_BAR_CLASSES.length]
            const growthPct = cluster.growth_rate != null && cluster.growth_rate > 0
              ? Math.round(cluster.growth_rate * 100)
              : null
            return (
              <button
                key={cluster.id}
                onClick={() => onSelect(cluster)}
                className="w-full text-left relative overflow-hidden rounded-lg border border-anveshak-border bg-anveshak-card p-3 pl-4 hover:border-anveshak-accent/40 transition-all"
              >
                <div className={`absolute left-0 top-0 bottom-0 w-1 rounded-l-lg ${barClass}`} />
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold text-text-primary leading-snug">
                      {cluster.label ?? 'Unclassified cluster'}
                    </h3>
                    {cluster.executive_summary && (
                      <p className="text-xs text-text-secondary leading-relaxed mt-1 line-clamp-2">
                        {cluster.executive_summary}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant="accent">{cluster.item_count}</Badge>
                    <span className="text-[10px] text-text-muted">{cluster.isc} src</span>
                    {growthPct != null && (
                      <span className="text-[9px] text-cred-high font-bold">
                        +{growthPct}%
                      </span>
                    )}
                    {cluster.max_deepfake_score != null && cluster.max_deepfake_score >= 0.7 && (
                      <Badge variant="danger">⚠ {deepfakeLabel(cluster.max_deepfake_score).label}</Badge>
                    )}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      )}

      {/* View all button */}
      {(total > INLINE_LIMIT || onShowAll) && (
        <div className="mt-3 text-center">
          <button
            onClick={onShowAll}
            className="text-[11px] text-anveshak-accent hover:underline"
          >
            View all {total} narratives →
          </button>
        </div>
      )}
    </section>
  )
}
