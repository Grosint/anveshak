import api from './client'

/**
 * Actor View — issue #35.
 *
 * A query over content items, never a stored record. There is no create,
 * update or delete here, and there is no actor endpoint that writes.
 */

export interface ActorSummary {
  post_count?: number
  source_count?: number
  platform_count?: number
  platforms?: string[] | null
  first_seen?: string | null
  last_seen?: string | null
  total_likes?: number
  total_views?: number
  total_shares?: number
}

export interface ActorContentItem {
  id: string
  url: string | null
  title: string | null
  clean_text: string
  translated_text?: string | null
  language: string
  captured_at: string
  published_at: string | null
  stance: string | null
  hostility: number | null
  source_name: string | null
  platform: string | null
  cluster_label: string | null
  narrative_cluster_id: string | null
  engagement: Record<string, number> | null
}

export interface ActorActivityPoint {
  day: string
  post_count: number
  /** Posts plotted at collection time because the platform gave no publication time. */
  approximate_count: number
  total_likes: number
}

export interface Actor {
  handle: string
  topic_id: string
  summary: ActorSummary
  content: ActorContentItem[]
  activity: ActorActivityPoint[]
}

export const actorsApi = {
  get: (topicId: string, handle: string, params?: { days?: number; limit?: number }) =>
    api
      .get<Actor>(
        `/api/v1/topics/${topicId}/actors/${encodeURIComponent(handle)}`,
        { params },
      )
      .then((r) => r.data),
}
