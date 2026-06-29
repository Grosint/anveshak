/** Standard paginated response envelope from backend. */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  offset: number
  limit: number
}
