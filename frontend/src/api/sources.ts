import api from './client'
import type { PaginatedResponse } from './types'

export type Platform = 'web' | 'telegram' | 'twitter' | 'reddit' | 'bluesky' | 'rss' | 'upload' | 'darkweb'

export type HealthStatus = 'healthy' | 'degraded' | 'down' | 'unverified'

export interface Source {
  id: string
  name: string
  url_or_handle: string
  platform: Platform
  credibility_score: number
  is_active: boolean
  health_status: HealthStatus
  consecutive_failures: number
  health_error: string | null
  last_checked_at: string | null
  topic_links_count: number
}

export interface HealthCheckResult {
  source_id: string
  health_status: HealthStatus
  consecutive_failures: number
  health_error: string | null
  checked_at: string
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
  topic_ids?: string[]
}

export interface UpdateSourcePayload {
  name?: string
  url_or_handle?: string
}

export const sourcesApi = {
  list: (offset = 0, limit = 50) =>
    api.get<PaginatedResponse<Source>>('/api/v1/sources', { params: { offset, limit } }).then((r) => r.data),

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

  checkHealth: (sourceId: string) =>
    api
      .post<HealthCheckResult>(`/api/v1/sources/${sourceId}/check-health`)
      .then((r) => r.data),

  update: (sourceId: string, payload: UpdateSourcePayload) =>
    api.patch<{ source_id: string }>(`/api/v1/sources/${sourceId}`, payload).then((r) => r.data),

  delete: (sourceId: string, force = false) =>
    api.delete(`/api/v1/sources/${sourceId}`, { params: force ? { force: true } : {} }),
}
