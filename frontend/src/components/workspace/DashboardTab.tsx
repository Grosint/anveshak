import { useCallback, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import cytoscape from 'cytoscape'
import { intelligenceApi } from '../../api/intelligence'
import { signalsApi } from '../../api/signals'
import { alertsApi } from '../../api/alerts'
import { SentimentTrend } from '../topics/SentimentTrend'
import { TrendingKeywords } from '../topics/TrendingKeywords'
import { Spinner } from '../ui/Spinner'

// Recharts can't use CSS vars — hardcode hex matching theme
const CHART_COLORS = {
  bar: '#38bdf8',    // --anveshak-accent
  line: '#a78bfa',   // purple
  grid: '#1e293b',   // --anveshak-border
  tick: '#94a3b8',   // --text-muted
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <p className="text-xs text-text-muted uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-text-primary mt-1">{value}</p>
      {sub && <p className="text-xs text-text-secondary mt-0.5">{sub}</p>}
    </div>
  )
}

interface DashboardTabProps {
  topicId: string
}

export default function DashboardTab({ topicId }: DashboardTabProps) {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['topic-stats', topicId],
    queryFn: () => intelligenceApi.topicStats(topicId, 30),
    staleTime: 60_000,
  })

  const { data: authors, isLoading: authorsLoading } = useQuery({
    queryKey: ['top-authors', topicId],
    queryFn: () => intelligenceApi.topAuthors(topicId, 30, 10),
    staleTime: 60_000,
  })

  const { data: signals = [] } = useQuery({
    queryKey: ['signals', topicId, 'new'],
    queryFn: () => signalsApi.listByTopic(topicId, 'new'),
    staleTime: 30_000,
  })

  const { data: triggers = [] } = useQuery({
    queryKey: ['alert-triggers', topicId],
    queryFn: () => alertsApi.listTriggers(topicId, 10),
    staleTime: 30_000,
  })

  if (statsLoading) {
    return <div className="flex items-center justify-center h-64"><Spinner label="Loading dashboard..." /></div>
  }

  const eng = stats?.engagement
  const totalEng = (eng?.total_likes ?? 0) + (eng?.total_comments ?? 0) + (eng?.total_shares ?? 0)
  const totalPosts = stats?.platforms?.reduce((s, p) => s + p.post_count, 0) ?? 0
  const totalSources = stats?.platforms?.reduce((s, p) => s + p.source_count, 0) ?? 0

  return (
    <div className="space-y-6">
      {/* Stat cards row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Posts (30d)" value={totalPosts.toLocaleString()} />
        <StatCard label="Sources" value={totalSources} />
        <StatCard label="Signals" value={signals.length} sub="new / unread" />
        <StatCard label="Engagement" value={totalEng.toLocaleString()} sub={`${eng?.total_views?.toLocaleString() ?? 0} views`} />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Platform activity */}
        <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
          <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wide mb-3">
            Platform Activity
          </h3>
          {stats?.platforms && stats.platforms.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={stats.platforms} layout="vertical" margin={{ left: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis type="number" tick={{ fontSize: 10, fill: CHART_COLORS.tick }} />
                <YAxis dataKey="platform" type="category" tick={{ fontSize: 10, fill: CHART_COLORS.tick }} width={55} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '6px', fontSize: '11px' }}
                />
                <Bar dataKey="post_count" fill={CHART_COLORS.bar} name="Posts" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-xs text-text-muted">No platform data</div>
          )}
        </div>

        {/* Content volume timeline */}
        <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
          <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wide mb-3">
            Content Volume
          </h3>
          {stats?.volume_timeline && stats.volume_timeline.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={stats.volume_timeline}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: CHART_COLORS.tick }} tickFormatter={(v: string) => v.slice(5)} />
                <YAxis tick={{ fontSize: 10, fill: CHART_COLORS.tick }} width={32} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '6px', fontSize: '11px' }}
                />
                <Line type="monotone" dataKey="count" stroke={CHART_COLORS.line} strokeWidth={2} dot={{ r: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-xs text-text-muted">No volume data</div>
          )}
        </div>
      </div>

      {/* Charts row 2: reuse existing components */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SentimentTrend topicId={topicId} />
        <TrendingKeywords topicId={topicId} />
      </div>

      {/* Row 3: Influence Score + alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Influence Score Ranking */}
        <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
          <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wide mb-3">
            Influence Score
          </h3>
          {authorsLoading ? (
            <div className="h-40 flex items-center justify-center"><Spinner /></div>
          ) : !authors || authors.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-xs text-text-muted">No author data yet</div>
          ) : (() => {
            const scored = authors.map((a) => ({
              ...a,
              score: a.post_count * 1 + (a.total_likes || 0) * 0.5 + (a.total_shares || 0) * 2 + (a.total_views || 0) * 0.01,
            })).sort((x, y) => y.score - x.score)
            const maxScore = scored[0]?.score || 1
            return (
              <div className="space-y-1.5 max-h-[260px] overflow-y-auto">
                {scored.map((a, i) => {
                  const sentColor = a.avg_sentiment > 0.05 ? '#22c55e' : a.avg_sentiment < -0.05 ? '#ef4444' : '#94a3b8'
                  return (
                    <div key={`${a.author_handle}-${a.platform}`} className="text-xs">
                      <div className="flex items-center justify-between mb-0.5">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-text-muted w-4 text-right font-mono">{i + 1}</span>
                          <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: sentColor }} />
                          <span className="text-text-primary font-medium truncate">{a.author_handle}</span>
                          <span className="text-text-muted px-1 py-0.5 rounded bg-anveshak-muted text-[8px]">{a.platform}</span>
                        </div>
                        <span className="text-anveshak-accent font-mono font-bold tabular-nums">{Math.round(a.score).toLocaleString()}</span>
                      </div>
                      <div className="ml-6 flex items-center gap-2">
                        <div className="flex-1 h-1.5 rounded-full bg-anveshak-border overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${(a.score / maxScore) * 100}%`,
                              backgroundColor: `color-mix(in srgb, var(--anveshak-accent) ${Math.round(30 + (a.score / maxScore) * 70)}%, transparent)`,
                            }}
                          />
                        </div>
                        <span className="text-[9px] text-text-muted tabular-nums shrink-0">{a.post_count}p · {(a.total_likes || 0).toLocaleString()}l · {(a.total_shares || 0).toLocaleString()}s</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )
          })()}
        </div>

        {/* Active alerts */}
        <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
          <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wide mb-3">
            Recent Keyword Alerts
          </h3>
          {triggers.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-xs text-text-muted">
              No keyword alerts configured or triggered
            </div>
          ) : (
            <div className="space-y-2 max-h-[240px] overflow-y-auto">
              {triggers.map((t) => (
                <div key={t.id} className="text-xs py-1.5 border-b border-anveshak-border/50 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className="text-red-400 font-medium">
                      {t.matched_keywords.join(', ')}
                    </span>
                    <span className="text-text-muted">
                      {new Date(t.triggered_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-text-secondary mt-0.5 truncate">{t.content_snippet}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Row 4: Forwarding Network Graph */}
      {/* Row 5: Forwarding Network + Influence Matrix */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ForwardingNetwork topicId={topicId} />
        </div>
        <InfluenceMatrix topicId={topicId} />
      </div>
    </div>
  )
}


const PLATFORM_COLORS: Record<string, string> = {
  telegram: '#38bdf8',
  instagram: '#e879f9',
  web: '#94a3b8',
  rss: '#a3e635',
  reddit: '#f97316',
  twitter: '#60a5fa',
  bluesky: '#818cf8',
  unknown: '#64748b',
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CY_STYLE: any[] = [
  { selector: 'node', style: {
    label: 'data(label)',
    'text-valign': 'bottom',
    'text-halign': 'center',
    'font-size': 10,
    'font-weight': 600,
    color: '#e2e8f0',
    'text-margin-y': 6,
    'text-outline-color': '#0f172a',
    'text-outline-width': 2,
    'background-color': 'data(color)',
    width: 'data(size)',
    height: 'data(size)',
    'border-width': 2,
    'border-color': '#334155',
  }},
  { selector: 'edge', style: {
    width: 'data(thickness)',
    'line-color': 'data(edgeColor)',
    'target-arrow-color': 'data(edgeColor)',
    'target-arrow-shape': 'triangle',
    'arrow-scale': 1.3,
    'curve-style': 'bezier',
    opacity: 0.9,
    label: 'data(edgeLabel)',
    'font-size': 10,
    'font-weight': 700,
    color: '#f8fafc',
    'text-background-color': '#0f172a',
    'text-background-opacity': 0.8,
    'text-background-padding': '2px',
    'text-rotation': 'autorotate',
  }},
  { selector: 'node:active, node:selected', style: {
    'border-color': '#38bdf8',
    'border-width': 3,
  }},
]

function ForwardingNetwork({ topicId }: { topicId: string }) {
  const cyContainer = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)

  const { data: graph, isLoading } = useQuery({
    queryKey: ['network-graph', topicId],
    queryFn: () => intelligenceApi.networkGraph(topicId, 1, 200),
    staleTime: 120_000,
  })

  const initGraph = useCallback(() => {
    if (!cyContainer.current || !graph || graph.edges.length === 0) return
    if (cyRef.current) cyRef.current.destroy()

    // Only show nodes that participate in at least one edge
    const connectedIds = new Set<string>()
    graph.edges.forEach((e) => { connectedIds.add(e.source); connectedIds.add(e.target) })
    const connectedNodes = graph.nodes.filter((n) => connectedIds.has(n.id))
    // Add missing nodes referenced by edges but not in nodes list
    graph.edges.forEach((e) => {
      if (!connectedNodes.find((n) => n.id === e.source))
        connectedNodes.push({ id: e.source, platform: 'unknown', post_count: 0 })
      if (!connectedNodes.find((n) => n.id === e.target))
        connectedNodes.push({ id: e.target, platform: 'unknown', post_count: 0 })
    })

    const maxPosts = Math.max(...connectedNodes.map((n) => n.post_count), 1)
    const maxWeight = Math.max(...graph.edges.map((e) => e.weight), 1)

    const elements: cytoscape.ElementDefinition[] = [
      ...connectedNodes.map((n) => ({
        data: {
          id: n.id,
          label: n.id,
          color: PLATFORM_COLORS[n.platform] || PLATFORM_COLORS.unknown,
          size: 22 + (n.post_count / maxPosts) * 35,
        },
      })),
      ...graph.edges.map((e, i) => ({
        data: {
          id: `e-${i}`,
          source: e.source,
          target: e.target,
          thickness: 1.5 + (e.weight / maxWeight) * 4,
          edgeColor: e.weight >= 4 ? '#f59e0b' : e.weight >= 2 ? '#38bdf8' : '#64748b',
          edgeLabel: `${e.weight}x`,
        },
      })),
    ]

    cyRef.current = cytoscape({
      container: cyContainer.current,
      elements,
      style: CY_STYLE,
      layout: {
        name: 'cose',
        nodeRepulsion: () => 8000,
        idealEdgeLength: () => 150,
        gravity: 0.4,
        numIter: 300,
        animate: true,
        animationDuration: 600,
      } as cytoscape.LayoutOptions,
      minZoom: 0.3,
      maxZoom: 3,
    })

    cyRef.current.on('tap', 'node', (evt) => {
      const node = evt.target
      cyRef.current?.elements().style({ opacity: 0.2 })
      node.style({ opacity: 1 })
      node.neighborhood().style({ opacity: 1 })
    })
    cyRef.current.on('tap', (evt) => {
      if (evt.target === cyRef.current) {
        cyRef.current?.elements().style({ opacity: 1 })
      }
    })
  }, [graph])

  useEffect(() => {
    initGraph()
    return () => { cyRef.current?.destroy() }
  }, [initGraph])

  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wide mb-3">
        Forwarding Network
      </h3>
      {isLoading ? (
        <div className="h-[320px] flex items-center justify-center"><Spinner /></div>
      ) : !graph || graph.nodes.length === 0 ? (
        <div className="h-[320px] flex items-center justify-center text-xs text-text-muted">
          No forwarding data detected
        </div>
      ) : (
        <>
          <p className="text-[10px] text-text-muted mb-2">
            {graph.node_count} authors · {graph.edge_count} forwarding chains · click node to highlight
          </p>
          <div ref={cyContainer} className="h-[320px] w-full rounded border border-anveshak-border/50" />
        </>
      )}
    </div>
  )
}


function InfluenceMatrix({ topicId }: { topicId: string }) {
  const { data: graph } = useQuery({
    queryKey: ['network-graph', topicId],
    queryFn: () => intelligenceApi.networkGraph(topicId, 1, 200),
    staleTime: 120_000,
  })

  if (!graph || graph.edges.length === 0) {
    return (
      <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
        <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wide mb-3">
          Influence Matrix
        </h3>
        <div className="h-[320px] flex items-center justify-center text-xs text-text-muted">
          No forwarding data
        </div>
      </div>
    )
  }

  // Build matrix: origin (source) → forwarder (target)
  const origins = new Set<string>()
  const forwarders = new Set<string>()
  const weights = new Map<string, number>()

  graph.edges.forEach((e) => {
    origins.add(e.source)
    forwarders.add(e.target)
    weights.set(`${e.source}→${e.target}`, e.weight)
  })

  const originList = [...origins].sort()
  const forwarderList = [...forwarders].sort()
  const maxWeight = Math.max(...graph.edges.map((e) => e.weight), 1)

  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wide mb-3">
        Influence Matrix
      </h3>
      <p className="text-[9px] text-text-muted mb-3">Origin → Forwarder · cell = forwarding count</p>
      <div className="overflow-auto">
        <table className="text-[10px] w-full">
          <thead>
            <tr>
              <th className="text-left text-text-muted font-normal p-1 border-b border-anveshak-border">Origin ↓</th>
              {forwarderList.map((f) => (
                <th key={f} className="text-center text-text-muted font-normal p-1 border-b border-anveshak-border whitespace-nowrap">
                  {f.length > 12 ? f.slice(0, 10) + '…' : f}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {originList.map((o) => (
              <tr key={o}>
                <td className="text-text-primary font-medium p-1 border-b border-anveshak-border/30 whitespace-nowrap">
                  {o.length > 14 ? o.slice(0, 12) + '…' : o}
                </td>
                {forwarderList.map((f) => {
                  const w = weights.get(`${o}→${f}`) || 0
                  const intensity = w / maxWeight
                  return (
                    <td key={f} className="text-center p-1 border-b border-anveshak-border/30">
                      {w > 0 ? (
                        <span
                          className="inline-block w-7 h-7 rounded flex items-center justify-center text-[10px] font-bold"
                          style={{
                            backgroundColor: `color-mix(in srgb, #38bdf8 ${Math.round(intensity * 100)}%, transparent)`,
                            color: intensity > 0.5 ? '#0f172a' : '#e2e8f0',
                          }}
                        >
                          {w}
                        </span>
                      ) : (
                        <span className="text-text-muted/30">·</span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
