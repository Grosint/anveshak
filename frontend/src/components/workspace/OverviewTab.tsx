import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { topicsApi } from '../../api/topics'
import { trackersApi } from '../../api/trackers'
import { signalsApi, Signal } from '../../api/signals'
import { identifiersApi } from '../../api/identifiers'
import { reportsApi } from '../../api/reports'
import { SentimentTrend } from '../topics/SentimentTrend'
import { TrendingKeywords } from '../topics/TrendingKeywords'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { inferSeverity } from '../../lib/domain'
import { formatDistanceToNow } from 'date-fns'

const severityVariant: Record<string, 'danger' | 'warning' | 'success' | 'default'> = {
  HIGH: 'danger', MEDIUM: 'warning', LOW: 'success',
}

const TYPE_COLORS: Record<string, string> = {
  PHONE_IN: 'text-green-400', PHONE_INTL: 'text-teal-400', UPI: 'text-purple-400', TELEGRAM_HANDLE: 'text-blue-400',
  CRYPTO_BTC: 'text-amber-400', EMAIL: 'text-cyan-400', GSTIN: 'text-orange-400',
  SEBI_REG: 'text-pink-400', URL_DOMAIN: 'text-violet-400',
  INSTAGRAM_HANDLE: 'text-rose-400', FACEBOOK_HANDLE: 'text-blue-500', X_HANDLE: 'text-slate-400',
  PAN: 'text-text-muted', IFSC: 'text-text-muted',
}

const TYPE_SHORT: Record<string, string> = {
  PHONE_IN: 'PHONE', PHONE_INTL: 'INTL', UPI: 'UPI', TELEGRAM_HANDLE: 'TELEGRAM', CRYPTO_BTC: 'BTC',
  CRYPTO_ETH: 'ETH', EMAIL: 'EMAIL', GSTIN: 'GSTIN', URL_DOMAIN: 'URL',
  SEBI_REG: 'SEBI', INSTAGRAM_HANDLE: 'INSTA', FACEBOOK_HANDLE: 'FB', X_HANDLE: 'X',
  PAN: 'PAN', IFSC: 'IFSC', BANK_ACCOUNT: 'BANK',
}

interface OverviewTabProps {
  topicId: string
  onSelectSignal: (signal: Signal) => void
  onNavigateTab: (tab: string) => void
  onViewReport: (reportId: string) => void
}

export default function OverviewTab({ topicId, onSelectSignal, onNavigateTab, onViewReport }: OverviewTabProps) {
  // Parallel data fetching
  const { data: clusters = [] } = useQuery({
    queryKey: ['clusters', topicId],
    queryFn: () => topicsApi.listClusters(topicId),
  })

  const { data: signalsPage } = useQuery({
    queryKey: ['signals-topic', topicId, 'new'],
    queryFn: () => signalsApi.listByTopic(topicId, 'new'),
  })
  const signals = signalsPage?.items ?? []

  const { data: identifiers = [] } = useQuery({
    queryKey: ['identifiers-top-overview', topicId],
    queryFn: () => identifiersApi.top(topicId, undefined, 10),
  })

  const { data: reportsData } = useQuery({
    queryKey: ['reports-history', topicId],
    queryFn: () => reportsApi.listForTopic(topicId),
  })
  const reports = reportsData?.items ?? []

  const topClusters = clusters.slice(0, 5)
  const latestReport = reports.find((r) => r.generated_at)

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      {/* Section: Active Narratives */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[11px] font-bold text-text-muted uppercase tracking-widest">
            Active Narratives
          </h2>
          {clusters.length > 5 && (
            <button onClick={() => onNavigateTab('clusters')} className="text-[10px] text-anveshak-accent hover:underline">
              View all {clusters.length} clusters
            </button>
          )}
        </div>

        {topClusters.length === 0 ? (
          <p className="text-sm text-text-muted">No narrative clusters detected yet.</p>
        ) : (
          <div className="space-y-2">
            {topClusters.map((cluster, i) => {
              const accentColors = ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b']
              const color = accentColors[i % accentColors.length]
              return (
                <div
                  key={cluster.id}
                  className="relative overflow-hidden rounded-lg border border-anveshak-border bg-anveshak-card p-3 pl-4"
                >
                  {/* Accent bar */}
                  <div
                    className="absolute left-0 top-0 bottom-0 w-1 rounded-l-lg"
                    style={{ backgroundColor: color }}
                  />
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
                      <span className="text-xs font-bold" style={{ color }}>{cluster.item_count}</span>
                      <span className="text-[10px] text-text-muted">{cluster.independent_source_count} src</span>
                    </div>
                  </div>
                  {/* Source chips */}
                  {cluster.sources?.length > 0 && (
                    <div className="flex gap-1 flex-wrap mt-2">
                      {cluster.sources.map((src, j) => (
                        <span key={j} className="text-[9px] bg-anveshak-muted rounded px-1.5 py-0.5 text-text-muted">
                          {src.platform.toUpperCase()} {src.source_name.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}
                        </span>
                      ))}
                    </div>
                  )}
                  {/* Tracker buttons */}
                  <ClusterTrackerButtons clusterId={cluster.id} />
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* 2-column: Signals + Identifiers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Signals */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[11px] font-bold text-text-muted uppercase tracking-widest">
              Signals
              {signals.length > 0 && (
                <span className="ml-2 text-signal-high bg-signal-high/20 rounded-full px-1.5 py-0.5 text-[9px]">
                  {signals.length} new
                </span>
              )}
            </h2>
          </div>

          {signals.length === 0 ? (
            <p className="text-sm text-text-muted">No active signals.</p>
          ) : (
            <div className="space-y-1.5">
              {signals.slice(0, 5).map((sig) => {
                const sev = inferSeverity(sig)
                return (
                  <button
                    key={sig.id}
                    onClick={() => onSelectSignal(sig)}
                    className="w-full text-left bg-anveshak-card border border-anveshak-border rounded-lg p-2.5 hover:border-anveshak-accent/40 transition-all"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant={severityVariant[sev] ?? 'default'} className="text-[9px] px-1.5 py-0">
                        {sev}
                      </Badge>
                      <span className="text-[10px] text-text-muted">
                        {sig.signal_type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-[10px] text-text-muted ml-auto">
                        {formatDistanceToNow(new Date(sig.created_at), { addSuffix: true })}
                      </span>
                    </div>
                    <p className="text-xs text-text-primary leading-snug line-clamp-2">
                      {sig.cluster_label || sig.description}
                    </p>
                    {sig.independent_source_count != null && (
                      <span className="text-[9px] text-text-muted mt-1 inline-block">
                        {sig.independent_source_count} independent sources · {sig.cluster_item_count ?? 0} items
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </section>

        {/* Top Identifiers */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[11px] font-bold text-text-muted uppercase tracking-widest">
              Top Identifiers
            </h2>
            {identifiers.length > 0 && (
              <button onClick={() => onNavigateTab('identifiers')} className="text-[10px] text-anveshak-accent hover:underline">
                View all
              </button>
            )}
          </div>

          {identifiers.length === 0 ? (
            <p className="text-sm text-text-muted">No identifiers extracted yet.</p>
          ) : (
            <div className="bg-anveshak-card border border-anveshak-border rounded-lg overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-anveshak-border/50 text-text-muted text-[9px] uppercase tracking-wider">
                    <th className="text-left py-2 px-3">Type</th>
                    <th className="text-left py-2 px-3">Value</th>
                    <th className="text-right py-2 px-3">Sources</th>
                    <th className="text-right py-2 px-3">Items</th>
                  </tr>
                </thead>
                <tbody>
                  {identifiers.map((id, i) => (
                    <tr key={`${id.identifier_type}-${id.identifier_value}-${i}`} className="border-b border-anveshak-border/30 last:border-0">
                      <td className="py-1.5 px-3">
                        <span className={`text-[9px] font-bold ${TYPE_COLORS[id.identifier_type] ?? 'text-text-muted'}`}>
                          {TYPE_SHORT[id.identifier_type] ?? id.identifier_type}
                        </span>
                      </td>
                      <td className="py-1.5 px-3 font-mono text-text-primary text-[11px] truncate max-w-[180px]">
                        {id.identifier_value}
                      </td>
                      <td className="py-1.5 px-3 text-right">
                        <span className={`font-bold ${id.source_count >= 3 ? 'text-signal-high' : 'text-text-primary'}`}>
                          {id.source_count}
                        </span>
                      </td>
                      <td className="py-1.5 px-3 text-right text-text-muted">{id.content_item_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {/* Sentiment + Keywords */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section>
          <SentimentTrend topicId={topicId} />
        </section>
        <section>
          <TrendingKeywords topicId={topicId} />
        </section>
      </div>

      {/* Latest Report */}
      {latestReport && (
        <section>
          <h2 className="text-[11px] font-bold text-text-muted uppercase tracking-widest mb-3">
            Latest Report
          </h2>
          <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Badge variant="ghost">{latestReport.report_type.replace(/_/g, ' ')}</Badge>
              {latestReport.confidence_score != null && (
                <Badge variant={latestReport.confidence_score >= 0.7 ? 'success' : 'warning'}>
                  {Math.round(latestReport.confidence_score * 100)}% confidence
                </Badge>
              )}
              {latestReport.content_item_count != null && (
                <span className="text-[11px] text-text-muted">{latestReport.content_item_count} items analyzed</span>
              )}
              <span className="text-[11px] text-text-muted">
                {latestReport.generated_at && formatDistanceToNow(new Date(latestReport.generated_at), { addSuffix: true })}
              </span>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" onClick={() => onViewReport(latestReport.id)}>
                View Report
              </Button>
              <Button size="sm" variant="ghost" onClick={() => onNavigateTab('reports')}>
                All Reports
              </Button>
            </div>
          </div>
        </section>
      )}

      {/* Quick action: Generate report if none exists */}
      {!latestReport && (
        <section>
          <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4 text-center">
            <p className="text-sm text-text-muted mb-2">No reports generated yet for this topic.</p>
            <Button size="sm" onClick={() => onNavigateTab('reports')}>
              Generate First Report
            </Button>
          </div>
        </section>
      )}
    </div>
  )
}


function ClusterTrackerButtons({ clusterId }: { clusterId: string }) {
  const navigate = useNavigate()
  const [creating, setCreating] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Check if a tracker already exists for this cluster
  const { data: trackersData } = useQuery({
    queryKey: ['trackers'],
    queryFn: () => trackersApi.list(),
    staleTime: 30_000,
  })
  const trackers = trackersData?.items ?? []
  const existing = trackers.find((t) => t.origin_cluster_id === clusterId)

  const handleCreate = async (status: 'watching' | 'active') => {
    setCreating(status)
    setError(null)
    try {
      const tracker = await trackersApi.createFromCluster(clusterId, { status })
      if (status === 'active') {
        navigate(`/trackers/${tracker.id}`)
      } else {
        navigate('/trackers')
      }
    } catch {
      setError('Failed to create tracker')
      setTimeout(() => setError(null), 3000)
    } finally {
      setCreating(null)
    }
  }

  if (existing) {
    return (
      <div className="flex gap-2 mt-2 pt-2 border-t border-anveshak-border">
        <span className="text-[10px] text-text-muted">
          Tracked as{' '}
          <button
            onClick={() => navigate(`/trackers/${existing.id}`)}
            className="text-anveshak-accent underline hover:no-underline"
          >
            {existing.case_number}
          </button>
          {' '}({existing.status})
        </span>
      </div>
    )
  }

  return (
    <div className="mt-2 pt-2 border-t border-anveshak-border">
      {error && <p className="text-[10px] text-red-400 mb-1">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={() => handleCreate('watching')}
          disabled={creating !== null}
          className="text-[10px] px-2 py-0.5 rounded text-text-muted hover:text-anveshak-accent hover:bg-anveshak-accent/10 transition-colors"
        >
          {creating === 'watching' ? 'Creating...' : 'Watch'}
        </button>
        <button
          onClick={() => handleCreate('active')}
          disabled={creating !== null}
          className="text-[10px] px-2 py-0.5 rounded bg-anveshak-accent/10 text-anveshak-accent hover:bg-anveshak-accent/20 transition-colors"
        >
          {creating === 'active' ? 'Creating...' : 'Open Tracker'}
        </button>
      </div>
    </div>
  )
}
