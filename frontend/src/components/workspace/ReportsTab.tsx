import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import { reportsApi, Report, ReportType, CreateReportPayload } from '../../api/reports'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'
import { formatDistanceToNow } from 'date-fns'

const REPORT_TYPES: { value: ReportType; label: string }[] = [
  { value: 'intelligence_brief', label: 'Intelligence Brief' },
  { value: 'research_summary', label: 'Research Summary' },
  { value: 'weekly_digest', label: 'Weekly Digest' },
]

interface ReportsTabProps {
  topicId: string
}

export default function ReportsTab({ topicId }: ReportsTabProps) {
  const qc = useQueryClient()
  const [reportType, setReportType] = useState<ReportType>('intelligence_brief')
  const [windowHours, setWindowHours] = useState(72)
  const [currentReportId, setCurrentReportId] = useState<string | null>(null)

  // Report history
  const { data: history = [], isLoading: loadingHistory } = useQuery({
    queryKey: ['reports-history', topicId],
    queryFn: () => reportsApi.listForTopic(topicId),
    enabled: !!topicId,
  })

  // Poll current report
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

  const generate = useMutation({
    mutationFn: (payload: CreateReportPayload) => reportsApi.create(payload),
    onSuccess: (data) => {
      setCurrentReportId(data.report_id)
      qc.invalidateQueries({ queryKey: ['reports-history', topicId] })
    },
  })

  const handleGenerate = () => {
    generate.mutate({
      topic_id: topicId,
      report_type: reportType,
      time_window_hours: windowHours,
    })
  }

  // Auto-load latest report from history if none selected
  useEffect(() => {
    if (!currentReportId && history.length > 0) {
      const latest = history.find((h) => h.generated_at)
      if (latest) setCurrentReportId(latest.id)
    }
  }, [history, currentReportId])

  return (
    <div className="h-full flex flex-col">
      {/* Generate form */}
      <div className="px-6 py-3 border-b border-anveshak-border flex items-center gap-3 flex-wrap">
        <select
          value={reportType}
          onChange={(e) => setReportType(e.target.value as ReportType)}
          className="bg-anveshak-card border border-anveshak-border rounded px-2 py-1.5 text-xs text-text-primary"
        >
          {REPORT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>

        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-text-muted">Window:</span>
          <input
            type="number"
            value={windowHours}
            onChange={(e) => setWindowHours(parseInt(e.target.value) || 72)}
            min={1}
            max={720}
            className="w-16 bg-anveshak-card border border-anveshak-border rounded px-2 py-1.5 text-xs text-text-primary"
          />
          <span className="text-[11px] text-text-muted">hours</span>
        </div>

        <Button
          size="sm"
          onClick={handleGenerate}
          loading={generate.isPending || report?.generation_status === 'queued'}
          disabled={generate.isPending}
        >
          Generate Report
        </Button>

        {report?.generation_status === 'queued' && (
          <span className="text-[11px] text-amber-400 animate-pulse">Generating...</span>
        )}
      </div>

      {/* Report content or history */}
      <div className="flex-1 overflow-y-auto">
        {report?.generation_status === 'complete' && report.content_md ? (
          <div className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <Badge variant="success">Complete</Badge>
              {report.confidence_score != null && (
                <Badge variant={report.confidence_score >= 0.7 ? 'success' : 'warning'}>
                  {Math.round(report.confidence_score * 100)}% confidence
                </Badge>
              )}
              {report.content_item_count != null && (
                <span className="text-[11px] text-text-muted">{report.content_item_count} items analyzed</span>
              )}
              <Button
                size="sm"
                variant="secondary"
                onClick={() => reportsApi.downloadPdf(report.id)}
              >
                Download PDF
              </Button>
            </div>

            <div className="prose-anveshak text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
                {report.content_md}
              </ReactMarkdown>
            </div>
          </div>
        ) : report?.generation_status === 'failed' ? (
          <div className="p-6">
            <Badge variant="danger">Failed</Badge>
            <p className="text-sm text-text-muted mt-2">{report.generation_error || 'Unknown error'}</p>
          </div>
        ) : report?.generation_status === 'queued' ? (
          <div className="flex items-center justify-center py-20">
            <Spinner label="Generating report..." />
          </div>
        ) : (
          /* History list */
          <div className="p-6">
            <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-3">
              Report History ({history.length})
            </h3>
            {loadingHistory ? (
              <Spinner label="Loading..." />
            ) : history.length === 0 ? (
              <p className="text-sm text-text-muted">No reports yet. Generate one above.</p>
            ) : (
              <div className="space-y-2">
                {history.map((h) => (
                  <button
                    key={h.id}
                    onClick={() => setCurrentReportId(h.id)}
                    className={`w-full text-left p-3 rounded-lg border transition-all ${
                      currentReportId === h.id
                        ? 'border-anveshak-accent/40 bg-anveshak-accent/5'
                        : 'border-anveshak-border hover:border-anveshak-border/80'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="ghost" className="text-[9px]">{h.report_type.replace(/_/g, ' ')}</Badge>
                        {h.confidence_score != null && (
                          <span className="text-[10px] text-text-muted">{Math.round(h.confidence_score * 100)}%</span>
                        )}
                      </div>
                      <span className="text-[10px] text-text-muted">
                        {h.generated_at
                          ? formatDistanceToNow(new Date(h.generated_at), { addSuffix: true })
                          : 'pending'}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
