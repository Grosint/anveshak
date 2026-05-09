import api from './client'

export interface User {
  id: string
  username: string
  role: 'analyst' | 'admin'
  created_at: string
  updated_at: string
}

export interface CreateUserPayload {
  username: string
  password: string
  role: 'analyst' | 'admin'
}

export const usersApi = {
  list: () =>
    api.get<User[]>('/api/v1/users').then((r) => r.data),

  create: (payload: CreateUserPayload) =>
    api.post<{ user_id: string }>('/api/v1/users', payload).then((r) => r.data),

  delete: (userId: string) =>
    api.delete(`/api/v1/users/${userId}`).then((r) => r.data),

  updateRole: (userId: string, role: 'analyst' | 'admin') =>
    api.patch<{ user_id: string; role: string }>(
      `/api/v1/users/${userId}/role`, { role },
    ).then((r) => r.data),
}
