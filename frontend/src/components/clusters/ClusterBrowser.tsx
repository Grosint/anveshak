import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { topicsApi, Cluster, ClusterContentItem } from '../../api/topics'
import { Badge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'
import { EmptyState } from '../ui/EmptyState'
import { SentimentBadge } from '../content/SentimentBadge'

const TIER_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  high:    { bg: 'bg-emerald-500/20', text: 'text-emerald-400', label: 'High' },
  medium:  { bg: 'bg-amber-500/20',   text: 'text-amber-400',   label: 'Medium' },
  low:     { bg: 'bg-red-500/20',     text: 'text-red-400',     label: 'Low' },
  keyword: { bg: 'bg-blue-500/20',    text: 'text-blue-400',    label: 'Keyword' },
}

function RelevanceBadge({ tier }: { tier?: string | null }) {
  if (!tier) return null
  const style = TIER_STYLES[tier] ?? TIER_STYLES.low
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  )
}

interface ClusterBrowserProps {
  topicId: string
  onSelectContent: (contentId: string, title?: string) => void
}

export function ClusterBrowser({ topicId, onSelectContent }: ClusterBrowserProps) {
  const [searchQ, setSearchQ] = useState('')
  const [searchActive, setSearchActive] = useState(false)
  const [expandedClusterId, setExpandedClusterId] = useState<string | null>(null)
  const [drilldownSort, setDrilldownSort] = useState<'time' | 'relevance'>('time')

  // Browse clusters
  const { data: clusters = [], isLoading } = useQuery({
    queryKey: ['clusters', topicId],
    queryFn: () => topicsApi.listClusters(topicId),
    enabled: !!topicId && !searchActive,
  })

  // Search clusters
  const { data: narrativeResults = [], isFetching: isSearching } = useQuery({
    queryKey: ['cluster-search', topicId, searchQ],
    queryFn: () => topicsApi.searchClusters(topicId, searchQ),
    enabled: searchActive && !!searchQ && !!topicId,
    staleTime: 60_000,
  })

  // Drilldown content
  const { data: clusterContent = [], isFetching: isDrilldownLoading } = useQuery({
    queryKey: ['cluster-content', topicId, expandedClusterId, drilldownSort, searchActive ? searchQ : ''],
    queryFn: () => topicsApi.getClusterContent(topicId, expandedClusterId!, {
      q: searchActive ? searchQ : undefined,
      sort: searchActive && searchQ ? drilldownSort : 'time',
      limit: 50,
    }),
    enabled: !!topicId && !!expandedClusterId,
  })

  const displayClusters: Cluster[] = searchActive ? narrativeResults : clusters

  const handleClusterClick = (id: string) => {
    if (expandedClusterId === id) {
      setExpandedClusterId(null)
    } else {
      setExpandedClusterId(id)
      setDrilldownSort(searchActive && searchQ ? 'relevance' : 'time')
    }
  }

  return (
    <div className="p-4">
      {/* Search bar */}
      <div className="flex gap-2 items-center mb-4">
        <input
          type="search"
          value={searchQ}
          onChange={(e) => setSearchQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && searchQ.trim()) setSearchActive(true)
            if (e.key === 'Escape') { setSearchActive(false); setSearchQ(''); setExpandedClusterId(null) }
          }}
          placeholder="Search narratives..."
          className="flex-1 bg-anveshak-card border border-anveshak-border rounded px-3 py-1.5 text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent"
        />
        {searchActive ? (
          <button
            onClick={() => { setSearchActive(false); setSearchQ(''); setExpandedClusterId(null) }}
            className="text-xs text-text-muted hover:text-text-primary px-2 py-1"
          >
            Clear
          </button>
        ) : (
          <button
            onClick={() => { if (searchQ.trim()) setSearchActive(true) }}
            disabled={!searchQ.trim()}
            className="text-xs text-anveshak-accent disabled:text-text-muted px-2 py-1"
          >
            Search
          </button>
        )}
      </div>

      {isLoading || isSearching ? (
        <div className="flex justify-center py-20">
          <Spinner label={isSearching ? 'Searching narratives...' : 'Loading clusters...'} />
        </div>
      ) : displayClusters.length === 0 ? (
        <EmptyState
          icon="📊"
          title={searchActive ? 'No matching narratives' : 'No clusters yet'}
          description={searchActive ? 'Try different keywords.' : 'Clusters emerge when enough content is analyzed.'}
        />
      ) : (
        <div className="max-w-3xl space-y-3">
          {/* Summary */}
          <div className="flex items-center gap-3 text-[10px] text-text-muted px-1">
            <span>
              {searchActive
                ? `${displayClusters.length} matching narrative${displayClusters.length !== 1 ? 's' : ''}`
                : `${displayClusters.length} cluster${displayClusters.length !== 1 ? 's' : ''}`}
            </span>
            <span className="text-anveshak-border">|</span>
            <span>{displayClusters.reduce((s, c) => s + c.item_count, 0)} total items</span>
          </div>

          {displayClusters.map((cluster) => {
            const isExpanded = expandedClusterId === cluster.id
            return (
              <div key={cluster.id}>
                <article
                  className={`bg-anveshak-card border border-anveshak-border rounded-lg p-4 hover:border-anveshak-accent/40 transition-all cursor-pointer ${
                    isExpanded ? 'ring-1 ring-anveshak-accent' : ''
                  }`}
                  onClick={() => handleClusterClick(cluster.id)}
                >
                  <div className="flex items-start justify-between mb-1">
                    <div className="flex items-center gap-2 min-w-0">
                      <h3 className="text-sm font-semibold text-text-primary truncate">{cluster.label ?? 'Unclassified'}</h3>
                      <RelevanceBadge tier={cluster.relevance_tier} />
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Badge variant="accent">{cluster.item_count}</Badge>
                      <span className="text-[10px] text-text-muted">{cluster.independent_source_count} sources</span>
                      <svg
                        viewBox="0 0 20 20" fill="currentColor"
                        className={`w-3 h-3 text-text-muted transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                      >
                        <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                      </svg>
                    </div>
                  </div>
                  {cluster.executive_summary && (
                    <p className="text-xs text-text-secondary leading-relaxed line-clamp-3">{cluster.executive_summary}</p>
                  )}
                  {cluster.sources?.length > 0 && (
                    <div className="flex gap-1.5 flex-wrap mt-2">
                      {cluster.sources.map((src, i) => (
                        <span key={i} className="text-[9px] bg-anveshak-muted rounded px-1.5 py-0.5 text-text-muted">
                          {src.platform.toUpperCase()} {src.source_name.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}
                        </span>
                      ))}
                    </div>
                  )}
                </article>

                {/* Drill-down */}
                {isExpanded && (
                  <div className="ml-4 mt-1 mb-2 border-l-2 border-anveshak-border/40 pl-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-[10px] text-text-muted">Sort:</span>
                      <button
                        className={`text-[10px] px-2 py-0.5 rounded ${drilldownSort === 'time' ? 'bg-anveshak-accent/20 text-anveshak-accent' : 'text-text-muted hover:text-text-primary'}`}
                        onClick={(e) => { e.stopPropagation(); setDrilldownSort('time') }}
                      >
                        Chronological
                      </button>
                      <button
                        className={`text-[10px] px-2 py-0.5 rounded ${drilldownSort === 'relevance' ? 'bg-anveshak-accent/20 text-anveshak-accent' : 'text-text-muted hover:text-text-primary'}`}
                        onClick={(e) => { e.stopPropagation(); setDrilldownSort('relevance') }}
                        disabled={!searchQ}
                      >
                        Relevance
                      </button>
                    </div>

                    {isDrilldownLoading ? (
                      <div className="py-3 flex justify-center">
                        <Spinner size="sm" label="Loading items..." />
                      </div>
                    ) : clusterContent.length === 0 ? (
                      <p className="text-[11px] text-text-muted py-2">No content items in this cluster.</p>
                    ) : (
                      <div className="space-y-2">
                        {clusterContent.map((item: ClusterContentItem) => (
                          <div
                            key={item.id}
                            className="bg-anveshak-card/50 border border-anveshak-border rounded-lg p-3 cursor-pointer hover:border-anveshak-accent/40 transition-colors"
                            onClick={(e) => { e.stopPropagation(); onSelectContent(item.id, item.title ?? undefined) }}
                          >
                            <div className="flex items-start justify-between gap-2 mb-1">
                              <div className="flex items-center gap-2 min-w-0">
                                {item.platform && (
                                  <span className="text-[9px] font-bold text-text-muted shrink-0">
                                    {item.platform.toUpperCase()}
                                  </span>
                                )}
                                <span className="text-[10px] text-text-muted truncate">
                                  {item.source_name?.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}
                                </span>
                                <RelevanceBadge tier={item.relevance_tier} />
                                {item.sentiment && <SentimentBadge compound={item.sentiment.compound} />}
                              </div>
                              <span className="text-[9px] text-text-muted shrink-0">
                                {new Date(item.captured_at).toLocaleDateString()}
                              </span>
                            </div>
                            {item.title && (
                              <p className="text-[11px] font-medium text-text-primary mb-1 line-clamp-1">{item.title}</p>
                            )}
                            <p className="text-[11px] text-text-secondary/80 leading-relaxed line-clamp-2">
                              {item.translated_text || item.clean_text}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
