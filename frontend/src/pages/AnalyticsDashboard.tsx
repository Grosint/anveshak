import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { systemApi } from '../api/system'
import { identifiersApi, type ConvergenceResult } from '../api/identifiers'
import { Spinner } from '../components/ui/Spinner'
import IdentifierSearch from '../components/search/IdentifierSearch'
import { TimeFilterBar } from '../components/analytics/TimeFilterBar'
import { KpiCards } from '../components/analytics/KpiCards'
import { ContentVolumeTrend } from '../components/analytics/ContentVolumeTrend'
import { SignalActivityTrend } from '../components/analytics/SignalActivityTrend'
import { TopEntitiesChart } from '../components/analytics/TopEntitiesChart'
import { SentimentOverview } from '../components/analytics/SentimentOverview'
import { PlatformBreakdownChart } from '../components/analytics/PlatformBreakdownChart'
import { LanguageBreakdownChart } from '../components/analytics/LanguageBreakdownChart'
import { RecentActivityFeed } from '../components/analytics/RecentActivityFeed'

export default function AnalyticsDashboard({ embedded = false }: { embedded?: boolean }) {
  const [days, setDays] = useState(30)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['pipeline-health'],
    queryFn: systemApi.pipelineHealth,
    refetchInterval: 60_000,
  })

  const { data: dashboard, isLoading: dashboardLoading } = useQuery({
    queryKey: ['analytics-dashboard', days],
    queryFn: () => systemApi.analyticsDashboard(days),
    refetchInterval: 60_000,
  })

  const { data: convergence = [] } = useQuery({
    queryKey: ['identifier-convergence'],
    queryFn: () => identifiersApi.convergence(),
    staleTime: 60_000,
  })

  const isLoading = healthLoading || dashboardLoading

  function handleConvergenceClick(item: ConvergenceResult) {
    setSearchQuery(item.identifier_value)
    setSearchOpen(true)
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      {!embedded ? (
        <div className="px-6 pt-6 pb-4 border-b border-anveshak-border flex items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-text-primary">Intelligence Dashboard</h1>
            <p className="text-sm text-text-muted mt-0.5">Cross-topic intelligence overview</p>
          </div>
          <TimeFilterBar days={days} onChange={setDays} />
        </div>
      ) : (
        <div className="px-4 pt-3 pb-3 border-b border-anveshak-border flex justify-end">
          <TimeFilterBar days={days} onChange={setDays} />
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Spinner label="Loading intelligence metrics..." />
          </div>
        ) : (
          <div className="space-y-6">
            {/* KPI Cards */}
            {health && (
              <KpiCards health={health} activeTopics={dashboard?.active_topics ?? 0} />
            )}

            {/* Trend Charts */}
            {dashboard && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <ContentVolumeTrend data={dashboard.content_volume_trend} />
                <SignalActivityTrend data={dashboard.signal_activity_trend} />
              </div>
            )}

            {/* Intelligence Breakdown */}
            {dashboard && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="space-y-4">
                  <TopEntitiesChart data={dashboard.top_entities} />
                  <SentimentOverview data={dashboard.sentiment_distribution} />
                </div>
                <div className="space-y-4">
                  <PlatformBreakdownChart data={dashboard.content_by_platform} />
                  <LanguageBreakdownChart data={dashboard.content_by_language} />
                </div>
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

            {/* Recent Activity */}
            {dashboard && (
              <RecentActivityFeed data={dashboard.recent_activity} />
            )}
          </div>
        )}
      </div>

      {/* Identifier search modal */}
      <IdentifierSearch
        open={searchOpen}
        onClose={() => { setSearchOpen(false); setSearchQuery('') }}
        initialQuery={searchQuery}
      />
    </div>
  )
}
