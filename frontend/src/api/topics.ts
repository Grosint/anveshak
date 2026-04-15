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

export interface Cluster {
  id: string
  label: string | null
  item_count: number
  independent_source_count: number
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
}
