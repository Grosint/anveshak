import api from './client'

export interface AlertRule {
  id: string
  topic_id: string
  keywords: string[]
  match_mode: 'any' | 'all'
  is_active: boolean
  created_at: string
}

export interface AlertTrigger {
  id: string
  rule_id: string
  content_item_id: string
  matched_keywords: string[]
  triggered_at: string
  url: string
  content_snippet: string
  rule_keywords: string[]
}

export const alertsApi = {
  listRules: (topicId: string) =>
    api.get<AlertRule[]>(`/api/v1/topics/${topicId}/alerts`).then((r) => r.data),

  createRule: (topicId: string, keywords: string[], matchMode = 'any') =>
    api.post<{ id: string }>(`/api/v1/topics/${topicId}/alerts`, { keywords, match_mode: matchMode }).then((r) => r.data),

  updateRule: (topicId: string, ruleId: string, data: Partial<AlertRule>) =>
    api.patch<AlertRule>(`/api/v1/topics/${topicId}/alerts/${ruleId}`, data).then((r) => r.data),

  deleteRule: (topicId: string, ruleId: string) =>
    api.delete(`/api/v1/topics/${topicId}/alerts/${ruleId}`).then((r) => r.data),

  listTriggers: (topicId: string, limit = 50) =>
    api.get<AlertTrigger[]>(`/api/v1/topics/${topicId}/alerts/triggers`, { params: { limit } }).then((r) => r.data),
}
