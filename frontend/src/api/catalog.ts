import api from './client'
import type { Platform } from './sources'

export type ReliabilityTier = 'S' | 'A' | 'B' | 'C'
export type RecommendationRank = 'most_recommended' | 'proven' | 'curated' | 'low_performer'
export type DiscoveryMethod = 'snowball' | 'forwarding' | 'entity_search' | 'llm_suggestion'
export type DiscoveryStatus = 'pending' | 'approved' | 'dismissed'

export interface CatalogEntry {
  id: string
  name: string
  url_or_handle: string
  platform: Platform
  domain_tags: string[]
  reliability_tier: ReliabilityTier
  bias_indicator: string
  risk_level: string
  language: string
  category: string
  description: string
  subscriber_count: number | null
  activity_frequency: string
  signal_contribution_count: number
  relevance_hit_rate: number | null
  cluster_participation_rate: number | null
  topics_approved_count: number
  recommendation_rank: RecommendationRank
  created_at: string
  updated_at: string
}

export interface DiscoveredSource {
  id: string
  topic_id: string
  domain_or_handle: string
  platform: Platform | string
  discovery_method: DiscoveryMethod
  citation_count: number
  confidence_score: number | null
  evidence: Record<string, unknown>
  status: DiscoveryStatus
  source_id: string | null
  created_at: string
  updated_at: string
}

export const catalogApi = {
  /** Get catalog suggestions for a topic (matches by keyword overlap) */
  suggestions: (topicId: string) =>
    api.get<{ topic_id: string; suggestions: CatalogEntry[]; total: number }>(
      `/api/v1/topics/${topicId}/catalog-suggestions`
    ).then(r => r.data),

  /** Approve a catalog entry for a topic — creates source + links */
  approve: (topicId: string, catalogEntryId: string) =>
    api.post<{ catalog_entry_id: string; source_id: string; topic_id: string; name: string }>(
      `/api/v1/topics/${topicId}/catalog-approve`,
      null,
      { params: { catalog_entry_id: catalogEntryId } }
    ).then(r => r.data),

  /** List all catalog entries (admin) */
  listAll: () =>
    api.get<{ entries: CatalogEntry[]; total: number }>('/api/v1/catalog').then(r => r.data),

  /** List discovered sources for a topic */
  discovered: (topicId: string, status?: DiscoveryStatus) =>
    api.get<{ topic_id: string; discovered: DiscoveredSource[]; total: number }>(
      `/api/v1/topics/${topicId}/discovered`,
      { params: status ? { status } : {} }
    ).then(r => r.data),

  /** Approve a discovered source */
  approveDiscovered: (topicId: string, discoveredId: string) =>
    api.post<{ discovered_id: string; source_id: string }>(
      `/api/v1/topics/${topicId}/discovered/${discoveredId}/approve`
    ).then(r => r.data),

  /** Dismiss a discovered source */
  dismissDiscovered: (topicId: string, discoveredId: string) =>
    api.post<{ discovered_id: string; status: string }>(
      `/api/v1/topics/${topicId}/discovered/${discoveredId}/dismiss`
    ).then(r => r.data),
}
