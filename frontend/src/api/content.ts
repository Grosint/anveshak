import api from './client'

export interface ContentItem {
  id: string
  url: string
  clean_text: string
  translated_text?: string | null
  translation_model?: string | null
  language: string
  credibility_score_at_capture: number
  captured_at: string
  backfilled: boolean
  // Detail-only fields (GET /api/v1/content/{id})
  source_name?: string
  platform?: string
  content_hash?: string
  topic_id?: string
  source_id?: string
  extracted_entities?: Entity[]
}

export interface Entity {
  id: string
  entity_type: string
  entity_text: string
  confidence: number
  language: string
  created_at: string
}

export interface SearchResult extends Omit<ContentItem, 'backfilled' | 'extracted_entities'> {
  similarity_score: number
}

export interface ContentFilters {
  language?: string
  credibility_min?: number
  date_from?: string
  date_to?: string
  has_embedding?: boolean
}

export const contentApi = {
  list: (topicId: string, offset = 0, limit = 50) =>
    api
      .get<ContentItem[]>(`/api/v1/topics/${topicId}/content`, { params: { offset, limit } })
      .then((r) => r.data),

  get: (contentId: string) =>
    api.get<ContentItem>(`/api/v1/content/${contentId}`).then((r) => r.data),

  search: (q: string, topicId: string) =>
    api.get<SearchResult[]>('/api/v1/search', { params: { q, topic_id: topicId } }).then((r) => r.data),

  getVision: (contentId: string) =>
    api.get(`/api/v1/content/${contentId}/vision`).then((r) => r.data),
}
