import { useInfiniteQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { contentApi, ContentFilters } from '../api/content'
import { applyClientFilters } from '../lib/domain'

const PAGE_SIZE = 50

export function useInfiniteContent(topicId: string, filters: ContentFilters = {}, enabled = true) {
  const query = useInfiniteQuery({
    queryKey: ['content', topicId, filters],
    queryFn: ({ pageParam }) => contentApi.list(topicId, pageParam as number, PAGE_SIZE, filters.sentiment, filters.sort_by),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      if (!lastPage || lastPage.length < PAGE_SIZE) return undefined
      return allPages.flat().length
    },
    staleTime: 30_000,
    enabled: enabled && !!topicId,
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
