import api from './client'

/**
 * Sentiment Timeline — issue #29.
 *
 * Supporting and opposing volume as separate series over publication time,
 * with mean hostility overlaid.
 */

export interface TimelineBucket {
  bucket: string
  supporting: number
  opposing: number
  neutral: number
  /** Content in a language or script the models handle poorly. */
  unsupported_language: number
  /** Content the scoring pass has not reached yet. */
  unscored: number
  total: number
  mean_hostility: number | null
  hostility_sample_count: number
}

export interface ConstrainedPlatform {
  platform: string
  earliest_published_at: string | null
  item_count: number
}

export interface SentimentTimeline {
  topic_id: string
  bucket: 'day' | 'week'
  days: number
  as_percentage: boolean
  buckets: TimelineBucket[]
  /** Items with no publication time. Excluded from the plot, reported here. */
  excluded_no_publication_time: number
  /** Platforms whose search window bounds how far back the chart reaches. */
  constrained_platforms: ConstrainedPlatform[]
}

export const timelineApi = {
  get: (topicId: string, params?: { days?: number; as_percentage?: boolean }) =>
    api
      .get<SentimentTimeline>(`/api/v1/topics/${topicId}/sentiment-timeline`, { params })
      .then((r) => r.data),
}
