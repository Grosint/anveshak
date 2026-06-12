import api from './client'

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
  is_active: boolean
  created_at: string
  linked_at?: string
}

export const templatesApi = {
  list: () =>
    api.get<ScamTemplate[]>('/api/v1/templates').then((r) => r.data),

  get: (templateId: string) =>
    api.get<ScamTemplate>(`/api/v1/templates/${templateId}`).then((r) => r.data),

  listForTopic: (topicId: string) =>
    api.get<ScamTemplate[]>(`/api/v1/topics/${topicId}/templates`).then((r) => r.data),

  link: (topicId: string, templateId: string) =>
    api.post(`/api/v1/topics/${topicId}/templates/${templateId}`).then((r) => r.data),

  unlink: (topicId: string, templateId: string) =>
    api.delete(`/api/v1/topics/${topicId}/templates/${templateId}`).then((r) => r.data),
}
