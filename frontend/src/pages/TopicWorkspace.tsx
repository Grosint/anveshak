import { useState, lazy, Suspense } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { topicsApi, Cluster, ClusterContentItem } from '../api/topics'
import { Signal } from '../api/signals'
import { TopIdentifier } from '../api/identifiers'
import { contentApi, ContentFilters, ContentItem } from '../api/content'
import { useInfiniteContent } from '../hooks/useInfiniteContent'
import { ContentCard } from '../components/content/ContentCard'
import { ContentDetail } from '../components/content/ContentDetail'
import { FilterBar } from '../components/content/FilterBar'
import { IntelSidebar } from '../components/workspace/IntelSidebar'
import { WorkspacePanel, PanelItem } from '../components/workspace/WorkspacePanel'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import ExportButton from '../components/ui/ExportButton'

type SearchMode = 'content' | 'narratives'

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
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold ${style.bg} ${style.text}`}
      title="Topic similarity — indicates shared subject matter, not operational linkage"
    >
      {style.label}
    </span>
  )
}

const Identifiers = lazy(() => import('./Identifiers'))
const TemplateManager = lazy(() => import('../components/topics/TemplateManager'))
const ReportsTab = lazy(() => import('../components/workspace/ReportsTab'))
const SourcesTab = lazy(() => import('../components/workspace/SourcesTab'))
import EntityGraph from '../components/workspace/EntityGraph'
const OverviewTab = lazy(() => import('../components/workspace/OverviewTab'))
const LocationMap = lazy(() => import('../components/workspace/LocationMap'))
const SignalGraph = lazy(() => import('../components/signals/SignalGraph').then(m => ({ default: m.SignalGraph })))
const DashboardTab = lazy(() => import('../components/workspace/DashboardTab'))

type CenterTab = 'dashboard' | 'overview' | 'feed' | 'clusters' | 'map' | 'identifiers' | 'reports' | 'sources'

const TABS: { key: CenterTab; label: string }[] = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'overview', label: 'Overview' },
  { key: 'feed', label: 'Feed' },
  { key: 'clusters', label: 'Clusters' },
  { key: 'map', label: 'Map' },
  { key: 'identifiers', label: 'Identifiers' },
  { key: 'reports', label: 'Reports' },
  { key: 'sources', label: 'Sources' },
]

export default function TopicWorkspace() {
  const { topicId } = useParams<{ topicId: string }>()
  const navigate = useNavigate()

  const [activeTab, setActiveTab] = useState<CenterTab>('dashboard')
  const [filters, setFilters] = useState<ContentFilters>({})
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [panelItem, setPanelItem] = useState<PanelItem>(null)
  const [searchQ, setSearchQ] = useState('')
  const [searchActive, setSearchActive] = useState(false)
  const [searchMode, setSearchMode] = useState<SearchMode>('content')
  const [expandedClusterId, setExpandedClusterId] = useState<string | null>(null)
  const [drilldownSort, setDrilldownSort] = useState<'time' | 'relevance'>('time')
  const [showTemplateModal, setShowTemplateModal] = useState(false)
  const [graphSignalId, setGraphSignalId] = useState<string | null>(null)
  const [showEntityGraph, setShowEntityGraph] = useState(false)

  // Topic metadata
  const { data: topic } = useQuery({
    queryKey: ['topics', topicId],
    queryFn: () => topicsApi.get(topicId!),
    enabled: !!topicId,
  })

  // Clusters (browsing)
  const { data: clusters = [] } = useQuery({
    queryKey: ['clusters', topicId],
    queryFn: () => topicsApi.listClusters(topicId!),
    enabled: !!topicId && activeTab === 'clusters' && !(searchActive && searchMode === 'narratives'),
  })

  // Narrative search — cluster centroid search
  const { data: narrativeResults = [], isFetching: isNarrativeSearching } = useQuery({
    queryKey: ['cluster-search', topicId, searchQ],
    queryFn: () => topicsApi.searchClusters(topicId!, searchQ),
    enabled: searchActive && searchMode === 'narratives' && !!searchQ && !!topicId && activeTab === 'clusters',
    staleTime: 60_000,
  })

  // Cluster drill-down — content within expanded cluster
  const { data: clusterContent = [], isFetching: isDrilldownLoading } = useQuery({
    queryKey: ['cluster-content', topicId, expandedClusterId, drilldownSort, searchActive ? searchQ : ''],
    queryFn: () => topicsApi.getClusterContent(topicId!, expandedClusterId!, {
      q: searchActive ? searchQ : undefined,
      sort: searchActive && searchQ ? drilldownSort : 'time',
      limit: 50,
    }),
    enabled: !!topicId && !!expandedClusterId,
  })

  // Content semantic search
  const { data: searchResults = [], isFetching: isContentSearching } = useQuery({
    queryKey: ['search', topicId, searchQ],
    queryFn: () => contentApi.search(searchQ, topicId!),
    enabled: searchActive && searchMode === 'content' && !!searchQ && !!topicId,
    staleTime: 60_000,
  })

  const isSearching = isContentSearching || isNarrativeSearching

  // Infinite feed
  const { items, isLoading, isFetchingNextPage, sentinelRef } = useInfiniteContent(
    topicId ?? '',
    filters,
  )

  if (!topicId) return null

  const displayItems: ContentItem[] = searchActive
    ? searchResults.map((r) => ({ ...r, backfilled: false }))
    : items

  // Handlers
  const handleSelectSignal = (signal: Signal) => {
    setPanelItem({ type: 'signal', id: signal.id, topicId: topicId! })
  }

  const handleSelectIdentifier = (_id: TopIdentifier) => {
    setActiveTab('identifiers')
  }

  const handleSelectContent = (contentId: string) => {
    setSelectedId(contentId)
  }

  const handleClosePanel = () => setPanelItem(null)

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-anveshak-border bg-[#0f1729] shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => navigate('/topics')}
              className="text-text-muted hover:text-text-primary transition-colors shrink-0"
              aria-label="Back to topics"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                <path fillRule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clipRule="evenodd" />
              </svg>
            </button>
            <h1 className="text-lg font-semibold text-text-primary truncate">
              {topic?.name ?? 'Loading...'}
            </h1>
            {topic?.status && (
              <Badge variant={topic.status === 'active' ? 'success' : 'default'}>
                {topic.status}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button size="sm" variant="secondary" onClick={() => setShowEntityGraph(true)}>
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                <path d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H4.233a.75.75 0 00-.75.75v4a.75.75 0 001.5 0v-2.146l.312.31a7 7 0 0011.712-3.138.75.75 0 00-1.449-.39zm1.436-7.674a.75.75 0 00-.75.75v2.146l-.312-.31A7 7 0 003.974 9.474a.75.75 0 101.449.39A5.5 5.5 0 0114.624 7.61l.312.311h-2.433a.75.75 0 000 1.5h3.999a.75.75 0 00.75-.75v-4a.75.75 0 00-.75-.75z" />
              </svg>
              Graph
            </Button>
            <ExportButton
              endpoint="/api/v1/export/content"
              params={{ topic_id: topicId }}
              label="Export"
              format="csv"
            />
          </div>
        </div>
      </div>

      {/* Main 3-column layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left intel sidebar */}
        <IntelSidebar
          topicId={topicId}
          onSelectSignal={handleSelectSignal}
          onSelectIdentifier={handleSelectIdentifier}
          onViewAllIdentifiers={() => setActiveTab('identifiers')}
          onManageTemplates={() => setShowTemplateModal(true)}
        />

        {/* Center content */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          {/* Tab bar */}
          <div className="px-4 border-b border-anveshak-border shrink-0">
            <div className="flex items-center gap-0.5 -mb-px">
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`px-3 py-2.5 text-xs font-medium border-b-2 transition-colors ${
                    activeTab === tab.key
                      ? 'border-anveshak-accent text-anveshak-accent'
                      : 'border-transparent text-text-muted hover:text-text-primary'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Search bar (feed + clusters only) */}
          {(activeTab === 'feed' || activeTab === 'clusters') && (
            <div className="px-4 py-2 border-b border-anveshak-border flex gap-2 items-center shrink-0">
              {/* Segmented control: Content | Narratives */}
              <div className="flex bg-anveshak-card border border-anveshak-border rounded overflow-hidden shrink-0">
                <button
                  className={`px-2.5 py-1 text-[10px] font-medium transition-colors ${
                    searchMode === 'content'
                      ? 'bg-anveshak-accent/20 text-anveshak-accent'
                      : 'text-text-muted hover:text-text-primary'
                  }`}
                  onClick={() => { setSearchMode('content'); if (searchActive) { setSearchActive(false); setExpandedClusterId(null) } }}
                >
                  Content
                </button>
                <button
                  className={`px-2.5 py-1 text-[10px] font-medium transition-colors border-l border-anveshak-border ${
                    searchMode === 'narratives'
                      ? 'bg-anveshak-accent/20 text-anveshak-accent'
                      : 'text-text-muted hover:text-text-primary'
                  }`}
                  onClick={() => { setSearchMode('narratives'); setActiveTab('clusters'); if (searchActive) { setSearchActive(false); setExpandedClusterId(null) } }}
                >
                  Narratives
                </button>
              </div>
              <input
                type="search"
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && searchQ.trim()) {
                    setSearchActive(true)
                    if (searchMode === 'narratives') setActiveTab('clusters')
                  }
                  if (e.key === 'Escape') { setSearchActive(false); setSearchQ(''); setExpandedClusterId(null) }
                }}
                placeholder={searchMode === 'narratives' ? 'Search narratives...' : 'Semantic search...'}
                className="flex-1 bg-anveshak-card border border-anveshak-border rounded px-3 py-1.5 text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent"
              />
              {searchActive ? (
                <Button size="sm" variant="ghost" onClick={() => { setSearchActive(false); setSearchQ(''); setExpandedClusterId(null) }}>
                  Clear
                </Button>
              ) : (
                <Button size="sm" variant="secondary" onClick={() => {
                  if (searchQ.trim()) {
                    setSearchActive(true)
                    if (searchMode === 'narratives') setActiveTab('clusters')
                  }
                }} disabled={!searchQ.trim()}>
                  Search
                </Button>
              )}
            </div>
          )}

          {/* Filter bar (feed only) */}
          {activeTab === 'feed' && !searchActive && (
            <FilterBar
              filters={filters}
              onChange={setFilters}
              clusterView={false}
              onToggleCluster={() => setActiveTab('clusters')}
            />
          )}

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto">
            {activeTab === 'dashboard' && (
              <Suspense fallback={<div className="p-4"><Spinner label="Loading dashboard..." /></div>}>
                <DashboardTab topicId={topicId!} />
              </Suspense>
            )}

            {activeTab === 'overview' && (
              <Suspense fallback={<div className="p-4"><Spinner label="Loading overview..." /></div>}>
                <OverviewTab
                  topicId={topicId}
                  onSelectSignal={handleSelectSignal}
                  onNavigateTab={(tab) => setActiveTab(tab as CenterTab)}
                  onViewReport={(reportId) => setPanelItem({ type: 'report', id: reportId })}
                />
              </Suspense>
            )}

            {activeTab === 'feed' && (
              <div className="p-4">
                {isLoading || isSearching ? (
                  <div className="flex justify-center py-20">
                    <Spinner label={isSearching ? 'Searching...' : 'Loading content...'} />
                  </div>
                ) : displayItems.length === 0 ? (
                  <EmptyState
                    icon="📄"
                    title={searchActive ? 'No results found' : 'No content yet'}
                    description={searchActive ? 'Try different keywords.' : 'Content will appear once sources are scraped.'}
                  />
                ) : (
                  <div className="max-w-2xl space-y-3">
                    {displayItems.map((item) => (
                      <ContentCard
                        key={item.id}
                        item={item}
                        onClick={() => handleSelectContent(item.id)}
                      />
                    ))}
                    {!searchActive && <div ref={sentinelRef} className="h-1" />}
                    {isFetchingNextPage && (
                      <div className="flex justify-center py-4">
                        <Spinner size="sm" label="Loading more..." />
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'clusters' && (() => {
              const displayClusters: Cluster[] = (searchActive && searchMode === 'narratives')
                ? narrativeResults
                : clusters

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
                  {isNarrativeSearching ? (
                    <div className="flex justify-center py-20">
                      <Spinner label="Searching narratives..." />
                    </div>
                  ) : displayClusters.length === 0 ? (
                    <EmptyState
                      icon="📊"
                      title={searchActive && searchMode === 'narratives' ? 'No matching narratives' : 'No clusters yet'}
                      description={searchActive ? 'Try different keywords.' : 'Clusters emerge when enough content is analyzed.'}
                    />
                  ) : (
                    <div className="max-w-3xl space-y-3">
                      {/* Summary */}
                      <div className="flex items-center gap-3 text-[10px] text-text-muted px-1">
                        <span>
                          {searchActive && searchMode === 'narratives'
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

                            {/* Drill-down: content items */}
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
                                    title={searchQ ? 'Rank by query similarity' : 'Enter a search query to enable relevance sort'}
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
                                        onClick={(e) => { e.stopPropagation(); setSelectedId(item.id) }}
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
            })()}

            {activeTab === 'map' && (
              <Suspense fallback={<div className="p-4"><Spinner label="Loading map..." /></div>}>
                <LocationMap topicId={topicId} />
              </Suspense>
            )}

            {activeTab === 'identifiers' && (
              <Suspense fallback={<div className="p-4"><Spinner label="Loading identifiers..." /></div>}>
                <Identifiers embedded topicId={topicId} />
              </Suspense>
            )}

            {activeTab === 'reports' && (
              <Suspense fallback={<div className="p-4"><Spinner label="Loading reports..." /></div>}>
                <ReportsTab topicId={topicId} />
              </Suspense>
            )}

            {activeTab === 'sources' && (
              <Suspense fallback={<div className="p-4"><Spinner label="Loading sources..." /></div>}>
                <SourcesTab topicId={topicId} />
              </Suspense>
            )}

          </div>
        </div>

        {/* Right panel (contextual) */}
        {panelItem && (
          <WorkspacePanel item={panelItem} onClose={handleClosePanel} onShowGraph={setGraphSignalId} />
        )}
      </div>

      {/* Content detail slide-over */}
      {selectedId && (
        <ContentDetail contentId={selectedId} onClose={() => setSelectedId(null)} />
      )}

      {/* Template manager modal */}
      {showTemplateModal && (
        <>
          <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm" onClick={() => setShowTemplateModal(false)} />
          <div className="fixed inset-x-4 top-[10%] bottom-[10%] z-50 max-w-2xl mx-auto bg-[#0b1222] border border-anveshak-border rounded-xl shadow-2xl overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-text-primary">Manage Templates</h2>
              <button onClick={() => setShowTemplateModal(false)} className="text-text-muted hover:text-text-primary">
                <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
                  <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
                </svg>
              </button>
            </div>
            <Suspense fallback={<Spinner label="Loading..." />}>
              <TemplateManager topicId={topicId} />
            </Suspense>
          </div>
        </>
      )}
      {/* Entity graph full-screen modal */}
      {showEntityGraph && (
        <div className="fixed inset-0 z-[60] bg-[#0b1222]">
          <EntityGraph topicId={topicId} onClose={() => setShowEntityGraph(false)} />
        </div>
      )}

      {/* Signal graph full-screen modal */}
      {graphSignalId && (
        <Suspense fallback={null}>
          <div className="fixed inset-0 z-[60] bg-[#0b1222]">
            <SignalGraph signalId={graphSignalId} onClose={() => setGraphSignalId(null)} />
          </div>
        </Suspense>
      )}
    </div>
  )
}
