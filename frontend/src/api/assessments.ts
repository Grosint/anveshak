import api from './client'

export interface SourceEngagement {
  likes: number
  comments: number
  shares: number
  views: number
}

export interface LanguageBreakdown {
  language: string
  count: number
  pct: number
}

export interface VolumeEntry {
  date: string
  count: number
}

export interface TopEntity {
  entity_text: string
  entity_type: string
  count: number
}

export interface IdentifierOverlap {
  identifier_type: string
  identifier_value: string
  source_count: number
}

export interface ClusterParticipation {
  cluster_id: string
  label: string
  item_count: number
}

export interface SentimentDistribution {
  negative: number
  neutral: number
  positive: number
}

export interface CredibilityEntry {
  old_score: number
  new_score: number
  reason: string
  date: string
}

export interface SourceStats {
  total_posts: number
  first_post: string | null
  last_post: string | null
  avg_posts_per_day: number
  engagement: SourceEngagement
  language_breakdown: LanguageBreakdown[]
  volume_timeline: VolumeEntry[]
  top_entities: TopEntity[]
  identifier_overlap: IdentifierOverlap[]
  cluster_participation: ClusterParticipation[]
  sentiment_distribution: SentimentDistribution
  credibility_trajectory: CredibilityEntry[]
}

export type AssessmentStatus = 'stats_only' | 'queued' | 'complete' | 'failed'

export interface SourceAssessment {
  id: string
  topic_id: string
  source_id: string
  time_window_start: string
  time_window_end: string
  content_item_count: number
  stats: SourceStats
  source_snapshot: Record<string, { name: string; credibility_score: number }> | null
  platform_metadata: Record<string, unknown> | null
  brief_md: string | null
  confidence_score: number | null
  generated_at: string
  generation_status: AssessmentStatus
  created_at: string
}

export interface AssessmentSummary {
  id: string
  topic_id: string
  source_id: string
  content_item_count: number
  generated_at: string | null
  has_brief: boolean
  created_at: string
}

export interface CreateAssessmentPayload {
  time_window_start?: string
  time_window_end?: string
  time_window_days?: number
}

export const assessmentsApi = {
  create: (topicId: string, sourceId: string, payload?: CreateAssessmentPayload) =>
    api
      .post<SourceAssessment>(
        `/api/v1/topics/${topicId}/sources/${sourceId}/assessment`,
        payload ?? {},
      )
      .then((r) => r.data),

  list: (topicId: string, sourceId: string) =>
    api
      .get<AssessmentSummary[]>(
        `/api/v1/topics/${topicId}/sources/${sourceId}/assessments`,
      )
      .then((r) => r.data),

  get: (topicId: string, sourceId: string, assessmentId: string) =>
    api
      .get<SourceAssessment>(
        `/api/v1/topics/${topicId}/sources/${sourceId}/assessments/${assessmentId}`,
      )
      .then((r) => r.data),

  generateBrief: (topicId: string, sourceId: string, assessmentId: string) =>
    api
      .post<{ assessment_id: string; status: string; arq_job_id: string | null }>(
        `/api/v1/topics/${topicId}/sources/${sourceId}/assessments/${assessmentId}/brief`,
      )
      .then((r) => r.data),
}
