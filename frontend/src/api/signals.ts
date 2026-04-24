import api from './client'

export type SignalStatus = 'new' | 'acknowledged' | 'dismissed'

export interface SignalSource {
  source_name: string
  platform: string
  credibility_score: number
}

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
  cluster_item_count: number | null
  executive_summary: string | null
  topic_name: string | null
  sources: SignalSource[]
  first_seen: string | null
  last_seen: string | null
}

export interface GraphNode {
  id: string
  type: 'signal' | 'cluster' | 'content' | 'source' | 'cross_signal'
  label: string
  data: Record<string, unknown>
}

export interface GraphEdge {
  source: string
  target: string
  type: 'triggers' | 'contains' | 'from_source' | 'converges_with'
}

export interface SignalConnections {
  nodes: GraphNode[]
  edges: GraphEdge[]
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

  connections: (signalId: string) =>
    api.get<SignalConnections>(`/api/v1/signals/${signalId}/connections`).then((r) => r.data),
}
