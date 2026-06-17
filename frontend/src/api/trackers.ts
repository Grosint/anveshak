import api from './client'

export interface Tracker {
  id: string
  case_number: string
  org_id?: string
  topic_id: string
  origin_cluster_id?: string
  title: string
  external_case_ref?: string
  status: 'watching' | 'active' | 'concluded'
  priority: 'low' | 'medium' | 'high' | 'critical'
  assigned_to?: string
  created_by: string
  concluded_by?: string
  concluded_at?: string
  closing_summary?: string
  content_count: number
  pending_count: number
  created_at: string
  updated_at: string
}

export interface TrackerContentItem {
  id: string
  url?: string
  clean_text?: string
  language?: string
  credibility_score_at_capture?: number
  captured_at: string
  source_name?: string
  platform?: string
  attached_by: 'seed' | 'auto' | 'manual'
  status: 'pending' | 'confirmed'
  similarity_score?: number
  confirmed_by?: string
  confirmed_at?: string
  attached_at: string
}

export interface TrackerNote {
  id: string
  tracker_id: string
  user_id: string
  body: string
  created_at: string
}

export interface TrackerAuditEntry {
  id: string
  tracker_id: string
  action: string
  actor_id: string
  detail: Record<string, unknown>
  created_at: string
}

export const trackersApi = {
  list: (params?: { topic_id?: string; status?: string }) =>
    api.get<Tracker[]>('/api/v1/trackers', { params }).then((r) => r.data),

  get: (id: string) =>
    api.get<Tracker>(`/api/v1/trackers/${id}`).then((r) => r.data),

  create: (data: {
    title: string
    topic_id: string
    external_case_ref?: string
    priority?: string
    status?: string
  }) => api.post<Tracker>('/api/v1/trackers', data).then((r) => r.data),

  createFromCluster: (
    clusterId: string,
    data?: { external_case_ref?: string; priority?: string; status?: string }
  ) =>
    api
      .post<Tracker>(`/api/v1/trackers/from-cluster/${clusterId}`, data || {})
      .then((r) => r.data),

  updateStatus: (id: string, data: { status: string; closing_summary?: string }) =>
    api.patch(`/api/v1/trackers/${id}/status`, data).then((r) => r.data),

  updatePriority: (id: string, data: { priority: string }) =>
    api.patch(`/api/v1/trackers/${id}/priority`, data).then((r) => r.data),

  assign: (id: string, data: { assigned_to?: string }) =>
    api.patch(`/api/v1/trackers/${id}/assign`, data).then((r) => r.data),

  update: (id: string, data: { title?: string; external_case_ref?: string }) =>
    api.patch(`/api/v1/trackers/${id}`, data).then((r) => r.data),

  listContent: (id: string, params?: { limit?: number; offset?: number }) =>
    api
      .get<TrackerContentItem[]>(`/api/v1/trackers/${id}/content`, { params })
      .then((r) => r.data),

  listPending: (id: string) =>
    api.get<TrackerContentItem[]>(`/api/v1/trackers/${id}/pending`).then((r) => r.data),

  confirmItem: (id: string, itemId: string) =>
    api.post(`/api/v1/trackers/${id}/content/${itemId}/confirm`).then((r) => r.data),

  rejectItem: (id: string, itemId: string) =>
    api.post(`/api/v1/trackers/${id}/content/${itemId}/reject`).then((r) => r.data),

  confirmAll: (id: string) =>
    api.post(`/api/v1/trackers/${id}/content/confirm-all`).then((r) => r.data),

  addContent: (id: string, itemId: string) =>
    api.post(`/api/v1/trackers/${id}/content/${itemId}`).then((r) => r.data),

  addNote: (id: string, data: { body: string }) =>
    api.post<TrackerNote>(`/api/v1/trackers/${id}/notes`, data).then((r) => r.data),

  listNotes: (id: string) =>
    api.get<TrackerNote[]>(`/api/v1/trackers/${id}/notes`).then((r) => r.data),

  listSignals: (id: string) =>
    api.get(`/api/v1/trackers/${id}/signals`).then((r) => r.data),

  linkSignal: (id: string, signalId: string) =>
    api.post(`/api/v1/trackers/${id}/signals/${signalId}`).then((r) => r.data),

  listAuditLog: (id: string, params?: { limit?: number; offset?: number }) =>
    api
      .get<TrackerAuditEntry[]>(`/api/v1/trackers/${id}/audit-log`, { params })
      .then((r) => r.data),
}
