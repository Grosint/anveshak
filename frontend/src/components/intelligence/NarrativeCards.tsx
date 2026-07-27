import type { IntelCluster } from '../../api/intelligence'
import { Badge } from '../ui/Badge'

/* Accent bar colors as Tailwind classes — mirrors CSS variable palette.
   Using classes instead of inline hex per theming rules. */
const ACCENT_BAR_CLASSES = [
  'bg-blue-500',    // var(--accent)
  'bg-violet-500',  // var(--accent-secondary)
  'bg-cyan-500',
  'bg-emerald-500',
  'bg-amber-500',
]

interface NarrativeCardsProps {
  clusters: IntelCluster[]
  onSelect: (cluster: IntelCluster) => void
  onShowAll?: () => void
  totalCount?: number
}

export function NarrativeCards({ clusters, onSelect, onShowAll, totalCount }: NarrativeCardsProps) {
  if (clusters.length === 0) return null

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[11px] font-bold text-text-muted uppercase tracking-widest">
          Narratives
        </h2>
        {onShowAll && (totalCount ?? clusters.length) > clusters.length && (
          <button onClick={onShowAll} className="text-[10px] text-anveshak-accent hover:underline">
            Show all {totalCount ?? clusters.length} →
          </button>
        )}
      </div>
      <div className="space-y-2">
        {clusters.map((cluster, i) => {
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
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}
