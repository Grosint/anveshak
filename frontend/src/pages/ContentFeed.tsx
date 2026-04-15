import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { topicsApi } from '../api/topics'
import { contentApi, ContentFilters, ContentItem } from '../api/content'
import { useInfiniteContent } from '../hooks/useInfiniteContent'
import { ContentCard } from '../components/content/ContentCard'
import { ContentDetail } from '../components/content/ContentDetail'
import { FilterBar } from '../components/content/FilterBar'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { Button } from '../components/ui/Button'

export default function ContentFeed() {
  const { topicId } = useParams<{ topicId: string }>()
  const navigate = useNavigate()

  const [filters, setFilters]           = useState<ContentFilters>({})
  const [clusterView, setClusterView]   = useState(false)
  const [selectedId, setSelectedId]     = useState<string | null>(null)
  const [searchQ, setSearchQ]           = useState('')
  const [searchActive, setSearchActive] = useState(false)

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
          // Cluster view
          <div className="max-w-2xl space-y-6">
            {clusters.length === 0 ? (
              <p className="text-sm text-text-muted">No clusters formed yet — more content needed.</p>
            ) : (
              clusters.map((cluster) => (
                <section key={cluster.id} aria-labelledby={`cluster-${cluster.id}`}>
                  <div className="flex items-center gap-2 mb-3">
                    <h3 id={`cluster-${cluster.id}`} className="text-sm font-semibold text-text-primary">
                      {cluster.label ?? `Cluster (${cluster.item_count} items)`}
                    </h3>
                    <span className="text-xs text-text-muted">
                      {cluster.independent_source_count} platforms · {cluster.item_count} items
                    </span>
                  </div>
                  <p className="text-xs text-text-muted mb-3">
                    Items grouped into this narrative cluster — click to view individual articles.
                  </p>
                </section>
              ))
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
    </div>
  )
}
