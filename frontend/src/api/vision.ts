import api from './client'

export interface YoloDetection {
  label: string
  confidence: number
  bbox: [number, number, number, number] // [x1, y1, x2, y2] in model pixel space
}

export interface VisionResult {
  vision_result_id: string
  media_asset_id: string
  yolo_detections: YoloDetection[] | null
  clip_labels: Record<string, number> | null
  deepfake_score: number // always float 0.0–1.0
  deepfake_model: string | null
  synthetic_probability: number | null
  processed_at: string
  asset_type: string
  exif_data: Record<string, unknown> | null
  phash: string | null
  content_hash: string
}

export interface VisionJob {
  job_id: string
  media_asset_id?: string
  asset_type?: string
  status: 'queued' | 'in_progress' | 'complete' | 'failed' | 'unknown'
  enqueue_time: string | null
  start_time: string | null
  finish_time: string | null
  result: VisionResult | null
}

export interface ReverseSearchResult {
  media_asset_id: string
  content_item_id: string
  asset_type: string
  content_hash: string
  url: string
  topic_id: string
  hamming_distance: number
}

export interface VisionJobSummary {
  job_id: string
  deepfake_score: number | null
  yolo_count: number
  clip_top: string | null
  status: string
  created_at: string | null
}

export const visionApi = {
  analyse: (file: File, contentItemId?: string, topicId?: string) => {
    const form = new FormData()
    form.append('file', file)
    const params: Record<string, string> = {}
    if (contentItemId) params.content_item_id = contentItemId
    if (topicId) params.topic_id = topicId
    return api
      .post<{ job_id: string; media_asset_id: string; asset_type: string; status: string }>(
        '/api/v1/vision/analyse',
        form,
        {
          params: Object.keys(params).length > 0 ? params : undefined,
          headers: { 'Content-Type': 'multipart/form-data' },
        },
      )
      .then((r) => r.data)
  },

  pollJob: (jobId: string) =>
    api.get<VisionJob>(`/api/v1/vision/jobs/${jobId}`).then((r) => r.data),

  reverseSearch: (phash: string, threshold?: number) =>
    api
      .get<ReverseSearchResult[]>('/api/v1/vision/reverse-search', {
        params: { phash, ...(threshold !== undefined ? { threshold } : {}) },
      })
      .then((r) => r.data),

  listRecentJobs: (limit = 10) =>
    api.get<VisionJobSummary[]>('/api/v1/vision/jobs/recent', { params: { limit } }).then((r) => r.data),

  analyseYoutubeVideo: (videoUrl: string, contentItemId?: string) =>
    api
      .post<{ job_id: string; status: string }>('/api/v1/vision/analyse-youtube', {
        video_url: videoUrl,
        content_item_id: contentItemId,
      })
      .then((r) => r.data),
}
