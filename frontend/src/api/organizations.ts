import api from './client'

export interface Organization {
  id: string
  name: string
  slug: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CreateOrgPayload {
  name: string
  slug: string
}

export interface UpdateOrgPayload {
  name?: string
  is_active?: boolean
}

export const organizationsApi = {
  list: () =>
    api.get<Organization[]>('/api/v1/organizations').then((r) => r.data),

  create: (payload: CreateOrgPayload) =>
    api.post<{ org_id: string }>('/api/v1/organizations', payload).then((r) => r.data),

  get: (orgId: string) =>
    api.get<Organization>(`/api/v1/organizations/${orgId}`).then((r) => r.data),

  update: (orgId: string, payload: UpdateOrgPayload) =>
    api.patch<{ org_id: string; updated: boolean }>(
      `/api/v1/organizations/${orgId}`, payload,
    ).then((r) => r.data),
}
