import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts'
import { systemApi } from '../api/system'
import { sourcesApi } from '../api/sources'
import { identifiersApi, type ConvergenceResult } from '../api/identifiers'
import { Spinner } from '../components/ui/Spinner'
import IdentifierSearch from '../components/search/IdentifierSearch'

function StatCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <p className="text-xs text-text-muted uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-text-primary mt-1">{value}</p>
      {sub && <p className="text-xs text-text-secondary mt-0.5">{sub}</p>}
    </div>
  )
}

function SourceHealthBar({ active, down }: { active: number; down: number }) {
  const total = active + down
  const pct = total > 0 ? Math.round((active / total) * 100) : 100
  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <p className="text-xs text-text-muted uppercase tracking-wide">Source Health</p>
      <div className="flex items-baseline gap-2 mt-1">
        <span className="text-2xl font-bold text-cred-high">{active}</span>
        <span className="text-sm text-text-muted">active</span>
        {down > 0 && (
          <>
            <span className="text-2xl font-bold text-signal-high">{down}</span>
            <span className="text-sm text-text-muted">down</span>
          </>
        )}
      </div>
      <div className="mt-2 h-1.5 bg-anveshak-muted rounded-full overflow-hidden">
        <div className="h-full bg-cred-high rounded-full" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

const HEALTH_COLORS: Record<string, string> = {
  healthy: '#10b981',
  degraded: '#f59e0b',
  down: '#ef4444',
  unverified: '#6b7280',
}

const ACCENT_COLOR = '#3b82f6'

interface ChartTooltipProps {
  active?: boolean
  payload?: { name?: string; value?: number }[]
  label?: string
}

function ChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-[#0f172a] border border-[#334155] rounded px-3 py-2 text-xs">
      <p className="text-text-primary font-medium">{label || payload[0]?.name}</p>
      <p className="text-text-muted">{payload[0]?.value}</p>
    </div>
  )
}

export default function AnalyticsDashboard() {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['pipeline-health'],
    queryFn: systemApi.pipelineHealth,
    refetchInterval: 30_000,
  })

  const { data: sources = [], isLoading: sourcesLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: sourcesApi.list,
    staleTime: 30_000,
  })

  const { data: convergence = [] } = useQuery({
    queryKey: ['identifier-convergence'],
    queryFn: () => identifiersApi.convergence(),
    staleTime: 60_000,
  })

  const isLoading = healthLoading || sourcesLoading

  function handleConvergenceClick(item: ConvergenceResult) {
    setSearchQuery(item.identifier_value)
    setSearchOpen(true)
  }

  // Derive chart data from sources
  const healthDistribution = useMemo(() => {
    const counts: Record<string, number> = {}
    sources.forEach((s) => {
      counts[s.health_status] = (counts[s.health_status] ?? 0) + 1
    })
    return Object.entries(counts).map(([status, count]) => ({
      name: status.charAt(0).toUpperCase() + status.slice(1),
      value: count,
      color: HEALTH_COLORS[status] ?? '#6b7280',
    }))
  }, [sources])

  const platformDistribution = useMemo(() => {
    const counts: Record<string, number> = {}
    sources.forEach((s) => {
      counts[s.platform] = (counts[s.platform] ?? 0) + 1
    })
    return Object.entries(counts)
      .map(([platform, count]) => ({ name: platform, count }))
      .sort((a, b) => b.count - a.count)
  }, [sources])

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border">
        <h1 className="text-xl font-semibold text-text-primary">Analytics</h1>
        <p className="text-sm text-text-muted mt-0.5">Pipeline health and source overview</p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Spinner label="Loading metrics..." />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Pipeline stats */}
            {health && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                  <StatCard label="Content Items" value={health.content_items_total} sub={`${health.content_items_last_24h} last 24h`} />
                  <StatCard label="Embedded" value={health.content_items_embedded} sub={`${Math.round((health.content_items_embedded / Math.max(health.content_items_total, 1)) * 100)}% coverage`} />
                  <StatCard label="Clusters" value={health.narrative_clusters_total} />
                  <StatCard label="Signals (30d)" value={health.signals_last_30d} />
                  <StatCard label="Reports (30d)" value={health.reports_last_30d} />
                  <SourceHealthBar active={health.sources_active} down={health.sources_down} />
                </div>

                {/* Multilingual */}
                {health.content_items_zh > 0 && (
                  <div className="grid grid-cols-3 gap-3">
                    <StatCard label="Chinese Content" value={health.content_items_zh} />
                    <StatCard label="Translated" value={health.content_items_translated} />
                    <StatCard label="Entities from ZH" value={health.extracted_entities_zh} />
                  </div>
                )}
              </>
            )}

            {/* Charts row */}
            {sources.length > 0 && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Source Health Distribution — Donut */}
                <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
                  <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
                    Source Health Distribution
                  </h2>
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={healthDistribution}
                          cx="50%"
                          cy="50%"
                          innerRadius={45}
                          outerRadius={75}
                          paddingAngle={2}
                          dataKey="value"
                          nameKey="name"
                        >
                          {healthDistribution.map((entry, i) => (
                            <Cell key={i} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip content={<ChartTooltip />} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  {/* Legend */}
                  <div className="flex flex-wrap gap-3 mt-2 justify-center">
                    {healthDistribution.map((entry) => (
                      <div key={entry.name} className="flex items-center gap-1.5 text-xs text-text-muted">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: entry.color }} />
                        {entry.name} ({entry.value})
                      </div>
                    ))}
                  </div>
                </div>

                {/* Platform Distribution — Bar Chart */}
                <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
                  <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
                    Sources by Platform
                  </h2>
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={platformDistribution} layout="vertical" margin={{ left: 10, right: 20 }}>
                        <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} allowDecimals={false} />
                        <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} width={70} />
                        <Tooltip content={<ChartTooltip />} />
                        <Bar dataKey="count" fill={ACCENT_COLOR} radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}

            {/* Source details table */}
            {sources.length > 0 && (
              <div className="bg-anveshak-card border border-anveshak-border rounded-lg overflow-hidden">
                <div className="px-4 py-3 border-b border-anveshak-border">
                  <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
                    All Sources ({sources.length})
                  </h2>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-anveshak-border text-left text-xs text-text-muted uppercase tracking-wide">
                      <th className="px-4 py-2.5">Name</th>
                      <th className="px-4 py-2.5">Platform</th>
                      <th className="px-4 py-2.5">Health</th>
                      <th className="px-4 py-2.5">Credibility</th>
                      <th className="px-4 py-2.5">Topics</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sources.map((s) => (
                      <tr key={s.id} className="border-b border-anveshak-border last:border-0 hover:bg-anveshak-muted/30 transition-colors">
                        <td className="px-4 py-2.5 text-text-primary font-medium truncate max-w-[200px]">{s.name}</td>
                        <td className="px-4 py-2.5 text-text-muted">{s.platform}</td>
                        <td className="px-4 py-2.5">
                          <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                            s.health_status === 'healthy' ? 'text-cred-high' :
                            s.health_status === 'degraded' ? 'text-yellow-400' :
                            s.health_status === 'down' ? 'text-signal-high' : 'text-text-muted'
                          }`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${
                              s.health_status === 'healthy' ? 'bg-cred-high' :
                              s.health_status === 'degraded' ? 'bg-yellow-400' :
                              s.health_status === 'down' ? 'bg-signal-high' : 'bg-text-muted'
                            }`} />
                            {s.health_status}
                          </span>
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-anveshak-muted rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  s.credibility_score >= 70 ? 'bg-cred-high' :
                                  s.credibility_score >= 40 ? 'bg-cred-mid' : 'bg-cred-low'
                                }`}
                                style={{ width: `${s.credibility_score}%` }}
                              />
                            </div>
                            <span className="text-xs text-text-muted">{s.credibility_score}</span>
                          </div>
                        </td>
                        <td className="px-4 py-2.5 text-text-muted text-xs">{s.topic_links_count ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Cross-topic convergence */}
            {convergence.length > 0 && (
              <div className="bg-anveshak-card border border-anveshak-border rounded-lg overflow-hidden">
                <div className="px-4 py-3 border-b border-anveshak-border">
                  <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
                    Cross-Topic Convergence
                  </h2>
                  <p className="text-xs text-text-muted mt-0.5">Identifiers appearing in 2+ topics</p>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-anveshak-border text-left text-xs text-text-muted uppercase tracking-wide">
                      <th className="px-4 py-2.5">Type</th>
                      <th className="px-4 py-2.5">Value</th>
                      <th className="px-4 py-2.5">Topics</th>
                      <th className="px-4 py-2.5">Appears In</th>
                    </tr>
                  </thead>
                  <tbody>
                    {convergence.map((item, i) => (
                      <tr
                        key={`${item.identifier_value}-${i}`}
                        onClick={() => handleConvergenceClick(item)}
                        className="border-b border-anveshak-border last:border-0 hover:bg-anveshak-accent/10 cursor-pointer transition-colors"
                      >
                        <td className="px-4 py-2.5">
                          <span className="text-[10px] font-medium bg-gray-500/20 text-gray-400 px-1.5 py-0.5 rounded">
                            {item.identifier_type.replace(/_/g, ' ')}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 font-mono text-text-primary text-xs">{item.identifier_value}</td>
                        <td className="px-4 py-2.5">
                          <span className="text-xs font-bold text-signal-high">{item.topic_count} topics</span>
                        </td>
                        <td className="px-4 py-2.5 text-xs text-text-muted truncate max-w-[300px]">
                          {item.topic_names.join(', ')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Identifier search modal (triggered from convergence card click) */}
      <IdentifierSearch
        open={searchOpen}
        onClose={() => { setSearchOpen(false); setSearchQuery('') }}
        initialQuery={searchQuery}
      />
    </div>
  )
}
