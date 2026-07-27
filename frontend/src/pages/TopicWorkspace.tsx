import { useState, useEffect, lazy, Suspense } from 'react'
import { useParams, useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { topicsApi } from '../api/topics'
import { contentApi, ContentFilters, ContentItem } from '../api/content'
import { useInfiniteContent } from '../hooks/useInfiniteContent'
import { useProvenance } from '../contexts/ProvenanceContext'
import { resolveWorkspaceView, WORKSPACE_VIEWS, WorkspaceView } from '../lib/domain'
import { IntelligenceView } from '../components/intelligence'
import { IdentifiersModal } from '../components/modals/IdentifiersModal'
import { ClustersModal } from '../components/modals/ClustersModal'
import { ReportGenerationModal } from '../components/modals/ReportGenerationModal'
import { SourceManagementModal } from '../components/modals/SourceManagementModal'
import { ContentCard } from '../components/content/ContentCard'
import { FilterBar } from '../components/content/FilterBar'
import { ProvenancePanel } from '../components/provenance/ProvenancePanel'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import ExportButton from '../components/ui/ExportButton'

import EntityGraph from '../components/workspace/EntityGraph'
const LocationMap = lazy(() => import('../components/workspace/LocationMap'))
const SignalGraph = lazy(() => import('../components/signals/SignalGraph').then(m => ({ default: m.SignalGraph })))

type ActiveModal = 'identifiers' | 'clusters' | 'report' | 'sources' | null

export default function TopicWorkspace() {
  const { topicId } = useParams<{ topicId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const provenance = useProvenance()
  const { push: provenancePush } = provenance

  const activeView: WorkspaceView = resolveWorkspaceView(location.pathname, topicId ?? '')

  const [filters, setFilters] = useState<ContentFilters>({})
  const [searchQ, setSearchQ] = useState('')
  const [searchActive, setSearchActive] = useState(false)
  const [graphSignalId, setGraphSignalId] = useState<string | null>(null)
  const [showEntityGraph, setShowEntityGraph] = useState(false)
  const [activeModal, setActiveModal] = useState<ActiveModal>(null)

  // Auto-open ProvenancePanel from URL params (e.g. ?panel=identifier&value=X)
  useEffect(() => {
    const panel = searchParams.get('panel')
    const value = searchParams.get('value')
    if (panel === 'identifier' && value && topicId) {
      provenancePush({
        entityType: 'identifier',
        entityId: value,
        topicId,
        label: value,
      })
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, setSearchParams, topicId, provenancePush])

  const handleViewSwitch = (view: WorkspaceView) => {
    const viewDef = WORKSPACE_VIEWS.find((v) => v.key === view)!
    navigate(`/topics/${topicId}${viewDef.path}`, { replace: true })
    provenance.close()
  }

  // Topic metadata
  const { data: topic } = useQuery({
    queryKey: ['topics', topicId],
    queryFn: () => topicsApi.get(topicId!),
    enabled: !!topicId,
  })

  // Content semantic search (only active in content view)
  const { data: searchResults = [], isFetching: isSearching } = useQuery({
    queryKey: ['search', topicId, searchQ],
    queryFn: () => contentApi.search(searchQ, topicId!),
    enabled: activeView === 'content' && searchActive && !!searchQ && !!topicId,
    staleTime: 60_000,
  })

  // Infinite feed — gated to content view only
  const { items, isLoading, isFetchingNextPage, sentinelRef } = useInfiniteContent(
    topicId ?? '',
    filters,
    activeView === 'content',
  )

  if (!topicId) return null

  const displayItems: ContentItem[] = searchActive
    ? searchResults.map((r) => ({ ...r, backfilled: false }))
    : items

  // ── Click handlers — all push to provenance panel ─────────────────────

  const handleSelectContent = (contentId: string, title?: string) => {
    provenance.push({
      entityType: 'content',
      entityId: contentId,
      topicId,
      label: title || contentId.slice(0, 8),
    })
  }

  const handleSelectIdentifier = (_type: string, value: string) => {
    provenance.push({
      entityType: 'identifier',
      entityId: value,
      topicId: topicId!,
      label: value,
    })
  }

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

      {/* Main layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Center content */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          {/* 3-view tab bar — responsive: scrollable on mobile */}
          <div className="px-2 sm:px-4 border-b border-anveshak-border shrink-0 overflow-x-auto">
            <nav className="flex items-center gap-0.5 -mb-px min-w-0" aria-label="Workspace views">
              {WORKSPACE_VIEWS.map((view) => (
                <button
                  key={view.key}
                  onClick={() => handleViewSwitch(view.key)}
                  className={`px-3 sm:px-4 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-colors whitespace-nowrap shrink-0 ${
                    activeView === view.key
                      ? 'border-anveshak-accent text-anveshak-accent'
                      : 'border-transparent text-text-muted hover:text-text-primary'
                  }`}
                  aria-current={activeView === view.key ? 'page' : undefined}
                >
                  {view.label}
                </button>
              ))}
            </nav>
          </div>

          {/* Search bar (content view only) */}
          {activeView === 'content' && (
            <div className="px-4 py-2 border-b border-anveshak-border flex gap-2 items-center shrink-0">
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
                <Button size="sm" variant="secondary" onClick={() => {
                  if (searchQ.trim()) setSearchActive(true)
                }} disabled={!searchQ.trim()}>
                  Search
                </Button>
              )}
            </div>
          )}

          {/* Filter bar (content view, not during search) */}
          {activeView === 'content' && !searchActive && (
            <FilterBar
              filters={filters}
              onChange={setFilters}
              clusterView={false}
              onToggleCluster={() => setActiveModal('clusters')}
            />
          )}

          {/* View content */}
          <div className="flex-1 overflow-y-auto">
            {activeView === 'intelligence' && (
              <IntelligenceView
                topicId={topicId}
                topicStatus={topic?.status}
                onNavigateMap={() => handleViewSwitch('map')}
                onNavigateContent={() => handleViewSwitch('content')}
                onShowAllClusters={() => setActiveModal('clusters')}
                onShowAllIdentifiers={() => setActiveModal('identifiers')}
                onGenerateReport={() => setActiveModal('report')}
                onManageSources={() => setActiveModal('sources')}
              />
            )}

            {activeView === 'content' && (
              <div className="p-4">
                <div className="flex justify-end mb-3">
                  <ExportButton
                    endpoint="/api/v1/export/content"
                    params={{ topic_id: topicId }}
                    label="Export CSV"
                    format="csv"
                  />
                </div>
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
                        onClick={() => handleSelectContent(item.id, item.title ?? undefined)}
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

            {activeView === 'map' && (
              <Suspense fallback={<div className="p-4"><Spinner label="Loading map..." /></div>}>
                <div className="h-full flex flex-col">
                  <div className="flex justify-end px-4 py-2 shrink-0">
                    <ExportButton
                      endpoint="/api/v1/export/locations"
                      params={{ topic_id: topicId }}
                      label="Export GeoJSON"
                      format="json"
                    />
                  </div>
                  <div className="flex-1 min-h-0">
                    <LocationMap topicId={topicId} topicName={topic?.name} />
                  </div>
                </div>
              </Suspense>
            )}
          </div>
        </div>

        {/* Right panel — provenance */}
        {provenance.isOpen && <ProvenancePanel />}
      </div>

      {/* Full-screen content modals */}
      <IdentifiersModal
        open={activeModal === 'identifiers'}
        onClose={() => setActiveModal(null)}
        topicId={topicId}
        onSelectIdentifier={handleSelectIdentifier}
      />
      <ClustersModal
        open={activeModal === 'clusters'}
        onClose={() => setActiveModal(null)}
        topicId={topicId}
        onSelectContent={handleSelectContent}
      />
      <ReportGenerationModal
        open={activeModal === 'report'}
        onClose={() => setActiveModal(null)}
        topicId={topicId}
      />
      <SourceManagementModal
        open={activeModal === 'sources'}
        onClose={() => setActiveModal(null)}
        topicId={topicId}
      />

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
