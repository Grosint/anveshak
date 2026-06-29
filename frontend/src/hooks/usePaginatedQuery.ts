import { useState } from 'react'
import { useQuery, type QueryKey } from '@tanstack/react-query'
import type { PaginatedResponse } from '../api/types'

interface UsePaginatedQueryOptions<T> {
  queryKey: QueryKey
  fetcher: (offset: number, limit: number) => Promise<PaginatedResponse<T>>
  pageSize?: number
  staleTime?: number
  enabled?: boolean
}

export function usePaginatedQuery<T>({
  queryKey,
  fetcher,
  pageSize = 25,
  staleTime = 30_000,
  enabled = true,
}: UsePaginatedQueryOptions<T>) {
  const [page, setPage] = useState(0)
  const offset = page * pageSize

  const query = useQuery({
    queryKey: [...queryKey, { page, pageSize }],
    queryFn: () => fetcher(offset, pageSize),
    staleTime,
    enabled,
  })

  return {
    items: query.data?.items ?? [],
    total: query.data?.total ?? 0,
    page,
    setPage,
    pageSize,
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  }
}
