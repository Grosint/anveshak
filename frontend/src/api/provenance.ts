import api from './client'

// ── Identifier Provenance ──────────────────────────────────────────────

export interface IdentifierContentItem {
  id: string
  title: string | null
  snippet: string
  captured_at: string
  platform: string | null
}

export interface IdentifierSource {
  id: string
  name: string
  platform: string
  credibility_score: number
}

export interface IdentifierCluster {
  id: string
  label: string | null
  isc: number
  item_count: number
}

export interface IdentifierSignal {
  id: string
  status: string
  fired_at: string
}

export interface CrossTopicAppearance {
  topic_name: string
  mention_count: number
}

export interface IdentifierProvenance {
  identifier_value: string
  topic_id: string
  content_items: IdentifierContentItem[]
  sources: IdentifierSource[]
  clusters: IdentifierCluster[]
  signals: IdentifierSignal[]
  cross_topic_appearances: CrossTopicAppearance[]
}

// ── Content Provenance ─────────────────────────────────────────────────

export interface ContentProvenance {
  id: string
  url: string | null
  clean_text: string
  translated_text: string | null
  language: string
  captured_at: string
  content_hash: string
  credibility_score_at_capture: number
  topic_id: string
  narrative_cluster_id: string | null
  source: {
    id: string | null
    name: string | null
    platform: string | null
    credibility_score: number | null
  }
  cluster: {
    label: string | null
    isc: number | null
  } | null
  identifiers: Array<{
    entity_type: string
    entity_text: string
    confidence: number
  }>
  vision_results: Array<{
    deepfake_score: number | null
    deepfake_model: string | null
    yolo_detections: Array<{ label?: string; class?: string; confidence: number }> | null
    clip_labels: Record<string, number> | null
    synthetic_probability: number | null
    processed_at: string | null
    storage_path: string | null
    asset_type: string | null
    exif_data: Record<string, unknown> | null
    phash: string | null
  }>
}

// ── Source Provenance (composed from existing endpoints) ────────────────

export interface SourceProvenance {
  id: string
  name: string
  platform: string
  credibility_score: number
  health_status: string
  recent_content: Array<{
    id: string
    title: string | null
    captured_at: string
  }>
  topic_links: string[]
  audit_log: Array<{
    id: string
    old_score: number
    new_score: number
    reason: string
    created_at: string
  }>
}

// ── Cluster Provenance ─────────────────────────────────────────────────

export interface ClusterProvenance {
  id: string
  label: string | null
  item_count: number
  isc: number
  executive_summary: string | null
  growth_24h: number
  items: Array<{
    id: string
    title: string | null
    clean_text: string
    captured_at: string
    platform: string | null
    source_name: string | null
  }>
  identifiers: Array<{
    entity_type: string
    entity_text: string
    mention_count: number
  }>
  signal: {
    id: string
    status: string
    fired_at: string
  } | null
}

// ── API Functions ──────────────────────────────────────────────────────

export const provenanceApi = {
  identifierProvenance: (identifierValue: string, topicId: string) =>
    api
      .get<IdentifierProvenance>(
        `/api/v1/identifiers/${encodeURIComponent(identifierValue)}/provenance`,
        { params: { topic_id: topicId } },
      )
      .then((r) => r.data),

  contentProvenance: (contentId: string) =>
    api
      .get<ContentProvenance>(`/api/v1/content/${contentId}/provenance`)
      .then((r) => r.data),

  // Source provenance: composed from existing endpoints
  sourceProvenance: async (sourceId: string, topicId: string): Promise<SourceProvenance> => {
    const [sourceRes, auditRes, contentRes] = await Promise.all([
      api.get(`/api/v1/sources`, { params: { offset: 0, limit: 200 } }),
      api.get(`/api/v1/sources/${sourceId}/audit-log`),
      api.get(`/api/v1/topics/${topicId}/content`, {
        params: { source_id: sourceId, limit: 5, sort_by: 'captured_at' },
      }),
    ])
    const allSources = sourceRes.data?.items ?? sourceRes.data ?? []
    const source = Array.isArray(allSources)
      ? allSources.find((s: Record<string, unknown>) => s.id === sourceId)
      : null

    return {
      id: sourceId,
      name: source?.name ?? 'Unknown',
      platform: source?.platform ?? 'web',
      credibility_score: source?.credibility_score ?? 0,
      health_status: source?.health_status ?? 'unverified',
      recent_content: (contentRes.data ?? []).slice(0, 5),
      topic_links: [],
      audit_log: (auditRes.data ?? []).slice(0, 10),
    }
  },

  // Cluster provenance: composed from existing endpoints
  clusterProvenance: async (clusterId: string, topicId: string): Promise<ClusterProvenance> => {
    const [clusterRes, contentRes] = await Promise.all([
      api.get(`/api/v1/topics/${topicId}/clusters`),
      api.get(`/api/v1/topics/${topicId}/clusters/${clusterId}/content`, {
        params: { limit: 20, sort: 'time' },
      }),
    ])
    const allClusters = clusterRes.data ?? []
    const cluster = Array.isArray(allClusters)
      ? allClusters.find((c: Record<string, unknown>) => c.id === clusterId)
      : null

    return {
      id: clusterId,
      label: cluster?.label ?? null,
      item_count: cluster?.item_count ?? 0,
      isc: cluster?.independent_source_count ?? 0,
      executive_summary: cluster?.executive_summary ?? null,
      growth_24h: 0,
      items: contentRes.data ?? [],
      identifiers: [],
      signal: null,
    }
  },
}
