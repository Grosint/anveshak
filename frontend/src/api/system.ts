import api from './client'

export interface PipelineHealth {
  content_items_total: number
  content_items_embedded: number
  content_items_last_24h: number
  narrative_clusters_total: number
  signals_last_30d: number
  reports_last_30d: number
  sources_active: number
  sources_down: number
  content_items_zh: number
  content_items_translated: number
  extracted_entities_zh: number
}

export interface VectorHealth {
  near_duplicate_table_exists: boolean
  hnsw_index_active: boolean
  near_duplicate_count: number
  archived_cluster_count: number
  labeled_cluster_count: number
}

export interface AuditTrailEntry {
  id: string
  user_id: string
  action: string
  resource_type: string
  resource_id: string
  details: Record<string, unknown>
  ip_address: string
  created_at: string
}

export interface AuditTrailParams {
  resource_type?: string
  resource_id?: string
  limit?: number
}

export const systemApi = {
  pipelineHealth: () =>
    api.get<PipelineHealth>('/api/v1/system/pipeline-health').then((r) => r.data),

  vectorHealth: () =>
    api.get<VectorHealth>('/api/v1/system/vector-health').then((r) => r.data),

  getAuditTrail: (params?: AuditTrailParams) =>
    api.get<AuditTrailEntry[]>('/api/v1/system/audit-trail', { params }).then((r) => r.data),
}
