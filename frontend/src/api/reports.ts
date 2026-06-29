import api from './client'
import type { PaginatedResponse } from './types'

export type ReportType = 'intelligence_brief' | 'research_summary' | 'weekly_digest'
export type ReportStatus = 'queued' | 'complete' | 'failed'

export interface SourceWarning {
  id: string
  source_id: string
  source_name: string
  warning_type: string
  old_score: number
  new_score: number
  created_at: string
}

export interface Report {
  id: string
  topic_id: string
  report_type: ReportType
  generated_at: string | null
  generation_status: ReportStatus
  generation_error: string | null
  content_md: string | null
  confidence_score: number | null
  content_item_count: number | null
  credibility_min_filter: number
  time_window_start: string
  time_window_end: string
  source_snapshot: Record<string, { name: string; credibility_score: number }> | null
  source_warnings: SourceWarning[]
  geojson: unknown | null
  created_at: string
}

export interface ReportSummary {
  id: string
  topic_id: string
  report_type: ReportType
  generated_at: string | null
  confidence_score: number | null
  content_item_count: number | null
  created_at: string
}

export interface CreateReportPayload {
  topic_id: string
  report_type?: ReportType
  time_window_start?: string
  time_window_end?: string
  time_window_hours?: number
  credibility_min?: number
}

export const reportsApi = {
  create: (payload: CreateReportPayload) =>
    api
      .post<{ report_id: string; status: string; arq_job_id: string | null }>('/api/v1/reports', payload)
      .then((r) => r.data),

  get: (reportId: string) =>
    api.get<Report>(`/api/v1/reports/${reportId}`).then((r) => r.data),

  listForTopic: (topicId: string, offset = 0, limit = 50) =>
    api
      .get<PaginatedResponse<ReportSummary>>(`/api/v1/topics/${topicId}/reports`, {
        params: { offset, limit },
      })
      .then((r) => r.data),

  getGeojson: (reportId: string) =>
    api.get(`/api/v1/reports/${reportId}/geojson`).then((r) => r.data),

  downloadPdf: async (reportId: string, filename = `report-${reportId}.pdf`) => {
    const res = await api.get(`/api/v1/reports/${reportId}/pdf`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  },
}
