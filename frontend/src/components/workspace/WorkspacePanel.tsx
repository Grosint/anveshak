import { useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import { reportsApi } from '../../api/reports'
import { Spinner } from '../ui/Spinner'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { SignalDetailPanel } from './SignalDetailPanel'

export type PanelItem =
  | { type: 'signal'; id: string; topicId: string }
  | { type: 'report'; id: string }
  | null

interface WorkspacePanelProps {
  item: PanelItem
  onClose: () => void
  onShowGraph?: (signalId: string) => void
}

export function WorkspacePanel({ item, onClose, onShowGraph }: WorkspacePanelProps) {
  if (!item) return null

  return (
    <aside
      className="w-[420px] shrink-0 border-l border-anveshak-border/50 bg-[#0b1222] flex flex-col overflow-hidden"
      aria-label="Detail panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-anveshak-border/50 bg-[#0f1729] shrink-0">
        <span className="text-[10px] font-bold text-text-muted uppercase tracking-widest">
          {item.type === 'signal' && 'Signal Detail'}
          {item.type === 'report' && 'Report Viewer'}
        </span>
        <button
          onClick={onClose}
          className="text-text-muted hover:text-text-primary transition-colors"
          aria-label="Close panel"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
            <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
          </svg>
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">
        {item.type === 'signal' && (
          <SignalDetailPanel signalId={item.id} topicId={item.topicId} onShowGraph={onShowGraph} />
        )}
        {item.type === 'report' && (
          <ReportPanel reportId={item.id} />
        )}
      </div>
    </aside>
  )
}

function ReportPanel({ reportId }: { reportId: string }) {
  const { data: report, isLoading } = useQuery({
    queryKey: ['report', reportId],
    queryFn: () => reportsApi.get(reportId),
  })

  if (isLoading) return <div className="p-4"><Spinner label="Loading report..." /></div>
  if (!report) return <p className="p-4 text-text-muted text-sm">Report not found</p>

  const pct = report.confidence_score != null ? Math.round(report.confidence_score * 100) : null

  return (
    <div className="p-4">
      {pct !== null && (
        <div className="flex items-center gap-2 mb-3">
          <Badge variant={pct >= 70 ? 'success' : pct >= 40 ? 'warning' : 'danger'}>
            {pct}% confidence
          </Badge>
          {report.content_item_count != null && (
            <span className="text-[11px] text-text-muted">{report.content_item_count} items</span>
          )}
          <Button size="sm" variant="secondary" onClick={() => reportsApi.downloadPdf(report.id)}>
            PDF
          </Button>
        </div>
      )}
      <div className="prose-anveshak text-sm">
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
          {report.content_md || 'Report content not yet generated.'}
        </ReactMarkdown>
      </div>
    </div>
  )
}
