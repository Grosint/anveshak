import api from './client'

export type SignalStatus = 'new' | 'acknowledged' | 'dismissed'

export interface Signal {
  id: string
  topic_id: string
  cluster_id: string | null
  signal_type: string
  description: string
  evidence: unknown
  status: SignalStatus
  created_at: string
  cluster_label: string | null
  independent_source_count: number | null
}

export const signalsApi = {
  list: (status: SignalStatus = 'new', since?: string, until?: string) =>
    api.get<Signal[]>('/api/v1/signals', {
      params: { status, ...(since ? { since } : {}), ...(until ? { until } : {}) },
    }).then((r) => r.data),

  acknowledge: (signalId: string) =>
    api.patch<{ signal_id: string; status: string }>(`/api/v1/signals/${signalId}/acknowledge`).then((r) => r.data),

  dismiss: (signalId: string) =>
    api.patch<{ signal_id: string; status: string }>(`/api/v1/signals/${signalId}/dismiss`).then((r) => r.data),
}
