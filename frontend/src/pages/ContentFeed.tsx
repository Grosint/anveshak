import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { topicsApi } from '../api/topics'
import { ManageSourcesModal } from '../components/topics/ManageSourcesModal'
import { SourceDiscoveryTab } from '../components/discovery/SourceDiscoveryTab'
import { contentApi, ContentFilters, ContentItem } from '../api/content'
import { useInfiniteContent } from '../hooks/useInfiniteContent'
import { ContentCard } from '../components/content/ContentCard'
import { ContentDetail } from '../components/content/ContentDetail'
import { FilterBar } from '../components/content/FilterBar'
import { SentimentTrend } from '../components/topics/SentimentTrend'
import { TrendingKeywords } from '../components/topics/TrendingKeywords'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { Button } from '../components/ui/Button'
import ExportButton from '../components/ui/ExportButton'
import { lazy, Suspense } from 'react'

const Identifiers = lazy(() => import('./Identifiers'))
const TemplateManager = lazy(() => import('../components/topics/TemplateManager'))

export default function ContentFeed() {
  const { topicId } = useParams<{ topicId: string }>()
  const navigate = useNavigate()

  const [filters, setFilters]           = useState<ContentFilters>({})
  const [clusterView, setClusterView]   = useState(false)
  const [selectedId, setSelectedId]     = useState<string | null>(null)
  const [searchQ, setSearchQ]           = useState('')
  const [searchActive, setSearchActive] = useState(false)
  const [showSources, setShowSources]   = useState(false)
  const [showDiscovery, setShowDiscovery] = useState(false)
  const [showAnalytics, setShowAnalytics] = useState(false)
  const [showIdentifiers, setShowIdentifiers] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)

  // Topic meta
  const { data: topic } = useQuery({
    queryKey: ['topics', topicId],
    queryFn: () => topicsApi.get(topicId!),
    enabled: !!topicId,
  })

  // Clusters (for cluster view)
  const { data: clusters = [] } = useQuery({
    queryKey: ['clusters', topicId],
    queryFn: () => topicsApi.listClusters(topicId!),
    enabled: !!topicId && clusterView,
  })

  // Semantic search
  const { data: searchResults = [], isFetching: isSearching } = useQuery({
    queryKey: ['search', topicId, searchQ],
    queryFn: () => contentApi.search(searchQ, topicId!),
    enabled: searchActive && !!searchQ && !!topicId,
    staleTime: 60_000,
  })

  // Infinite feed
  const { items, isLoading, isFetchingNextPage, sentinelRef } = useInfiniteContent(
    topicId ?? '',
    filters,
  )

  if (!topicId) return null

  // SearchResult lacks 'backfilled' — cast to ContentItem for unified rendering
  const displayItems: ContentItem[] = searchActive
    ? searchResults.map((r) => ({ ...r, backfilled: false }))
    : items

  return (
    <div className="h-full flex flex-col relative">
      {/* Header */}
      <div className="px-6 pt-5 pb-3 border-b border-anveshak-border">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <button
                onClick={() => navigate('/topics')}
                className="text-text-muted hover:text-text-primary transition-colors"
                aria-label="Back to topics"
              >
                <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
                  <path fillRule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clipRule="evenodd" />
                </svg>
              </button>
              <h1 className="text-xl font-semibold text-text-primary truncate">
                {topic?.name ?? 'Content Feed'}
              </h1>
            </div>
            <p className="text-sm text-text-muted">
              {searchActive
                ? `${searchResults.length} semantic search results`
                : `${items.length} items loaded`}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant={showAnalytics ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => setShowAnalytics((v) => !v)}
              aria-label="Toggle analytics panel"
              aria-pressed={showAnalytics}
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
                <path d="M15.5 2A1.5 1.5 0 0014 3.5v13a1.5 1.5 0 001.5 1.5h1a1.5 1.5 0 001.5-1.5v-13A1.5 1.5 0 0016.5 2h-1zM9.5 6A1.5 1.5 0 008 7.5v9A1.5 1.5 0 009.5 18h1a1.5 1.5 0 001.5-1.5v-9A1.5 1.5 0 0010.5 6h-1zM3.5 10A1.5 1.5 0 002 11.5v5A1.5 1.5 0 003.5 18h1A1.5 1.5 0 006 16.5v-5A1.5 1.5 0 004.5 10h-1z" />
              </svg>
              Analytics
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowSources(true)}
              aria-label="Manage topic sources"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
                <path d="M3.5 3A1.5 1.5 0 002 4.5v3.793a1.5 1.5 0 00.44 1.06l7.5 7.5a1.5 1.5 0 002.12 0l3.793-3.793a1.5 1.5 0 000-2.122l-7.5-7.5A1.5 1.5 0 007.293 3H3.5zM5 6a1 1 0 100-2 1 1 0 000 2z" />
              </svg>
              Manage Sources
            </Button>
            <Button
              variant={showDiscovery ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => setShowDiscovery((v) => !v)}
              aria-label="Discover new sources"
              aria-pressed={showDiscovery}
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
                <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clipRule="evenodd" />
              </svg>
              Discover Sources
            </Button>
            <Button
              variant={showIdentifiers ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => setShowIdentifiers((v) => !v)}
              aria-label="Toggle identifiers panel"
              aria-pressed={showIdentifiers}
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
                <path fillRule="evenodd" d="M3.5 2A1.5 1.5 0 002 3.5V5c0 .414.336.75.75.75h14.5A.75.75 0 0018 5V3.5A1.5 1.5 0 0016.5 2h-13zm11.066 4.97a.75.75 0 10-1.132-.99l-2.794 3.193-1.283-1.283a.75.75 0 00-1.06 1.06l1.857 1.858a.75.75 0 001.096-.035l3.316-3.803zM2 7.5h4v2H2.75A.75.75 0 012 8.75V7.5zm0 3.5h4v2H2.75a.75.75 0 01-.75-.75V11zm0 3.5h4V16h-.5A1.5 1.5 0 012 14.5zm14.25-7h-4v2h4.75V8.75a.75.75 0 00-.75-.75zm.75 3.5h-4.75v2h4.75v-1.25a.75.75 0 00-.75-.75h.75zm-.75 3.5h-4.25V16h2.75A1.5 1.5 0 0018 14.5V14.5h-1.75z" clipRule="evenodd" />
              </svg>
              Identifiers
            </Button>
            <Button
              variant={showTemplates ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => setShowTemplates((v) => !v)}
              aria-label="Toggle templates panel"
              aria-pressed={showTemplates}
            >
              Templates
            </Button>
            <ExportButton
              endpoint="/api/v1/export/content"
              params={{ topic_id: topicId }}
              label="Export CSV"
              format="csv"
            />
          </div>
        </div>
      </div>

      {/* Search bar */}
      <div className="px-6 py-3 border-b border-anveshak-border flex gap-2">
        <input
          type="search"
          value={searchQ}
          onChange={(e) => setSearchQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && searchQ.trim()) setSearchActive(true)
            if (e.key === 'Escape') { setSearchActive(false); setSearchQ('') }
          }}
          placeholder="Semantic search (pgvector)…"
          className="flex-1 bg-anveshak-card border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent"
          aria-label="Semantic search content"
        />
        {searchActive ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { setSearchActive(false); setSearchQ('') }}
          >
            Clear
          </Button>
        ) : (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => searchQ.trim() && setSearchActive(true)}
            disabled={!searchQ.trim()}
          >
            Search
          </Button>
        )}
      </div>

      {/* Filter bar (only in feed mode, not search) */}
      {!searchActive && (
        <FilterBar
          filters={filters}
          onChange={setFilters}
          clusterView={clusterView}
          onToggleCluster={() => setClusterView((v) => !v)}
        />
      )}

      {/* Analytics panel — only show when content exists */}
      {showAnalytics && !searchActive && items.length > 0 && (
        <div className="px-6 py-4 border-b border-anveshak-border">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SentimentTrend topicId={topicId} />
            <TrendingKeywords topicId={topicId} />
          </div>
        </div>
      )}

      {/* Source discovery panel */}
      {showDiscovery && (
        <div className="px-6 py-4 border-b border-anveshak-border max-h-[50vh] overflow-y-auto">
          <SourceDiscoveryTab topicId={topicId} />
        </div>
      )}

      {/* Identifiers panel (Engine C) */}
      {showIdentifiers && (
        <div className="px-6 py-4 border-b border-anveshak-border max-h-[60vh] overflow-y-auto">
          <Suspense fallback={<Spinner label="Loading identifiers…" />}>
            <Identifiers embedded topicId={topicId} />
          </Suspense>
        </div>
      )}

      {/* Template manager panel (Engine C) */}
      {showTemplates && (
        <div className="px-6 py-4 border-b border-anveshak-border max-h-[50vh] overflow-y-auto">
          <Suspense fallback={<Spinner label="Loading templates…" />}>
            <TemplateManager topicId={topicId} />
          </Suspense>
        </div>
      )}

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading || isSearching ? (
          <div className="flex justify-center py-20">
            <Spinner label={isSearching ? 'Searching…' : 'Loading content…'} />
          </div>
        ) : displayItems.length === 0 ? (
          <EmptyState
            icon="📄"
            title={searchActive ? 'No results found' : 'No content yet'}
            description={
              searchActive
                ? 'Try different keywords or broaden your search.'
                : 'Content will appear here once the scraper and social adapters collect items.'
            }
          />
        ) : clusterView && !searchActive ? (
          // Cluster view — military C2 aesthetic
          <div className="max-w-3xl space-y-3">
            {clusters.length === 0 ? (
              <EmptyState
                icon="📊"
                title="No clusters formed yet"
                description="Clusters emerge when enough content is collected and analysed."
              />
            ) : (
              <>
                {/* Summary bar */}
                <div className="flex items-center gap-4 text-[11px] text-text-muted mb-2 px-1">
                  <span>{clusters.length} narrative cluster{clusters.length !== 1 ? 's' : ''}</span>
                  <span className="text-anveshak-border">|</span>
                  <span>{clusters.reduce((s, c) => s + c.item_count, 0)} total items</span>
                </div>

                {(() => {
                  const maxItems = Math.max(...clusters.map((c) => c.item_count), 1)
                  // Color scale: top clusters get brighter accents
                  const accentColors = [
                    { bar: '#3b82f6', border: 'rgba(59,130,246,0.35)', glow: 'rgba(59,130,246,0.08)' },
                    { bar: '#8b5cf6', border: 'rgba(139,92,246,0.30)', glow: 'rgba(139,92,246,0.06)' },
                    { bar: '#06b6d4', border: 'rgba(6,182,212,0.30)', glow: 'rgba(6,182,212,0.06)' },
                    { bar: '#10b981', border: 'rgba(16,185,129,0.25)', glow: 'rgba(16,185,129,0.05)' },
                    { bar: '#f59e0b', border: 'rgba(245,158,11,0.25)', glow: 'rgba(245,158,11,0.05)' },
                  ]

                  return clusters.map((cluster, idx) => {
                    const barPct = Math.max(6, (cluster.item_count / maxItems) * 100)
                    const label = cluster.label ?? 'Unclassified cluster'
                    const sources = cluster.sources ?? []
                    const isc = cluster.independent_source_count
                    const accent = accentColors[idx % accentColors.length]
                    const isTop = idx < 3

                    return (
                      <article
                        key={cluster.id}
                        className="relative overflow-hidden rounded-lg border transition-all duration-300 cursor-pointer group hover:scale-[1.008] hover:shadow-lg"
                        style={{
                          borderColor: accent.border,
                          backgroundColor: accent.glow,
                        }}
                        onClick={() => {/* TODO: expand to show items */}}
                      >
                        {/* Left accent bar */}
                        <div
                          className="absolute left-0 top-0 bottom-0 w-1 rounded-l-lg"
                          style={{ backgroundColor: accent.bar, opacity: isTop ? 0.9 : 0.5 }}
                        />

                        {/* Subtle top glow for top clusters */}
                        {isTop && (
                          <div
                            className="absolute top-0 left-0 right-0 h-px"
                            style={{
                              background: `linear-gradient(90deg, transparent 0%, ${accent.bar}60 30%, ${accent.bar}80 50%, ${accent.bar}60 70%, transparent 100%)`,
                            }}
                          />
                        )}

                        <div className="pl-4 pr-4 py-3.5">
                          {/* Top row: label + item count badge */}
                          <div className="flex items-start justify-between gap-3 mb-1">
                            <h3 className="text-[13px] font-semibold text-text-primary leading-snug group-hover:text-white transition-colors flex-1 min-w-0">
                              {label}
                            </h3>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <span
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold"
                                style={{
                                  backgroundColor: `${accent.bar}20`,
                                  color: accent.bar,
                                }}
                              >
                                {cluster.item_count}
                              </span>
                              <span className="text-[10px] text-text-muted">
                                {isc} src{isc !== 1 ? 's' : ''}
                              </span>
                            </div>
                          </div>

                          {/* Size bar */}
                          <div className="w-full h-[3px] bg-white/[0.04] rounded-full mb-2.5 overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-700 ease-out"
                              style={{
                                width: `${barPct}%`,
                                background: `linear-gradient(90deg, ${accent.bar}90, ${accent.bar}40)`,
                                boxShadow: isTop ? `0 0 8px ${accent.bar}40` : undefined,
                              }}
                            />
                          </div>

                          {/* Executive summary */}
                          {cluster.executive_summary && (
                            <p className="text-[11px] text-text-secondary/80 leading-relaxed line-clamp-2 mb-2">
                              {cluster.executive_summary}
                            </p>
                          )}

                          {/* Source chips */}
                          {sources.length > 0 && (
                            <div className="flex items-center gap-1.5 flex-wrap">
                              {sources.map((src, i) => {
                                const credColor =
                                  src.credibility_score >= 70 ? 'text-cred-high' :
                                  src.credibility_score >= 40 ? 'text-signal-med' :
                                  'text-signal-high'
                                return (
                                  <span
                                    key={i}
                                    className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] border border-white/[0.06]"
                                    style={{ backgroundColor: 'rgba(255,255,255,0.03)' }}
                                  >
                                    <span className="font-bold text-text-muted">
                                      {src.platform.toUpperCase()}
                                    </span>
                                    <span className="text-text-muted/70 truncate max-w-[90px]">
                                      {src.source_name.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}
                                    </span>
                                    <span className={`font-mono font-bold ${credColor}`}>
                                      {Math.round(src.credibility_score)}
                                    </span>
                                  </span>
                                )
                              })}
                            </div>
                          )}
                        </div>
                      </article>
                    )
                  })
                })()}
              </>
            )}
          </div>
        ) : (
          // Feed view
          <div className="max-w-2xl space-y-3">
            {displayItems.map((item) => (
              <ContentCard
                key={item.id}
                item={item}
                onClick={() => setSelectedId(item.id)}
              />
            ))}
            {/* Infinite scroll sentinel */}
            {!searchActive && (
              <div ref={sentinelRef} className="h-1" aria-hidden="true" />
            )}
            {isFetchingNextPage && (
              <div className="flex justify-center py-4">
                <Spinner size="sm" label="Loading more…" />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Detail slide-over */}
      {selectedId && (
        <ContentDetail contentId={selectedId} onClose={() => setSelectedId(null)} />
      )}

      {/* Manage sources modal */}
      {topicId && (
        <ManageSourcesModal
          open={showSources}
          onClose={() => setShowSources(false)}
          topicId={topicId}
          topicName={topic?.name ?? ''}
        />
      )}
    </div>
  )
}
