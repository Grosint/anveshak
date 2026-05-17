import { useState, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { visionApi, VisionJob, VisionJobSummary } from '../api/vision'
import { DropZone } from '../components/vision/DropZone'
import { DeepfakeMeter } from '../components/vision/DeepfakeMeter'
import { YoloCanvas } from '../components/vision/YoloCanvas'
import { ExifTable } from '../components/vision/ExifTable'
import { Spinner } from '../components/ui/Spinner'
import { Badge } from '../components/ui/Badge'
import { Modal } from '../components/ui/Modal'
import { Button } from '../components/ui/Button'

type Tab = 'deepfake' | 'yolo' | 'exif' | 'reverse'

function getInitialJobId(): string | null {
  try {
    const url = new URL(window.location.href)
    return url.searchParams.get('job')
  } catch {
    return null
  }
}

export default function ImageAnalysis() {
  const [jobId, setJobId]             = useState<string | null>(getInitialJobId)
  const [previewUrl, setPreviewUrl]   = useState<string | null>(null)
  const [uploading, setUploading]     = useState(false)
  const [errorDialog, setErrorDialog] = useState<{ title: string; message: string } | null>(null)
  const [activeTab, setActiveTab]     = useState<Tab>('deepfake')
  const [reverseHash, setReverseHash] = useState('')
  const fileRef = useRef<File | null>(null)

  // Poll job until complete or errored
  const { data: job } = useQuery<VisionJob>({
    queryKey: ['vision-job', jobId],
    queryFn: () => visionApi.pollJob(jobId!),
    enabled: !!jobId,
    retry: false,  // don't retry on 404 — job simply doesn't exist
    refetchInterval: (query) => {
      if (query.state.error) return false          // stop on any HTTP error (404, 503…)
      const status = query.state.data?.status
      if (!status || status === 'queued' || status === 'in_progress') return 2000
      return false
    },
  })

  // Recent jobs history
  const { data: recentJobs = [] } = useQuery<VisionJobSummary[]>({
    queryKey: ['vision-jobs-recent'],
    queryFn: () => visionApi.listRecentJobs(10),
    staleTime: 30_000,
  })

  // Reverse search
  const { data: reverseResults = [], isFetching: isReversing } = useQuery({
    queryKey: ['reverse-search', reverseHash],
    queryFn: () => visionApi.reverseSearch(reverseHash),
    enabled: reverseHash.length === 16,
    staleTime: 60_000,
  })

  async function handleFile(file: File) {
    setErrorDialog(null)
    setJobId(null)
    fileRef.current = file

    // Preview
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)

    setUploading(true)
    try {
      const res = await visionApi.analyse(file)
      setJobId(res.job_id)
      setActiveTab('deepfake')
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number; data?: { detail?: string } } })?.response?.status
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail

      let message: string
      if (status === 413) {
        message = 'The file is too large. Maximum upload size is 100 MB.'
      } else if (status === 503) {
        message = 'The vision service is unavailable. Ensure the vision container is running and healthy.'
      } else if (status === 400) {
        message = detail ?? 'Invalid upload — check that the file is a supported image or video format.'
      } else if (!status) {
        message = 'Network error — check your connection and that the API is reachable.'
      } else {
        message = detail ?? `Upload failed with status ${status}.`
      }
      setErrorDialog({ title: 'Upload failed', message })
    } finally {
      setUploading(false)
    }
  }

  const result = job?.result
  const isProcessing = job?.status === 'queued' || job?.status === 'in_progress'
  const isDone = job?.status === 'complete'
  const isFailed = job?.status === 'failed'

  const TABS: { key: Tab; label: string }[] = [
    { key: 'deepfake', label: 'Deepfake' },
    { key: 'yolo',     label: `Objects${result?.yolo_detections?.length ? ` (${result.yolo_detections.length})` : ''}` },
    { key: 'exif',     label: 'EXIF' },
    { key: 'reverse',  label: 'Reverse search' },
  ]

  return (
    <div className="h-full flex flex-col">
      <Modal
        open={errorDialog !== null}
        onClose={() => setErrorDialog(null)}
        title={errorDialog?.title ?? 'Error'}
        footer={<Button onClick={() => setErrorDialog(null)}>Close</Button>}
      >
        <p className="text-sm text-text-secondary">{errorDialog?.message}</p>
      </Modal>

      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border">
        <h1 className="text-xl font-semibold text-text-primary">Image Analysis</h1>
        <p className="text-sm text-text-muted mt-0.5">
          Upload an image or video for deepfake detection, object detection, and metadata extraction
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl space-y-6">
          {/* Drop zone */}
          <DropZone onFile={handleFile} disabled={uploading} />

          {/* Recent analyses history */}
          {!jobId && recentJobs.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-text-secondary mb-3">Recent Analyses</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {recentJobs.map((j) => {
                  const score = j.deepfake_score
                  const level = score == null ? 'unknown' : score > 0.7 ? 'high' : score > 0.4 ? 'medium' : 'low'
                  const colors = {
                    high: 'border-red-500/40 bg-red-500/10 hover:bg-red-500/20',
                    medium: 'border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20',
                    low: 'border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20',
                    unknown: 'border-white/20 bg-white/5 hover:bg-white/10',
                  }
                  const scoreColors = { high: 'text-red-400', medium: 'text-amber-400', low: 'text-emerald-400', unknown: 'text-text-muted' }
                  return (
                    <button
                      key={j.job_id}
                      onClick={() => setJobId(j.job_id)}
                      className={`text-left rounded-lg border p-3 transition-colors cursor-pointer ${colors[level]}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className={`text-lg font-bold ${scoreColors[level]}`}>
                          {score != null ? `${(score * 100).toFixed(0)}%` : '—'}
                        </span>
                        <span className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
                          level === 'high' ? 'bg-red-500/20 text-red-400 border-red-500/30'
                            : level === 'medium' ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                            : level === 'low' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                            : 'bg-white/10 text-text-muted border-white/20'
                        }`}>
                          {level === 'high' ? 'HIGH RISK' : level === 'medium' ? 'MEDIUM' : level === 'low' ? 'AUTHENTIC' : 'N/A'}
                        </span>
                      </div>
                      <div className="text-[11px] text-text-muted space-y-0.5">
                        <div className="font-mono truncate">{j.job_id}</div>
                        {j.yolo_count > 0 && <div>{j.yolo_count} object{j.yolo_count > 1 ? 's' : ''} detected</div>}
                        {j.clip_top && <div className="truncate">CLIP: {j.clip_top}</div>}
                        {j.created_at && <div>{new Date(j.created_at).toLocaleString()}</div>}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Upload / processing status */}
          {uploading && (
            <div className="flex items-center gap-3 text-sm text-text-secondary">
              <Spinner size="sm" />
              <span>Uploading and dispatching analysis job…</span>
            </div>
          )}

          {jobId && !uploading && (
            <div className="flex items-center gap-2 text-xs text-text-muted">
              <span className="font-mono">job:{jobId.slice(0, 12)}…</span>
              {isProcessing && <Badge variant="warning">Processing</Badge>}
              {isDone      && <Badge variant="success">Complete</Badge>}
              {isFailed    && <Badge variant="danger">Failed</Badge>}
              {isProcessing && <Spinner size="sm" />}
            </div>
          )}

          {/* Image preview + results */}
          {(previewUrl || jobId) && (
            <div className="space-y-4">
              {/* Tabs */}
              <div className="flex border-b border-anveshak-border" role="tablist">
                {TABS.map((t) => (
                  <button
                    key={t.key}
                    role="tab"
                    aria-selected={activeTab === t.key}
                    onClick={() => setActiveTab(t.key)}
                    className={`px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none ${
                      activeTab === t.key
                        ? 'text-anveshak-accent border-b-2 border-anveshak-accent'
                        : 'text-text-muted hover:text-text-primary'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <div role="tabpanel">
                {activeTab === 'deepfake' && (
                  <div className="space-y-4">
                    {isProcessing ? (
                      <div className="flex justify-center py-8"><Spinner label="Analysing…" /></div>
                    ) : result ? (
                      <DeepfakeMeter score={result.deepfake_score} modelName={result.deepfake_model} />
                    ) : (
                      <p className="text-sm text-text-muted text-center py-8">
                        Upload an image to see deepfake analysis.
                      </p>
                    )}
                    {/* Image preview */}
                    {previewUrl && (
                      <div className="flex justify-center">
                        <img
                          src={previewUrl}
                          alt="Uploaded image preview"
                          className="max-w-full max-h-64 rounded border border-anveshak-border object-contain"
                          loading="lazy"
                          decoding="async"
                        />
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'yolo' && (
                  <div className="space-y-3">
                    {isProcessing ? (
                      <div className="flex justify-center py-8"><Spinner label="Detecting objects…" /></div>
                    ) : result?.yolo_detections ? (
                      <>
                        {previewUrl && (
                          <YoloCanvas
                            imgSrc={previewUrl}
                            detections={result.yolo_detections}
                            modelWidth={640}
                            modelHeight={640}
                          />
                        )}
                        <div className="space-y-1">
                          {result.yolo_detections.map((det, i) => (
                            <div key={i} className="flex items-center justify-between text-xs py-1 border-b border-anveshak-border/50">
                              <span className="text-text-primary font-medium">{det.label}</span>
                              <span className="text-text-muted">{Math.round(det.confidence * 100)}% confidence</span>
                            </div>
                          ))}
                        </div>
                      </>
                    ) : (
                      <p className="text-sm text-text-muted text-center py-8">
                        No object detections yet.
                      </p>
                    )}
                  </div>
                )}

                {activeTab === 'exif' && (
                  <div>
                    {isProcessing ? (
                      <div className="flex justify-center py-8"><Spinner label="Extracting EXIF…" /></div>
                    ) : result?.exif_data ? (
                      <ExifTable exif={result.exif_data as Record<string, unknown>} />
                    ) : (
                      <p className="text-sm text-text-muted text-center py-8">No EXIF data extracted yet.</p>
                    )}
                  </div>
                )}

                {activeTab === 'reverse' && (
                  <div className="space-y-4">
                    <div>
                      <label htmlFor="phash-input" className="block text-xs font-medium text-text-secondary mb-1.5">
                        pHash (16 hex chars)
                      </label>
                      <div className="flex gap-2">
                        <input
                          id="phash-input"
                          type="text"
                          maxLength={16}
                          placeholder={result?.phash ?? 'e.g. a1b2c3d4e5f60718'}
                          value={reverseHash}
                          onChange={(e) => setReverseHash(e.target.value.toLowerCase())}
                          className="flex-1 bg-anveshak-card border border-anveshak-border rounded px-3 py-2 text-sm font-mono text-text-primary focus:outline-none focus:border-anveshak-accent"
                        />
                        {result?.phash && (
                          <button
                            onClick={() => setReverseHash(result.phash!.replace('0x', ''))}
                            className="px-3 py-2 text-xs bg-anveshak-muted rounded border border-anveshak-border hover:border-anveshak-accent text-text-secondary"
                          >
                            Use current
                          </button>
                        )}
                      </div>
                      <p className="text-[10px] text-text-muted mt-1">
                        Finds near-duplicate images in the corpus using Hamming distance
                      </p>
                    </div>

                    {isReversing && <div className="flex justify-center py-4"><Spinner size="sm" label="Searching…" /></div>}

                    {reverseResults.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs text-text-muted">{reverseResults.length} near-duplicate(s) found</p>
                        {reverseResults.map((r) => (
                          <div key={r.media_asset_id} className="bg-anveshak-card border border-anveshak-border rounded p-3 text-xs space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="text-text-primary font-medium">{r.asset_type}</span>
                              <span className="text-text-muted">Hamming: {r.hamming_distance}</span>
                            </div>
                            <a href={r.url} target="_blank" rel="noopener noreferrer"
                              className="text-anveshak-accent hover:underline truncate block">
                              {r.url}
                            </a>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
