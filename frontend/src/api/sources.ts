import api from './client'

export type Platform = 'web' | 'telegram' | 'twitter' | 'reddit' | 'bluesky' | 'rss' | 'upload'

export interface Source {
  id: string
  name: string
  platform: Platform
  credibility_score: number
  is_active: boolean
  last_checked_at: string | null
}

export interface AuditEntry {
  id: string
  source_id: string
  old_score: number
  new_score: number
  reason: string
  changed_by: string
  created_at: string
}

export interface CreateSourcePayload {
  name: string
  url_or_handle: string
  platform: Platform
  credibility_score?: number
}

export const sourcesApi = {
  list: () =>
    api.get<Source[]>('/api/v1/sources').then((r) => r.data),

  create: (payload: CreateSourcePayload) =>
    api.post<{ id: string; name: string }>('/api/v1/sources', payload).then((r) => r.data),

  updateCredibility: (sourceId: string, newScore: number, reason: string) =>
    api
      .patch<{ source_id: string; old_score: number; new_score: number }>(
        `/api/v1/sources/${sourceId}/credibility`,
        null,
        { params: { new_score: newScore, reason } },
      )
      .then((r) => r.data),

  getAuditLog: (sourceId: string) =>
    api.get<AuditEntry[]>(`/api/v1/sources/${sourceId}/audit-log`).then((r) => r.data),

  toggleActive: (sourceId: string, isActive: boolean) =>
    api
      .patch<{ source_id: string; is_active: boolean }>(
        `/api/v1/sources/${sourceId}/active`,
        null,
        { params: { is_active: isActive } },
      )
      .then((r) => r.data),

  getReportWarningsCount: (sourceId: string) =>
    api
      .get<{ source_id: string; warning_count: number }>(`/api/v1/sources/${sourceId}/report-warnings/count`)
      .then((r) => r.data),
}
