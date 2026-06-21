import { useState, lazy, Suspense } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { topicsApi } from '../api/topics'
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
  const [showTemplateModal, setShowTemplateModal] = useState(false)
  const [graphSignalId, setGraphSignalId] = useState<string | null>(null)
  const [showEntityGraph, setShowEntityGraph] = useState(false)

  // Topic metadata
  const { data: topic } = useQuery({
    queryKey: ['topics', topicId],
    queryFn: () => topicsApi.get(topicId!),
    enabled: !!topicId,
  })

  // Clusters
  const { data: clusters = [] } = useQuery({
    queryKey: ['clusters', topicId],
    queryFn: () => topicsApi.listClusters(topicId!),
    enabled: !!topicId && activeTab === 'clusters',
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
            <div className="px-4 py-2 border-b border-anveshak-border flex gap-2 shrink-0">
              <input
                type="search"
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && searchQ.trim()) setSearchActive(true)
                  if (e.key === 'Escape') { setSearchActive(false); setSearchQ('') }
                }}
                placeholder="Semantic search..."
                className="flex-1 bg-anveshak-card border border-anveshak-border rounded px-3 py-1.5 text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent"
              />
              {searchActive ? (
                <Button size="sm" variant="ghost" onClick={() => { setSearchActive(false); setSearchQ('') }}>
                  Clear
                </Button>
              ) : (
                <Button size="sm" variant="secondary" onClick={() => searchQ.trim() && setSearchActive(true)} disabled={!searchQ.trim()}>
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

            {activeTab === 'clusters' && (
              <div className="p-4">
                {clusters.length === 0 ? (
                  <EmptyState icon="📊" title="No clusters yet" description="Clusters emerge when enough content is analyzed." />
                ) : (
                  <div className="max-w-3xl space-y-3">
                    {clusters.map((cluster) => (
                      <article
                        key={cluster.id}
                        className="bg-anveshak-card border border-anveshak-border rounded-lg p-4 hover:border-anveshak-accent/40 transition-all"
                      >
                        <div className="flex items-start justify-between mb-1">
                          <h3 className="text-sm font-semibold text-text-primary">{cluster.label ?? 'Unclassified'}</h3>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <Badge variant="accent">{cluster.item_count}</Badge>
                            <span className="text-[10px] text-text-muted">{cluster.independent_source_count} sources</span>
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
                    ))}
                  </div>
                )}
              </div>
            )}

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
