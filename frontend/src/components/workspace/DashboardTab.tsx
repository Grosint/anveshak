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

      {/* Row 3: Top authors + alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top authors */}
        <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
          <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wide mb-3">
            Top Authors
          </h3>
          {authorsLoading ? (
            <div className="h-40 flex items-center justify-center"><Spinner /></div>
          ) : !authors || authors.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-xs text-text-muted">No author data yet</div>
          ) : (
            <div className="space-y-2 max-h-[240px] overflow-y-auto">
              {authors.map((a, i) => (
                <div key={`${a.author_handle}-${a.platform}`} className="flex items-center justify-between text-xs py-1.5 border-b border-anveshak-border/50 last:border-0">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-text-muted w-4 text-right">{i + 1}</span>
                    <span className="text-text-primary font-medium truncate">{a.author_handle}</span>
                    <span className="text-text-muted px-1.5 py-0.5 rounded bg-anveshak-muted text-[9px]">{a.platform}</span>
                  </div>
                  <div className="flex gap-3 text-text-secondary tabular-nums">
                    <span>{a.post_count} posts</span>
                    <span>{a.total_likes.toLocaleString()} likes</span>
                  </div>
                </div>
              ))}
            </div>
          )}
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
      <ForwardingNetwork topicId={topicId} />
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
    'font-size': 9,
    color: '#cbd5e1',
    'text-margin-y': 4,
    'background-color': 'data(color)',
    width: 'data(size)',
    height: 'data(size)',
    'border-width': 1,
    'border-color': '#334155',
  }},
  { selector: 'edge', style: {
    width: 'data(weight)',
    'line-color': '#475569',
    'target-arrow-color': '#475569',
    'target-arrow-shape': 'triangle',
    'curve-style': 'bezier',
    opacity: 0.7,
  }},
  { selector: 'node:active, node:selected', style: {
    'border-color': '#38bdf8',
    'border-width': 2,
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
    if (!cyContainer.current || !graph || graph.nodes.length === 0) return
    if (cyRef.current) cyRef.current.destroy()

    const maxPosts = Math.max(...graph.nodes.map((n) => n.post_count), 1)

    const elements: cytoscape.ElementDefinition[] = [
      ...graph.nodes.map((n) => ({
        data: {
          id: n.id,
          label: n.id.length > 18 ? n.id.slice(0, 16) + '…' : n.id,
          color: PLATFORM_COLORS[n.platform] || PLATFORM_COLORS.unknown,
          size: 16 + (n.post_count / maxPosts) * 30,
        },
      })),
      ...graph.edges.map((e, i) => ({
        data: {
          id: `e-${i}`,
          source: e.source,
          target: e.target,
          weight: Math.min(e.weight, 6),
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
