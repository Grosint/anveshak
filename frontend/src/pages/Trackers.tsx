import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { trackersApi, type Tracker } from '../api/trackers'
import { Spinner } from '../components/ui/Spinner'
import { Pagination } from '../components/ui/Pagination'
import { CreateTrackerModal } from '../components/trackers/CreateTrackerModal'

type StatusFilter = 'all' | 'watching' | 'active' | 'concluded'

const STATUS_FILTERS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'watching', label: 'Watching' },
  { key: 'active', label: 'Active' },
  { key: 'concluded', label: 'Concluded' },
]

function statusDotClass(status: Tracker['status']): string {
  switch (status) {
    case 'watching':  return 'bg-blue-400'
    case 'active':    return 'bg-green-400'
    case 'concluded': return 'bg-gray-500'
  }
}

function priorityBadgeClass(priority: Tracker['priority']): string {
  switch (priority) {
    case 'critical': return 'bg-red-500/20 text-red-400'
    case 'high':     return 'bg-orange-500/20 text-orange-400'
    case 'medium':   return 'bg-yellow-500/20 text-yellow-400'
    case 'low':      return 'bg-gray-500/20 text-gray-400'
  }
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

const PAGE_SIZE = 50

export default function Trackers() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [createOpen, setCreateOpen] = useState(false)
  const [page, setPage] = useState(0)

  const statusParam = statusFilter === 'all' ? undefined : statusFilter

  const { data, isLoading, isError } = useQuery({
    queryKey: ['trackers', statusParam, page],
    queryFn: () => trackersApi.list({ status: statusParam, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    refetchInterval: 30_000,
  })

  const trackers = data?.items ?? []
  const total = data?.total ?? 0

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Trackers</h1>
          <p className="text-sm text-text-muted mt-0.5">
            Case tracking for narrative investigations
          </p>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="bg-anveshak-accent hover:bg-anveshak-accent/80 text-white rounded px-3 py-1.5 text-sm font-medium transition-colors"
        >
          + New Tracker
        </button>
      </div>

      {/* Status filter chips */}
      <div className="flex gap-2 px-6 py-3 border-b border-anveshak-border">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => { setStatusFilter(f.key); setPage(0) }}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              statusFilter === f.key
                ? 'bg-anveshak-accent text-white'
                : 'bg-anveshak-muted text-text-secondary hover:bg-anveshak-card hover:text-text-primary'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isError ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <p className="text-red-400 text-sm">Failed to load trackers.</p>
          </div>
        ) : isLoading ? (
          <div className="flex justify-center py-20">
            <Spinner label="Loading trackers…" />
          </div>
        ) : trackers.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <p className="text-text-muted text-sm">
              No trackers yet. Open a tracker from a narrative cluster or create one manually.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-anveshak-border text-text-muted text-xs uppercase tracking-wide">
                  <th className="text-left py-2 px-3 w-6"></th>
                  <th className="text-left py-2 px-3">Case #</th>
                  <th className="text-left py-2 px-3">Title</th>
                  <th className="text-right py-2 px-3">Items</th>
                  <th className="text-right py-2 px-3">Pending</th>
                  <th className="text-left py-2 px-3">Priority</th>
                  <th className="text-left py-2 px-3">Assigned</th>
                  <th className="text-left py-2 px-3">Created</th>
                </tr>
              </thead>
              <tbody>
                {trackers.map((tracker) => (
                  <tr
                    key={tracker.id}
                    onClick={() => navigate(`/trackers/${tracker.id}`)}
                    className="border-b border-anveshak-border/50 hover:bg-anveshak-muted/50 transition-colors cursor-pointer"
                  >
                    <td className="py-3 px-3">
                      <span
                        className={`inline-block w-2.5 h-2.5 rounded-full ${statusDotClass(tracker.status)}`}
                        title={tracker.status}
                      />
                    </td>
                    <td className="py-3 px-3 font-mono text-xs text-text-primary whitespace-nowrap">
                      {tracker.case_number}
                    </td>
                    <td className="py-3 px-3 text-text-primary max-w-xs truncate">
                      {tracker.title}
                    </td>
                    <td className="py-3 px-3 text-right text-text-secondary">
                      {tracker.content_count}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {tracker.pending_count > 0 ? (
                        <span className="inline-flex items-center justify-center min-w-[1.25rem] px-1.5 py-0.5 rounded text-[10px] font-bold bg-yellow-500/20 text-yellow-400">
                          {tracker.pending_count}
                        </span>
                      ) : (
                        <span className="text-text-muted">—</span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${priorityBadgeClass(tracker.priority)}`}>
                        {tracker.priority}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-text-muted text-xs">
                      {tracker.assigned_to || '—'}
                    </td>
                    <td className="py-3 px-3 text-text-muted text-xs whitespace-nowrap">
                      {relativeTime(tracker.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
          </div>
        )}
      </div>

      <CreateTrackerModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(tracker) => {
          setCreateOpen(false)
          navigate(`/trackers/${tracker.id}`)
        }}
      />
    </div>
  )
}
