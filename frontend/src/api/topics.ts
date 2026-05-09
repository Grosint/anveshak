import api from './client'

export interface Topic {
  id: string
  name: string
  status: 'active' | 'paused' | 'archived'
  signal_threshold: number
  credibility_min: number
  created_at: string
  content_count?: number
  signal_count?: number
  keywords?: string[]
  languages?: string[]
  clip_categories?: string[]
  scheduled_report_cron?: string | null
  scheduled_report_type?: string | null
}

export interface ClusterSource {
  source_name: string
  platform: string
  credibility_score: number
}

export interface Cluster {
  id: string
  label: string | null
  item_count: number
  independent_source_count: number
  executive_summary: string | null
  sources: ClusterSource[]
  created_at: string
}

export interface CreateTopicPayload {
  name: string
  keywords: string[]
  languages?: string[]
  credibility_min?: number
  signal_threshold?: number
  clip_categories?: string[]
  scheduled_report_cron?: string | null
  scheduled_report_type?: string | null
}

export interface TopicSource {
  id: string
  name: string
  url_or_handle: string
  platform: string
  credibility_score: number
  is_active: boolean
  health_status: string
  added_at: string
  item_count: number
}

export const topicsApi = {
  list: () =>
    api.get<Topic[]>('/api/v1/topics').then((r) => r.data),

  get: (topicId: string) =>
    api.get<Topic>(`/api/v1/topics/${topicId}`).then((r) => r.data),

  create: (payload: CreateTopicPayload) =>
    api.post<{ id: string; name: string; status: string }>('/api/v1/topics', payload).then((r) => r.data),

  updateStatus: (topicId: string, status: 'active' | 'paused' | 'archived') =>
    api.patch<{ topic_id: string; status: string }>(`/api/v1/topics/${topicId}/status`, { status }).then((r) => r.data),

  listClusters: (topicId: string) =>
    api.get<Cluster[]>(`/api/v1/topics/${topicId}/clusters`).then((r) => r.data),

  listSources: (topicId: string) =>
    api.get<TopicSource[]>(`/api/v1/topics/${topicId}/sources`).then((r) => r.data),

  linkSource: (topicId: string, sourceId: string) =>
    api.post<{ topic_id: string; source_id: string; status: string }>(
      `/api/v1/topics/${topicId}/sources/${sourceId}`,
    ).then((r) => r.data),

  unlinkSource: (topicId: string, sourceId: string) =>
    api.delete<{ topic_id: string; source_id: string; status: string }>(
      `/api/v1/topics/${topicId}/sources/${sourceId}`,
    ).then((r) => r.data),

  sentimentTrend: (topicId: string, days = 30) =>
    api.get<{ date: string; avg_compound: number; item_count: number }[]>(
      `/api/v1/topics/${topicId}/sentiment-trend`, { params: { days } },
    ).then((r) => r.data),

  trendingKeywords: (topicId: string, days = 7, limit = 15) =>
    api.get<{ keyword: string; frequency: number }[]>(
      `/api/v1/topics/${topicId}/trending-keywords`, { params: { days, limit } },
    ).then((r) => r.data),

  updateSchedule: (topicId: string, cron: string | null, reportType: string | null) =>
    api.patch<{ topic_id: string; scheduled_report_cron: string | null; scheduled_report_type: string | null }>(
      `/api/v1/topics/${topicId}/schedule`,
      { scheduled_report_cron: cron, scheduled_report_type: reportType },
    ).then((r) => r.data),
}
