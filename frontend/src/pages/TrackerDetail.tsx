import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { trackersApi, type TrackerContentItem, type TrackerNote, type TrackerAuditEntry } from '../api/trackers'
import { Spinner } from '../components/ui/Spinner'
import { ConcludeModal } from '../components/trackers/ConcludeModal'

type Tab = 'overview' | 'content' | 'pending' | 'notes' | 'signals' | 'reports' | 'audit'

const TABS: { key: Tab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'content',  label: 'Content' },
  { key: 'pending',  label: 'Pending Review' },
  { key: 'notes',    label: 'Notes' },
  { key: 'signals',  label: 'Signals' },
  { key: 'reports',  label: 'Reports' },
  { key: 'audit',    label: 'Audit Log' },
]

function priorityBadgeClass(priority: string): string {
  switch (priority) {
    case 'critical': return 'bg-red-500/20 text-red-400'
    case 'high':     return 'bg-orange-500/20 text-orange-400'
    case 'medium':   return 'bg-yellow-500/20 text-yellow-400'
    default:         return 'bg-gray-500/20 text-gray-400'
  }
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case 'watching':  return 'bg-blue-500/20 text-blue-400'
    case 'active':    return 'bg-green-500/20 text-green-400'
    case 'concluded': return 'bg-gray-500/20 text-gray-400'
    default:          return 'bg-gray-500/20 text-gray-400'
  }
}

function provenanceBadgeClass(attached_by: TrackerContentItem['attached_by']): string {
  switch (attached_by) {
    case 'seed':   return 'bg-teal-500/20 text-teal-400'
    case 'auto':   return 'bg-green-500/20 text-green-400'
    case 'manual': return 'bg-blue-500/20 text-blue-400'
  }
}

function provenanceLabel(attached_by: TrackerContentItem['attached_by']): string {
  switch (attached_by) {
    case 'seed':   return 'SEED'
    case 'auto':   return 'CONFIRMED'
    case 'manual': return 'MANUAL'
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatAuditDetail(action: string, detail: Record<string, unknown>): string {
  if (action === 'content_confirmed') return `Confirmed item`
  if (action === 'content_rejected') return `Rejected item`
  if (action === 'note_added') return 'Added a note'
  if (action === 'status_changed') return `Status → ${detail.status}`
  if (action === 'priority_changed') return `Priority → ${detail.priority}`
  if (action === 'assigned') return `Assigned to ${detail.assigned_to || 'unassigned'}`
  if (action === 'created') return `Tracker created`
  if (action === 'signal_linked') return `Linked signal`
  if (action === 'all_pending_confirmed') return 'Confirmed all pending items'
  return JSON.stringify(detail)
}

function severityBadgeClass(severity: string): string {
  switch (severity) {
    case 'critical': return 'bg-red-500/20 text-red-400'
    case 'high':     return 'bg-orange-500/20 text-orange-400'
    case 'medium':   return 'bg-yellow-500/20 text-yellow-400'
    case 'low':      return 'bg-blue-500/20 text-blue-400'
    default:         return 'bg-gray-500/20 text-gray-400'
  }
}

function reportStatusBadgeClass(status: string): string {
  switch (status) {
    case 'queued':   return 'bg-yellow-500/20 text-yellow-400'
    case 'complete': return 'bg-green-500/20 text-green-400'
    case 'failed':   return 'bg-red-500/20 text-red-400'
    default:         return 'bg-gray-500/20 text-gray-400'
  }
}

export default function TrackerDetail() {
  const { trackerId: id } = useParams<{ trackerId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [concludeOpen, setConcludeOpen] = useState(false)
  const [noteBody, setNoteBody] = useState('')
  const [statusChanging, setStatusChanging] = useState(false)

  const { data: tracker, isLoading } = useQuery({
    queryKey: ['tracker', id],
    queryFn: () => trackersApi.get(id!),
    enabled: !!id,
  })

  const { data: content = [], isLoading: contentLoading, isError: contentError } = useQuery({
    queryKey: ['tracker-content', id],
    queryFn: () => trackersApi.listContent(id!),
    enabled: !!id && activeTab === 'content',
  })

  const { data: pending = [], isLoading: pendingLoading, isError: pendingError } = useQuery({
    queryKey: ['tracker-pending', id],
    queryFn: () => trackersApi.listPending(id!),
    enabled: !!id && activeTab === 'pending',
  })

  const { data: notes = [], isLoading: notesLoading, isError: notesError } = useQuery({
    queryKey: ['tracker-notes', id],
    queryFn: () => trackersApi.listNotes(id!),
    enabled: !!id && activeTab === 'notes',
  })

  const { data: signals = [], isLoading: signalsLoading, isError: signalsError } = useQuery({
    queryKey: ['tracker-signals', id],
    queryFn: () => trackersApi.listSignals(id!),
    enabled: !!id && activeTab === 'signals',
  })

  const { data: auditLog = [], isLoading: auditLoading, isError: auditError } = useQuery({
    queryKey: ['tracker-audit', id],
    queryFn: () => trackersApi.listAuditLog(id!),
    enabled: !!id && activeTab === 'audit',
  })

  const { data: reports = [], isLoading: reportsLoading, isError: reportsError } = useQuery({
    queryKey: ['tracker-reports', id],
    queryFn: () => trackersApi.listReports(id!),
    enabled: !!id && activeTab === 'reports',
  })

  const generateReportMutation = useMutation({
    mutationFn: () => trackersApi.generateReport(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tracker-reports', id] })
    },
    onError: () => { /* handled by mutation.isError in UI */ },
  })

  const confirmMutation = useMutation({
    mutationFn: (itemId: string) => trackersApi.confirmItem(id!, itemId),
    onMutate: async (itemId) => {
      await qc.cancelQueries({ queryKey: ['tracker-pending', id] })
      const prev = qc.getQueryData<TrackerContentItem[]>(['tracker-pending', id])
      qc.setQueryData<TrackerContentItem[]>(['tracker-pending', id], (old = []) =>
        old.filter((i) => i.id !== itemId)
      )
      return { prev }
    },
    onError: (_e, _itemId, ctx) => {
      if (ctx?.prev) qc.setQueryData(['tracker-pending', id], ctx.prev)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['tracker', id] })
      qc.invalidateQueries({ queryKey: ['tracker-content', id] })
    },
  })

  const rejectMutation = useMutation({
    mutationFn: (itemId: string) => trackersApi.rejectItem(id!, itemId),
    onMutate: async (itemId) => {
      await qc.cancelQueries({ queryKey: ['tracker-pending', id] })
      const prev = qc.getQueryData<TrackerContentItem[]>(['tracker-pending', id])
      qc.setQueryData<TrackerContentItem[]>(['tracker-pending', id], (old = []) =>
        old.filter((i) => i.id !== itemId)
      )
      return { prev }
    },
    onError: (_e, _itemId, ctx) => {
      if (ctx?.prev) qc.setQueryData(['tracker-pending', id], ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['tracker', id] }),
  })

  const confirmAllMutation = useMutation({
    mutationFn: () => trackersApi.confirmAll(id!),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ['tracker-pending', id] })
      const prev = qc.getQueryData<TrackerContentItem[]>(['tracker-pending', id])
      qc.setQueryData<TrackerContentItem[]>(['tracker-pending', id], [])
      return { prev }
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(['tracker-pending', id], ctx.prev)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['tracker', id] })
      qc.invalidateQueries({ queryKey: ['tracker-content', id] })
    },
  })

  const addNoteMutation = useMutation({
    mutationFn: (body: string) => trackersApi.addNote(id!, { body }),
    onSuccess: () => {
      setNoteBody('')
      qc.invalidateQueries({ queryKey: ['tracker-notes', id] })
    },
    onError: () => { /* handled by mutation.isError in UI */ },
  })

  const updateStatusMutation = useMutation({
    mutationFn: (status: string) => trackersApi.updateStatus(id!, { status }),
    onSuccess: () => {
      setStatusChanging(false)
      qc.invalidateQueries({ queryKey: ['tracker', id] })
      qc.invalidateQueries({ queryKey: ['trackers'] })
    },
    onError: () => { setStatusChanging(false) },
  })

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner label="Loading tracker…" />
      </div>
    )
  }

  if (!tracker) {
    return (
      <div className="p-6">
        <p className="text-text-muted">Tracker not found.</p>
        <button
          onClick={() => navigate('/trackers')}
          className="mt-3 text-anveshak-accent hover:underline text-sm"
        >
          Back to Trackers
        </button>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 pt-5 pb-4 border-b border-anveshak-border">
        <Link
          to="/trackers"
          className="text-xs text-text-muted hover:text-anveshak-accent mb-3 inline-flex items-center gap-1"
        >
          ← Trackers
        </Link>

        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="font-mono text-sm text-text-muted">{tracker.case_number}</span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusBadgeClass(tracker.status)}`}>
                {tracker.status}
              </span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${priorityBadgeClass(tracker.priority)}`}>
                {tracker.priority}
              </span>
            </div>
            <h1 className="text-lg font-semibold text-text-primary mt-1 truncate">{tracker.title}</h1>
            <div className="flex items-center gap-4 mt-1 text-xs text-text-muted flex-wrap">
              {tracker.external_case_ref && (
                <span>Case ref: <span className="text-text-secondary">{tracker.external_case_ref}</span></span>
              )}
              {tracker.topic_id && (
                <Link
                  to={`/topics/${tracker.topic_id}/feed`}
                  className="text-anveshak-accent hover:underline"
                >
                  {tracker.topic_name || tracker.topic_id}
                </Link>
              )}
              {tracker.assigned_to && (
                <span>Assigned: <span className="text-text-secondary">{tracker.assigned_to}</span></span>
              )}
            </div>
          </div>

          {/* Status change */}
          <div className="flex items-center gap-2 shrink-0">
            {statusChanging ? (
              <select
                defaultValue={tracker.status}
                onChange={(e) => {
                  const val = e.target.value
                  if (val === 'concluded') {
                    setConcludeOpen(true)
                    setStatusChanging(false)
                  } else {
                    updateStatusMutation.mutate(val)
                  }
                }}
                className="bg-anveshak-card border border-anveshak-border rounded px-3 py-2 text-text-primary text-sm"
                autoFocus
              >
                <option value="watching">Watching</option>
                <option value="active">Active</option>
                <option value="concluded">Concluded</option>
              </select>
            ) : (
              tracker.status !== 'concluded' && (
                <button
                  onClick={() => setStatusChanging(true)}
                  className="text-xs text-text-muted border border-anveshak-border rounded px-2 py-1 hover:text-text-primary hover:border-anveshak-accent transition-colors"
                >
                  Change Status
                </button>
              )
            )}
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-anveshak-border px-6" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={activeTab === tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`relative px-4 py-3 text-sm font-medium transition-colors focus-visible:outline-none ${
              activeTab === tab.key
                ? 'text-anveshak-accent border-b-2 border-anveshak-accent'
                : 'text-text-muted hover:text-text-primary'
            }`}
          >
            {tab.label}
            {tab.key === 'pending' && tracker.pending_count > 0 && (
              <span className="ml-1.5 inline-flex items-center justify-center min-w-[1.1rem] px-1 py-0.5 rounded text-[10px] font-bold bg-yellow-500/20 text-yellow-400">
                {tracker.pending_count}
              </span>
            )}
            {tab.key === 'content' && tracker.content_count > 0 && (
              <span className="ml-1.5 inline-flex items-center justify-center min-w-[1.1rem] px-1 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400">
                {tracker.content_count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-6" role="tabpanel">

        {/* Overview tab */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Content Items', value: tracker.content_count },
                { label: 'Pending Review', value: tracker.pending_count },
                { label: 'Signals', value: '—' },
                { label: 'Notes', value: '—' },
              ].map((stat) => (
                <div key={stat.label} className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
                  <p className="text-xs text-text-muted">{stat.label}</p>
                  <p className="text-2xl font-bold text-text-primary mt-1">{stat.value}</p>
                </div>
              ))}
            </div>

            <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
              <h3 className="text-sm font-medium text-text-primary mb-3">Provenance Breakdown</h3>
              <div className="flex gap-6 text-sm">
                <div>
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-teal-500/20 text-teal-400 mr-2">SEED</span>
                  <span className="text-text-muted">Items that seeded this tracker</span>
                </div>
                <div>
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-500/20 text-green-400 mr-2">CONFIRMED</span>
                  <span className="text-text-muted">Auto-matched &amp; confirmed</span>
                </div>
                <div>
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/20 text-blue-400 mr-2">MANUAL</span>
                  <span className="text-text-muted">Manually added</span>
                </div>
              </div>
            </div>

            {tracker.closing_summary && (
              <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
                <h3 className="text-sm font-medium text-text-primary mb-2">Closing Summary</h3>
                <p className="text-sm text-text-secondary whitespace-pre-wrap">{tracker.closing_summary}</p>
                {tracker.concluded_at && (
                  <p className="text-xs text-text-muted mt-2">
                    Concluded {formatDate(tracker.concluded_at)}
                    {tracker.concluded_by && ` by ${tracker.concluded_by}`}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Content tab */}
        {activeTab === 'content' && (
          <div>
            {contentError ? (
              <p className="text-sm text-red-400 py-4">Failed to load content.</p>
            ) : contentLoading ? (
              <div className="flex justify-center py-10"><Spinner /></div>
            ) : content.length === 0 ? (
              <p className="text-text-muted text-sm">No confirmed content items yet.</p>
            ) : (
              <div className="space-y-3">
                {content.map((item) => (
                  <div key={item.id} className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${provenanceBadgeClass(item.attached_by)}`}>
                        {provenanceLabel(item.attached_by)}
                      </span>
                      {item.similarity_score != null && item.attached_by === 'auto' && (
                        <span className="text-xs text-text-muted">
                          {(item.similarity_score * 100).toFixed(0)}% match
                        </span>
                      )}
                      <span className="text-xs text-text-muted ml-auto">
                        {item.source_name && <>{item.source_name}</>}
                        {item.platform && <span className="ml-1 text-text-muted">({item.platform})</span>}
                      </span>
                    </div>
                    {item.clean_text && (
                      <p className="text-sm text-text-secondary line-clamp-3">{item.clean_text}</p>
                    )}
                    <p className="text-xs text-text-muted mt-2">{formatDate(item.captured_at)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Pending Review tab */}
        {activeTab === 'pending' && (
          <div>
            {pendingError ? (
              <p className="text-sm text-red-400 py-4">Failed to load pending items.</p>
            ) : pendingLoading ? (
              <div className="flex justify-center py-10"><Spinner /></div>
            ) : pending.length === 0 ? (
              <p className="text-text-muted text-sm">No items pending review.</p>
            ) : (
              <>
                <div className="flex justify-end mb-4">
                  <button
                    onClick={() => confirmAllMutation.mutate()}
                    disabled={confirmAllMutation.isPending}
                    className="bg-green-600/20 hover:bg-green-600/30 text-green-400 rounded px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
                  >
                    {confirmAllMutation.isPending ? 'Accepting…' : `Accept All (${pending.length})`}
                  </button>
                </div>
                <div className="space-y-3">
                  {pending.map((item) => (
                    <div key={item.id} className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          {item.similarity_score != null && (
                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-xs font-semibold text-anveshak-accent">
                                {(item.similarity_score * 100).toFixed(0)}% match
                              </span>
                              {item.source_name && (
                                <span className="text-xs text-text-muted">
                                  {item.source_name}
                                  {item.platform && ` (${item.platform})`}
                                </span>
                              )}
                            </div>
                          )}
                          {item.clean_text && (
                            <p className="text-sm text-text-secondary line-clamp-3">{item.clean_text}</p>
                          )}
                          <p className="text-xs text-text-muted mt-2">{formatDate(item.captured_at)}</p>
                        </div>
                        <div className="flex gap-2 shrink-0">
                          <button
                            onClick={() => confirmMutation.mutate(item.id)}
                            disabled={confirmMutation.isPending || rejectMutation.isPending}
                            className="bg-green-600/20 hover:bg-green-600/30 text-green-400 rounded px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-50"
                          >
                            Accept
                          </button>
                          <button
                            onClick={() => rejectMutation.mutate(item.id)}
                            disabled={confirmMutation.isPending || rejectMutation.isPending}
                            className="bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {/* Notes tab */}
        {activeTab === 'notes' && (
          <div className="space-y-4">
            <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
              <textarea
                value={noteBody}
                onChange={(e) => setNoteBody(e.target.value)}
                placeholder="Add an investigation note…"
                rows={3}
                className="w-full bg-anveshak-card border border-anveshak-border rounded px-3 py-2 text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent resize-none"
              />
              <div className="flex justify-end mt-2">
                <button
                  onClick={() => noteBody.trim() && addNoteMutation.mutate(noteBody.trim())}
                  disabled={!noteBody.trim() || addNoteMutation.isPending}
                  className="bg-anveshak-accent hover:bg-anveshak-accent/80 text-white rounded px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {addNoteMutation.isPending ? 'Saving…' : 'Submit'}
                </button>
              </div>
            </div>

            {notesError ? (
              <p className="text-sm text-red-400 py-4">Failed to load notes.</p>
            ) : notesLoading ? (
              <div className="flex justify-center py-6"><Spinner /></div>
            ) : notes.length === 0 ? (
              <p className="text-text-muted text-sm">No notes yet.</p>
            ) : (
              <div className="space-y-3">
                {[...notes].reverse().map((note: TrackerNote) => (
                  <div key={note.id} className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-text-secondary">{note.user_id}</span>
                      <span className="text-xs text-text-muted">{formatDate(note.created_at)}</span>
                    </div>
                    <p className="text-sm text-text-primary whitespace-pre-wrap">{note.body}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Signals tab */}
        {activeTab === 'signals' && (
          <div>
            {signalsError ? (
              <p className="text-sm text-red-400 py-4">Failed to load signals.</p>
            ) : signalsLoading ? (
              <div className="flex justify-center py-10"><Spinner /></div>
            ) : !signals || (signals as unknown[]).length === 0 ? (
              <p className="text-text-muted text-sm">No signals linked to this tracker.</p>
            ) : (
              <div className="space-y-3">
                {(signals as Record<string, unknown>[]).map((signal, i) => (
                  <div key={String(signal.id ?? i)} className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <p className="text-sm font-medium text-text-primary">{String(signal.title ?? signal.id ?? 'Signal')}</p>
                      {typeof signal.severity === 'string' && (
                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${severityBadgeClass(signal.severity)}`}>
                          {signal.severity}
                        </span>
                      )}
                      {typeof signal.signal_type === 'string' && (
                        <span className="text-xs text-text-muted">({signal.signal_type})</span>
                      )}
                      {typeof signal.status === 'string' && (
                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          signal.status === 'new' ? 'bg-blue-500/20 text-blue-400'
                          : signal.status === 'acknowledged' ? 'bg-yellow-500/20 text-yellow-400'
                          : 'bg-gray-500/20 text-gray-400'
                        }`}>
                          {signal.status}
                        </span>
                      )}
                    </div>
                    {typeof signal.description === 'string' && signal.description && (
                      <p className="text-sm text-text-secondary mb-2">{signal.description}</p>
                    )}
                    {typeof signal.detail === 'string' && signal.detail && (
                      <p className="text-sm text-text-muted">{signal.detail}</p>
                    )}
                    <div className="flex items-center gap-4 mt-2 text-xs text-text-muted">
                      {typeof signal.independent_source_count === 'number' && (
                        <span>{signal.independent_source_count} independent sources</span>
                      )}
                      {signal.created_at != null && (
                        <span>{formatDate(String(signal.created_at))}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Reports tab */}
        {activeTab === 'reports' && (
          <div className="space-y-4">
            <div className="flex justify-end">
              <button
                onClick={() => generateReportMutation.mutate()}
                disabled={generateReportMutation.isPending}
                className="bg-anveshak-accent hover:bg-anveshak-accent/80 text-white rounded px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
              >
                {generateReportMutation.isPending ? 'Generating...' : 'Generate Report'}
              </button>
            </div>
            {reportsError ? (
              <p className="text-sm text-red-400 py-4">Failed to load reports.</p>
            ) : reportsLoading ? (
              <div className="flex justify-center py-10"><Spinner /></div>
            ) : !reports || (reports as unknown[]).length === 0 ? (
              <p className="text-text-muted text-sm">No reports generated for this tracker.</p>
            ) : (
              <div className="space-y-3">
                {(reports as Record<string, unknown>[]).map((report, i) => (
                  <div key={String(report.id ?? i)} className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {typeof report.report_type === 'string' && (
                          <span className="text-sm font-medium text-text-primary">{report.report_type}</span>
                        )}
                        {typeof report.generation_status === 'string' && (
                          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${reportStatusBadgeClass(report.generation_status)}`}>
                            {report.generation_status}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        {report.created_at != null && (
                          <span className="text-xs text-text-muted">{formatDate(String(report.created_at))}</span>
                        )}
                        {typeof report.id === 'string' && (
                          <Link
                            to={`/reports?id=${report.id}`}
                            className="text-xs text-anveshak-accent hover:underline"
                          >
                            View
                          </Link>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Audit Log tab */}
        {activeTab === 'audit' && (
          <div>
            {auditError ? (
              <p className="text-sm text-red-400 py-4">Failed to load audit log.</p>
            ) : auditLoading ? (
              <div className="flex justify-center py-10"><Spinner /></div>
            ) : auditLog.length === 0 ? (
              <p className="text-text-muted text-sm">No audit log entries.</p>
            ) : (
              <div className="space-y-2">
                {auditLog.map((entry: TrackerAuditEntry) => (
                  <div key={entry.id} className="bg-anveshak-card border border-anveshak-border rounded-lg px-4 py-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold text-anveshak-accent uppercase tracking-wide">{entry.action}</span>
                      <span className="text-xs text-text-muted">{formatDate(entry.created_at)}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-text-secondary">{entry.actor_id}</span>
                      {entry.detail && Object.keys(entry.detail).length > 0 && (
                        <span className="text-xs text-text-muted">
                          {formatAuditDetail(entry.action, entry.detail as Record<string, unknown>)}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <ConcludeModal
        open={concludeOpen}
        trackerId={id!}
        onClose={() => setConcludeOpen(false)}
        onConcluded={() => {
          setConcludeOpen(false)
          qc.invalidateQueries({ queryKey: ['tracker', id] })
          qc.invalidateQueries({ queryKey: ['trackers'] })
        }}
      />
    </div>
  )
}
