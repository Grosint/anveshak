import api from './client'

export interface User {
  id: string
  username: string
  role: 'viewer' | 'analyst' | 'admin'
  org_id?: string
  created_at: string
  updated_at: string
}

export interface CreateUserPayload {
  username: string
  password: string
  role: 'viewer' | 'analyst' | 'admin'
  org_id?: string
}

export const usersApi = {
  list: () =>
    api.get<User[]>('/api/v1/users').then((r) => r.data),

  create: (payload: CreateUserPayload) =>
    api.post<{ user_id: string }>('/api/v1/users', payload).then((r) => r.data),

  delete: (userId: string) =>
    api.delete(`/api/v1/users/${userId}`).then((r) => r.data),

  updateRole: (userId: string, role: 'viewer' | 'analyst' | 'admin') =>
    api.patch<{ user_id: string; role: string }>(
      `/api/v1/users/${userId}/role`, { role },
    ).then((r) => r.data),
}
