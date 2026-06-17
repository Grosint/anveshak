import api from './client'

export type IdentifierType =
  | 'PHONE_IN'
  | 'UPI'
  | 'EMAIL'
  | 'CRYPTO_BTC'
  | 'CRYPTO_ETH'
  | 'CRYPTO_TRC20'
  | 'TELEGRAM_HANDLE'
  | 'INSTAGRAM_HANDLE'
  | 'URL_DOMAIN'
  | 'GSTIN'
  | 'UDYAM'
  | 'PAN'
  | 'IFSC'
  | 'BANK_ACCOUNT'
  | 'SEBI_REG'

export interface IdentifierResult {
  entity_type: IdentifierType
  entity_text: string
  confidence: number
  content_item_id: string
  content_url: string | null
  source_name: string
  source_platform: string
  captured_at: string
}

export interface TopIdentifier {
  identifier_type: IdentifierType
  identifier_value: string
  source_count: number
  content_item_count: number
  first_seen_at: string | null
  last_seen_at: string | null
}

export interface IdentifierCluster {
  id: string
  topic_id: string
  identifier_type: IdentifierType
  identifier_value: string
  source_count: number
  content_item_count: number
  first_seen_at: string | null
  last_seen_at: string | null
  created_at: string
}

export interface ClusterDetail {
  id: string
  topic_id: string
  identifier_type: IdentifierType
  identifier_value: string
  source_count: number
  content_item_count: number
  first_seen_at: string | null
  last_seen_at: string | null
  items: {
    content_item_id: string
    url: string | null
    clean_text: string
    source_name: string
    platform: string
    captured_at: string
  }[]
}

export interface GlobalSearchResult {
  identifier_type: IdentifierType
  identifier_value: string
  topic_id: string
  topic_name: string
  source_count: number
  content_item_count: number
  last_seen_at: string | null
}

export interface CoOccurrenceResult {
  topic_id: string
  identifier_a: string
  identifier_b: string
  items: Record<string, unknown>[]
  count: number
}

export interface ScamTemplate {
  id: string
  name: string
  display: string
  category: string
  keywords: string[]
  expected_identifiers: string[]
  severity: string
  legal_sections: string[]
  is_builtin: boolean
}

export const identifiersApi = {
  searchGlobal: (q: string, type?: IdentifierType, limit = 50) =>
    api
      .get<GlobalSearchResult[]>('/api/v1/identifiers/search-global', {
        params: { q, ...(type ? { type } : {}), limit },
      })
      .then((r) => r.data),

  search: (topicId: string, q: string, type?: IdentifierType, limit = 50) =>
    api
      .get<IdentifierResult[]>('/api/v1/identifiers/search', {
        params: { topic_id: topicId, q, ...(type ? { type } : {}), limit },
      })
      .then((r) => r.data),

  top: (topicId: string, type?: IdentifierType, limit = 20) =>
    api
      .get<TopIdentifier[]>('/api/v1/identifiers/top', {
        params: { topic_id: topicId, ...(type ? { type } : {}), limit },
      })
      .then((r) => r.data),

  clusters: (topicId: string, type?: IdentifierType, limit = 50, offset = 0) =>
    api
      .get<IdentifierCluster[]>('/api/v1/identifiers/clusters', {
        params: { topic_id: topicId, ...(type ? { type } : {}), limit, offset },
      })
      .then((r) => r.data),

  clusterDetail: (clusterId: string, topicId: string) =>
    api
      .get<ClusterDetail>(`/api/v1/identifiers/clusters/${clusterId}`, {
        params: { topic_id: topicId },
      })
      .then((r) => r.data),

  coOccurrence: (topicId: string, a: string, b: string, limit = 100) =>
    api
      .get<CoOccurrenceResult>('/api/v1/identifiers/co-occurrence', {
        params: { topic_id: topicId, identifier_a: a, identifier_b: b, limit },
      })
      .then((r) => r.data),

  listTopicTemplates: (topicId: string) =>
    api
      .get<ScamTemplate[]>(`/api/v1/identifiers/topics/${topicId}/templates`)
      .then((r) => r.data),

  linkTemplate: (topicId: string, templateId: string) =>
    api
      .post<{ status: string }>(`/api/v1/identifiers/topics/${topicId}/templates/${templateId}`)
      .then((r) => r.data),

  unlinkTemplate: (topicId: string, templateId: string) =>
    api
      .delete<{ status: string }>(`/api/v1/identifiers/topics/${topicId}/templates/${templateId}`)
      .then((r) => r.data),
}
