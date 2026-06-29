import type { PipelineHealth } from '../../api/system'

function StatCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <p className="text-xs text-text-muted uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-text-primary mt-1">{value}</p>
      {sub && <p className="text-xs text-text-secondary mt-0.5">{sub}</p>}
    </div>
  )
}

interface KpiCardsProps {
  health: PipelineHealth
  activeTopics: number
}

export function KpiCards({ health, activeTopics }: KpiCardsProps) {
  const embedPct = health.content_items_total > 0
    ? Math.round((health.content_items_embedded / health.content_items_total) * 100)
    : 0

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      <StatCard
        label="Content Items"
        value={health.content_items_total.toLocaleString()}
        sub={`${health.content_items_last_24h} last 24h`}
      />
      <StatCard
        label="Embedding Coverage"
        value={`${embedPct}%`}
        sub={`${health.content_items_embedded.toLocaleString()} embedded`}
      />
      <StatCard label="Active Topics" value={activeTopics} />
      <StatCard label="Clusters" value={health.narrative_clusters_total.toLocaleString()} />
      <StatCard label="Signals (30d)" value={health.signals_last_30d} />
      <StatCard label="Reports (30d)" value={health.reports_last_30d} />
    </div>
  )
}
