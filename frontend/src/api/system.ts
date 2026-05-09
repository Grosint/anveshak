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

export const systemApi = {
  pipelineHealth: () =>
    api.get<PipelineHealth>('/api/v1/system/pipeline-health').then((r) => r.data),

  vectorHealth: () =>
    api.get<VectorHealth>('/api/v1/system/vector-health').then((r) => r.data),
}
