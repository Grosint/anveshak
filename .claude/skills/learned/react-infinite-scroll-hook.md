# Pattern: Infinite Scroll with IntersectionObserver + React Query

## When to load: implementing paginated content feeds in the frontend

---

## The pattern

Combines `useInfiniteQuery` (React Query) with a sentinel `<div>` watched by
`IntersectionObserver`. When the sentinel enters the viewport, `fetchNextPage()` fires.
Client-side filters are applied after fetch — this avoids refetch storms when only
filter state changes (e.g. language filter).

```ts
// hooks/useInfiniteContent.ts
import { useInfiniteQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

export interface ContentFilters {
  language?: string
  credibilityMin?: number
  dateFrom?: string
  dateTo?: string
  platform?: string
}

export function useInfiniteContent(topicId: string, filters: ContentFilters) {
  const sentinelRef = useRef<HTMLDivElement | null>(null)

  const query = useInfiniteQuery({
    queryKey: ['content', topicId],
    queryFn: ({ pageParam = 0 }) =>
      contentApi.list(topicId, { limit: 50, offset: pageParam as number }),
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length === 50 ? allPages.flat().length : undefined,
    initialPageParam: 0,
  })

  // IntersectionObserver sentinel
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && query.hasNextPage && !query.isFetchingNextPage) {
          query.fetchNextPage()
        }
      },
      { threshold: 0.1 },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [query])

  // Flatten pages + apply client-side filters
  const allItems = query.data?.pages.flat() ?? []
  const filtered = applyClientFilters(allItems, filters)

  return { items: filtered, sentinelRef, isLoading: query.isLoading, isFetchingNext: query.isFetchingNextPage }
}

function applyClientFilters(items: ContentItem[], filters: ContentFilters): ContentItem[] {
  return items.filter((item) => {
    if (filters.language && item.language !== filters.language) return false
    if (filters.credibilityMin != null && item.credibility_score_at_capture < filters.credibilityMin) return false
    if (filters.platform && item.platform !== filters.platform) return false
    if (filters.dateFrom && new Date(item.captured_at) < new Date(filters.dateFrom)) return false
    if (filters.dateTo   && new Date(item.captured_at) > new Date(filters.dateTo))   return false
    return true
  })
}
```

```tsx
// Usage in page component
export default function ContentFeed({ topicId }: { topicId: string }) {
  const [filters, setFilters] = useState<ContentFilters>({})
  const { items, sentinelRef, isLoading, isFetchingNext } = useInfiniteContent(topicId, filters)

  return (
    <div>
      <FilterBar filters={filters} onChange={setFilters} />
      {items.map((item) => <ContentCard key={item.id} item={item} />)}
      {/* Sentinel — must be inside the scrollable container */}
      <div ref={sentinelRef} className="h-4" aria-hidden="true" />
      {isFetchingNext && <Spinner label="Loading more…" />}
    </div>
  )
}
```

## Key decisions

| Decision | Why |
|----------|-----|
| Client-side filters | Avoids refetch on every filter change; all pages stay cached |
| `queryKey: ['content', topicId]` — no filters | Filters apply after fetch, so cache is shared across filter states |
| `threshold: 0.1` | Triggers before user reaches very bottom — feels instant |
| `limit: 50` per page | Enough to fill screen, small enough for <500ms API response |
| `getNextPageParam` returns `undefined` when `lastPage.length < 50` | Signals end of data; `hasNextPage` becomes false |

## When to use server-side filtering instead

Use server-side filtering when:
- The dataset is large (>10K items) and client-side filtering would be slow
- Filters have low cardinality with distinct API endpoints (e.g. `platform=telegram`)
- In that case, add filter params to `queryKey` so each filter combination has its own cache

```ts
// Server-side filtering — queryKey includes filters
queryKey: ['content', topicId, filters.platform],
queryFn: ({ pageParam }) => contentApi.list(topicId, { platform: filters.platform, offset: pageParam }),
```
