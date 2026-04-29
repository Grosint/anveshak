import { lazy, Suspense, useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'
import { topicsApi } from '../api/topics'
import { reportsApi, Report, ReportType, ReportSummary, CreateReportPayload } from '../api/reports'
import { SourceWarningsBanner } from '../components/reports/SourceWarningsBanner'
import { ReportProgress } from '../components/reports/ReportProgress'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { format, formatDistanceToNow } from 'date-fns'

// Lazy-load MapLibre so it only ships when the GIS tab opens (~700KB saved from initial bundle)
const GeoMap = lazy(() => import('../components/map/GeoMap'))

type Tab = 'report' | 'gis' | 'history'

const REPORT_TYPES: { value: ReportType; label: string; description: string }[] = [
  { value: 'intelligence_brief',  label: 'Intelligence Brief',  description: '1–3 page executive summary' },
  { value: 'research_summary',    label: 'Research Summary',    description: 'Deep-dive, all entities, timeline' },
  { value: 'weekly_digest',       label: 'Weekly Digest',       description: 'Aggregated 7-day summary' },
]

function ConfidenceBadge({ score }: { score: number | null }) {
  if (score === null) return null
  const pct = Math.round(score * 100)
  const variant = pct >= 70 ? 'success' : pct >= 40 ? 'warning' : 'danger'
  return <Badge variant={variant}>{pct}% confidence</Badge>
}

export default function ReportBuilder() {
  const [selectedTopicId, setSelectedTopicId] = useState('')
  const [reportType, setReportType]           = useState<ReportType>('intelligence_brief')
  const [windowHours, setWindowHours]         = useState(72)
  const [credMin, setCredMin]                 = useState(30)
  const [currentReportId, setCurrentReportId] = useState<string | null>(null)
  const [activeTab, setActiveTab]             = useState<Tab>('report')
  const [generationStartedAt, setGenerationStartedAt] = useState<string | null>(null)
  const [historyTypeFilter, setHistoryTypeFilter]     = useState<ReportType | 'all'>('all')
  const [historyFrom, setHistoryFrom]                 = useState('')
  const [historyTo, setHistoryTo]                     = useState('')
  const qc = useQueryClient()

  // Topics for selector
  const { data: topics = [] } = useQuery({ queryKey: ['topics'], queryFn: topicsApi.list })

  // Poll current report until complete
  const { data: report } = useQuery<Report>({
    queryKey: ['report', currentReportId],
    queryFn: () => reportsApi.get(currentReportId!),
    enabled: !!currentReportId,
    refetchInterval: (query) => {
      const status = query.state.data?.generation_status
      if (!status || status === 'queued') return 5000
      return false
    },
  })

  // Report history for selected topic
  const { data: history = [] } = useQuery({
    queryKey: ['reports-history', selectedTopicId],
    queryFn: () => reportsApi.listForTopic(selectedTopicId),
    enabled: !!selectedTopicId && activeTab === 'history',
  })

  // GeoJSON (only fetched when GIS tab opens and report is done)
  const { data: geojson } = useQuery({
    queryKey: ['report-geojson', currentReportId],
    queryFn: () => reportsApi.getGeojson(currentReportId!),
    enabled: !!currentReportId && report?.generation_status === 'complete' && activeTab === 'gis',
    staleTime: Infinity,
  })

  const generate = useMutation({
    mutationFn: (payload: CreateReportPayload) => reportsApi.create(payload),
    onSuccess: (data) => {
      setCurrentReportId(data.report_id)
      setGenerationStartedAt(new Date().toISOString())
      setActiveTab('report')
      qc.invalidateQueries({ queryKey: ['reports-history', selectedTopicId] })
    },
  })

  async function handleGenerate() {
    if (!selectedTopicId) return
    await generate.mutateAsync({
      topic_id: selectedTopicId,
      report_type: reportType,
      time_window_hours: windowHours,
      credibility_min: credMin,
    })
  }

  const isGenerating = report?.generation_status === 'queued' || generate.isPending
  const isDone       = report?.generation_status === 'complete'

  const filteredHistory = useMemo(() => {
    return history.filter((r: ReportSummary) => {
      if (historyTypeFilter !== 'all' && r.report_type !== historyTypeFilter) return false
      if (historyFrom && new Date(r.created_at) < new Date(historyFrom)) return false
      if (historyTo && new Date(r.created_at) > new Date(historyTo + 'T23:59:59')) return false
      return true
    })
  }, [history, historyTypeFilter, historyFrom, historyTo])

  const TABS: { key: Tab; label: string }[] = [
    { key: 'report',  label: 'Report' },
    { key: 'gis',     label: 'GIS Map' },
    { key: 'history', label: 'History' },
  ]

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border">
        <h1 className="text-xl font-semibold text-text-primary">Report Builder</h1>
        <p className="text-sm text-text-muted mt-0.5">RAG-grounded intelligence reports via Ollama LLM</p>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl space-y-6">
          {/* ── Generation form ─────────────────────────────────────────────── */}
          <section className="bg-anveshak-card border border-anveshak-border rounded-lg p-5 space-y-4" aria-labelledby="form-heading">
            <h2 id="form-heading" className="text-sm font-semibold text-text-primary">Generate report</h2>

            {/* Topic selector */}
            <div>
              <label htmlFor="topic-select" className="block text-xs font-medium text-text-secondary mb-1.5">Topic</label>
              <select
                id="topic-select"
                value={selectedTopicId}
                onChange={(e) => setSelectedTopicId(e.target.value)}
                className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-anveshak-accent"
              >
                <option value="">Select a topic…</option>
                {topics.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>

            {/* Report type */}
            <div>
              <p className="text-xs font-medium text-text-secondary mb-2">Report type</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {REPORT_TYPES.map((rt) => (
                  <button
                    key={rt.value}
                    type="button"
                    onClick={() => setReportType(rt.value)}
                    className={`text-left p-3 rounded border transition-colors ${
                      reportType === rt.value
                        ? 'border-anveshak-accent bg-anveshak-accent/10'
                        : 'border-anveshak-border hover:border-anveshak-accent/40'
                    }`}
                    aria-pressed={reportType === rt.value}
                  >
                    <p className="text-xs font-semibold text-text-primary">{rt.label}</p>
                    <p className="text-[10px] text-text-muted mt-0.5">{rt.description}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Time window + credibility */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="window" className="block text-xs font-medium text-text-secondary mb-1.5">Time window (hours)</label>
                <input
                  id="window"
                  type="number"
                  min={1}
                  max={720}
                  value={windowHours}
                  onChange={(e) => setWindowHours(Number(e.target.value))}
                  className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-anveshak-accent"
                />
              </div>
              <div>
                <label htmlFor="cred-report" className="block text-xs font-medium text-text-secondary mb-1.5">Min. credibility</label>
                <input
                  id="cred-report"
                  type="number"
                  min={0}
                  max={100}
                  value={credMin}
                  onChange={(e) => setCredMin(Number(e.target.value))}
                  className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-anveshak-accent"
                />
              </div>
            </div>

            <Button
              onClick={handleGenerate}
              loading={generate.isPending}
              disabled={!selectedTopicId || isGenerating}
            >
              Generate report
            </Button>
          </section>

          {/* ── Tabs ──────────────────────────────────────────────────────────── */}
          {(currentReportId || selectedTopicId) && (
            <section aria-labelledby="report-output-heading">
              <h2 id="report-output-heading" className="sr-only">Report output</h2>

              {/* Progress tracker — only when a report is selected */}
              {currentReportId && (
              <div className="mb-4">
                <ReportProgress
                  status={report?.generation_status ?? 'queued'}
                  error={report?.generation_error}
                  startedAt={generationStartedAt ?? report?.created_at}
                />
                {isDone && report && (
                  <div className="flex items-center gap-3 mt-3 flex-wrap">
                    <ConfidenceBadge score={report.confidence_score} />
                    {report.content_item_count && (
                      <span className="text-xs text-text-muted">{report.content_item_count} sources used</span>
                    )}
                    <span className="text-xs text-text-muted">
                      {report.generated_at && format(new Date(report.generated_at), 'dd MMM yyyy HH:mm')}
                    </span>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => reportsApi.downloadPdf(currentReportId)}
                    >
                      Download PDF
                    </Button>
                  </div>
                )}
              </div>
              )}

              {/* Tabs */}
              <div className="flex border-b border-anveshak-border mb-4" role="tablist">
                {TABS.map((t) => (
                  <button
                    key={t.key}
                    role="tab"
                    aria-selected={activeTab === t.key}
                    onClick={() => setActiveTab(t.key)}
                    className={`px-4 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none ${
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
                {/* Report tab */}
                {activeTab === 'report' && (
                  <div className="space-y-4">
                    {!currentReportId ? (
                      <EmptyState icon="📄" title="Generate a report or select one from History" />
                    ) : (
                      <>
                        {report?.source_warnings && (
                          <SourceWarningsBanner warnings={report.source_warnings} />
                        )}
                        {report?.content_md && (
                          <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-6 prose-anveshak">
                            <ReactMarkdown rehypePlugins={[rehypeSanitize]}>
                              {report.content_md}
                            </ReactMarkdown>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}

                {/* GIS tab */}
                {activeTab === 'gis' && (
                  <div>
                    {!isDone ? (
                      <p className="text-sm text-text-muted">{!currentReportId ? 'Select a report first.' : 'Report must be complete to view GIS output.'}</p>
                    ) : (
                      <Suspense fallback={<Spinner label="Loading map…" />}>
                        <GeoMap
                          geojson={geojson ?? { type: 'FeatureCollection', features: [] }}
                        />
                      </Suspense>
                    )}
                  </div>
                )}

                {/* History tab */}
                {activeTab === 'history' && (
                  <div className="space-y-3">
                    {/* Filters */}
                    <div className="flex items-end gap-3 flex-wrap">
                      <div>
                        <label htmlFor="hist-type" className="block text-[11px] font-medium text-text-muted mb-1">Type</label>
                        <select
                          id="hist-type"
                          value={historyTypeFilter}
                          onChange={(e) => setHistoryTypeFilter(e.target.value as ReportType | 'all')}
                          className="bg-anveshak-bg border border-anveshak-border rounded px-2.5 py-1.5 text-xs text-text-primary focus:outline-none focus:border-anveshak-accent"
                        >
                          <option value="all">All types</option>
                          {REPORT_TYPES.map((rt) => (
                            <option key={rt.value} value={rt.value}>{rt.label}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label htmlFor="hist-from" className="block text-[11px] font-medium text-text-muted mb-1">From</label>
                        <input
                          id="hist-from"
                          type="date"
                          value={historyFrom}
                          onChange={(e) => setHistoryFrom(e.target.value)}
                          className="bg-anveshak-bg border border-anveshak-border rounded px-2.5 py-1.5 text-xs text-text-primary focus:outline-none focus:border-anveshak-accent"
                        />
                      </div>
                      <div>
                        <label htmlFor="hist-to" className="block text-[11px] font-medium text-text-muted mb-1">To</label>
                        <input
                          id="hist-to"
                          type="date"
                          value={historyTo}
                          onChange={(e) => setHistoryTo(e.target.value)}
                          className="bg-anveshak-bg border border-anveshak-border rounded px-2.5 py-1.5 text-xs text-text-primary focus:outline-none focus:border-anveshak-accent"
                        />
                      </div>
                      {(historyTypeFilter !== 'all' || historyFrom || historyTo) && (
                        <button
                          type="button"
                          onClick={() => { setHistoryTypeFilter('all'); setHistoryFrom(''); setHistoryTo('') }}
                          className="text-xs text-text-muted hover:text-text-primary transition-colors pb-1"
                        >
                          Clear filters
                        </button>
                      )}
                    </div>

                    {/* Results */}
                    {filteredHistory.length === 0 ? (
                      <EmptyState
                        icon="📋"
                        title={history.length === 0 ? 'No reports yet for this topic' : 'No reports match filters'}
                      />
                    ) : (
                      <div className="space-y-2">
                        <p className="text-[11px] text-text-muted">{filteredHistory.length} report{filteredHistory.length !== 1 ? 's' : ''}</p>
                        {filteredHistory.map((r) => (
                          <div
                            key={r.id}
                            className={`flex items-center justify-between bg-anveshak-card border rounded-lg px-4 py-3 text-sm cursor-pointer hover:border-anveshak-accent/40 transition-colors ${
                              r.id === currentReportId ? 'border-anveshak-accent' : 'border-anveshak-border'
                            }`}
                            onClick={() => { setCurrentReportId(r.id); setGenerationStartedAt(null); setActiveTab('report') }}
                            role="button"
                            tabIndex={0}
                            onKeyDown={(e) => e.key === 'Enter' && setCurrentReportId(r.id)}
                            aria-label={`Load report from ${r.created_at}`}
                          >
                            <div>
                              <span className="font-medium text-text-primary capitalize">
                                {r.report_type.replace(/_/g, ' ')}
                              </span>
                              <span className="ml-2 text-xs text-text-muted">
                                {format(new Date(r.created_at), 'dd MMM yyyy HH:mm')}
                              </span>
                              <span className="ml-1 text-xs text-text-muted">
                                ({formatDistanceToNow(new Date(r.created_at), { addSuffix: true })})
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              {r.confidence_score !== null && <ConfidenceBadge score={r.confidence_score} />}
                              <Badge variant={r.generated_at ? 'success' : 'warning'}>
                                {r.generated_at ? 'Done' : 'Pending'}
                              </Badge>
                              {r.generated_at && (
                                <button
                                  type="button"
                                  onClick={(e) => { e.stopPropagation(); reportsApi.downloadPdf(r.id) }}
                                  className="p-1 rounded hover:bg-anveshak-accent/10 text-text-muted hover:text-anveshak-accent transition-colors"
                                  aria-label="Download PDF"
                                  title="Download PDF"
                                >
                                  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
                                    <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
                                    <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
                                  </svg>
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
