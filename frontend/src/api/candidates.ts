import api from './client'

/**
 * Candidate Topic inbox — issues #26 and #27.
 *
 * A candidate is a narrative that surfaced inside a Watch Space and is
 * waiting on an analyst decision. Nothing is monitored until that decision.
 */

export interface CandidateMeasurements {
  independent_source_count?: number
  item_count?: number
  novelty_score?: number
  run_count?: number
  thresholds?: {
    min_independent_sources?: number
    min_item_count?: number
    min_novelty?: number
    min_runs?: number
  }
}

export interface CandidateTopic {
  id: string
  cluster_id: string
  watch_space_id: string
  watch_space_name: string | null
  cluster_label: string | null
  status: 'pending' | 'accepted' | 'dismissed'
  independent_source_count: number
  item_count: number
  contributing_account_count: number
  novelty_score: number | null
  run_count: number
  evidence: { measurements?: CandidateMeasurements; failed_gates?: string[] } | null
  created_at: string
  promoted_topic_id: string | null
}

export interface AcceptResult {
  candidate_id: string
  topic_id: string
  name: string
  content_items_linked: number
}

export const candidatesApi = {
  list: (status: 'pending' | 'accepted' | 'dismissed' = 'pending') =>
    api
      .get<CandidateTopic[]>('/api/v1/candidate-topics', {
        params: { candidate_status: status },
      })
      .then((r) => r.data),

  accept: (candidateId: string, payload: { name?: string; keywords?: string[] }) =>
    api
      .post<AcceptResult>(`/api/v1/candidate-topics/${candidateId}/accept`, payload)
      .then((r) => r.data),

  dismiss: (candidateId: string) =>
    api
      .post<{ candidate_id: string; status: string }>(
        `/api/v1/candidate-topics/${candidateId}/dismiss`,
      )
      .then((r) => r.data),
}
