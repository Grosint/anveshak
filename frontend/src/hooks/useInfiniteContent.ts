import { useInfiniteQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { contentApi, ContentItem, ContentFilters } from '../api/content'

const PAGE_SIZE = 50

function applyClientFilters(items: ContentItem[], filters: ContentFilters): ContentItem[] {
  return items.filter((item) => {
    if (filters.language && item.language !== filters.language) return false
    if (filters.credibility_min !== undefined && item.credibility_score_at_capture < filters.credibility_min) return false
    if (filters.date_from && item.captured_at < filters.date_from) return false
    if (filters.date_to && item.captured_at > filters.date_to) return false
    return true
  })
}

export function useInfiniteContent(topicId: string, filters: ContentFilters = {}) {
  const query = useInfiniteQuery({
    queryKey: ['content', topicId, filters],
    queryFn: ({ pageParam }) => contentApi.list(topicId, pageParam as number, PAGE_SIZE),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      if (!lastPage || lastPage.length < PAGE_SIZE) return undefined
      return allPages.flat().length
    },
    staleTime: 30_000,
  })

  const allItems = query.data?.pages.flat() ?? []
  const filtered = applyClientFilters(allItems, filters)

  // Intersection Observer sentinel
  const sentinelRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && query.hasNextPage && !query.isFetchingNextPage) {
          query.fetchNextPage()
        }
      },
      { rootMargin: '200px' },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [query])

  return {
    items: filtered,
    totalLoaded: allItems.length,
    isLoading: query.isLoading,
    isFetchingNextPage: query.isFetchingNextPage,
    hasNextPage: query.hasNextPage,
    sentinelRef,
    refetch: query.refetch,
  }
}
