import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { systemApi } from '../api/system'
import { topicsApi, Topic } from '../api/topics'
import { Spinner } from '../components/ui/Spinner'
import { Badge } from '../components/ui/Badge'

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

function TopicCard({ topic, onClick }: { topic: Topic; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="bg-anveshak-card border border-anveshak-border rounded-lg p-4 text-left hover:border-anveshak-accent transition-colors w-full"
    >
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-text-primary truncate">{topic.name}</p>
        <Badge variant={topic.status === 'active' ? 'success' : 'default'}>{topic.status}</Badge>
      </div>
      <div className="flex gap-4 mt-2 text-xs text-text-muted">
        <span>{topic.content_count ?? 0} items</span>
        <span>{topic.signal_count ?? 0} signals</span>
      </div>
    </button>
  )
}

export default function AnalyticsDashboard() {
  const navigate = useNavigate()

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['pipeline-health'],
    queryFn: systemApi.pipelineHealth,
    refetchInterval: 30_000,
  })

  const { data: topics = [], isLoading: topicsLoading } = useQuery({
    queryKey: ['topics'],
    queryFn: topicsApi.list,
  })

  const isLoading = healthLoading || topicsLoading

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border">
        <h1 className="text-xl font-semibold text-text-primary">Analytics</h1>
        <p className="text-sm text-text-muted mt-0.5">Pipeline health and topic overview</p>
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

            {/* Topic overview */}
            <div>
              <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
                Topics ({topics.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {topics.map((t) => (
                  <TopicCard
                    key={t.id}
                    topic={t}
                    onClick={() => navigate(`/topics/${t.id}/feed`)}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
