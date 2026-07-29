import api from './client'

// ── Topic Intelligence (aggregated overview) ──────────────────────────

export interface IntelSignal {
  id: string
  signal_type: string
  description: string
  status: string
  fired_at: string
  cluster_label: string | null
  isc: number
}

export interface IntelCluster {
  id: string
  label: string | null
  item_count: number
  isc: number
  executive_summary: string | null
  created_at: string
  growth_24h: number
  growth_rate: number | null
  max_deepfake_score: number | null
}

export interface IntelIdentifier {
  identifier_type: string
  identifier_value: string
  mention_count: number
  source_count: number
}

export interface IntelLocation {
  location_name: string
  latitude: number
  longitude: number
  content_count: number
}

export interface IntelSourceHealth {
  id: string
  name: string
  platform: string
  health_status: string
  credibility_score: number
}

export interface IntelStats {
  total_content: number
  total_clusters: number
  total_signals: number
}

export interface TopicIntelligence {
  signals: IntelSignal[]
  clusters: IntelCluster[]
  identifiers: IntelIdentifier[]
  locations: IntelLocation[]
  source_health: IntelSourceHealth[]
  stats: IntelStats
}

// ── Entity Graph ──────────────────────────────────────────────────────

export interface EntityNode {
  entity: string
  type: string
}

export interface EntityEdge {
  entity_a: string
  type_a: string
  entity_b: string
  type_b: string
  count: number
}

export interface EntityGraph {
  topic_id: string
  nodes: EntityNode[]
  edges: EntityEdge[]
  node_count: number
  edge_count: number
}

export const intelligenceApi = {
  topicIntelligence: (topicId: string) =>
    api
      .get<TopicIntelligence>(`/api/v1/topics/${topicId}/intelligence`)
      .then((r) => r.data),

  entityGraph: (topicId: string, minCount = 2, limit = 100) =>
    api
      .get<EntityGraph>(`/api/v1/topics/${topicId}/entity-graph`, {
        params: { min_count: minCount, limit },
      })
      .then((r) => r.data),

  locationMap: (topicId: string, minMentions = 2, limit = 100) =>
    api
      .get<GeoJSON.FeatureCollection & { metadata?: { total_extracted: number; geocoded: number; unresolved: string[] } }>(`/api/v1/topics/${topicId}/location-map-v2`, {
        params: { min_mentions: minMentions, limit },
      })
      .then((r) => r.data),

  locationTimeline: (topicId: string) =>
    api
      .get<{ locations: { name: string; timeline: { week: string; count: number }[] }[] }>(`/api/v1/topics/${topicId}/location-timeline`)
      .then((r) => r.data),

  locationContent: (topicId: string, entity: string, limit = 20) =>
    api
      .get<{ id: string; title: string; url: string; captured_at: string | null; source_name: string; platform: string; sentiment_compound: number | null }[]>(
        `/api/v1/topics/${topicId}/location/${encodeURIComponent(entity)}/content`,
        { params: { limit } },
      )
      .then((r) => r.data),

  listPins: (topicId: string) =>
    api
      .get<{ id: string; latitude: number; longitude: number; label: string; analyst_id: string; created_at: string }[]>(
        `/api/v1/topics/${topicId}/pins`,
      )
      .then((r) => r.data),

  createPin: (topicId: string, latitude: number, longitude: number, label: string) =>
    api
      .post<{ id: string; latitude: number; longitude: number; label: string }>(
        `/api/v1/topics/${topicId}/pins`,
        { latitude, longitude, label },
      )
      .then((r) => r.data),

  deletePin: (topicId: string, pinId: string) =>
    api
      .delete<{ status: string }>(`/api/v1/topics/${topicId}/pins/${pinId}`)
      .then((r) => r.data),

  topicStats: (topicId: string, days = 30) =>
    api
      .get<{
        topic_id: string
        days: number
        platforms: { platform: string; post_count: number; source_count: number; latest_post: string | null }[]
        volume_timeline: { date: string; count: number }[]
        engagement: { total_likes: number; total_comments: number; total_shares: number; total_views: number; posts_with_engagement: number }
      }>(`/api/v1/topics/${topicId}/stats`, { params: { days } })
      .then((r) => r.data),

  topAuthors: (topicId: string, days = 30, limit = 20) =>
    api
      .get<{ author_handle: string; author_id: string; platform: string; post_count: number; total_likes: number; total_views: number; total_shares: number; avg_sentiment: number }[]>(
        `/api/v1/topics/${topicId}/top-authors`,
        { params: { days, limit } },
      )
      .then((r) => r.data),

  networkGraph: (topicId: string, minWeight = 1, limit = 200) =>
    api
      .get<{
        topic_id: string
        nodes: { id: string; platform: string; post_count: number }[]
        edges: { source: string; target: string; edge_type: string; weight: number }[]
        node_count: number
        edge_count: number
      }>(`/api/v1/topics/${topicId}/network-graph`, {
        params: { min_weight: minWeight, limit },
      })
      .then((r) => r.data),
}
