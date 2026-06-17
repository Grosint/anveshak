import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { trackersApi, type TrackerContentItem, type TrackerNote, type TrackerAuditEntry } from '../api/trackers'
import { Spinner } from '../components/ui/Spinner'
import { ConcludeModal } from '../components/trackers/ConcludeModal'

type Tab = 'overview' | 'content' | 'pending' | 'notes' | 'signals' | 'audit'

const TABS: { key: Tab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'content',  label: 'Content' },
  { key: 'pending',  label: 'Pending Review' },
  { key: 'notes',    label: 'Notes' },
  { key: 'signals',  label: 'Signals' },
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

export default function TrackerDetail() {
  const { id } = useParams<{ id: string }>()
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

  const { data: content = [], isLoading: contentLoading } = useQuery({
    queryKey: ['tracker-content', id],
    queryFn: () => trackersApi.listContent(id!),
    enabled: !!id && activeTab === 'content',
  })

  const { data: pending = [], isLoading: pendingLoading } = useQuery({
    queryKey: ['tracker-pending', id],
    queryFn: () => trackersApi.listPending(id!),
    enabled: !!id && activeTab === 'pending',
  })

  const { data: notes = [], isLoading: notesLoading } = useQuery({
    queryKey: ['tracker-notes', id],
    queryFn: () => trackersApi.listNotes(id!),
    enabled: !!id && activeTab === 'notes',
  })

  const { data: signals = [], isLoading: signalsLoading } = useQuery({
    queryKey: ['tracker-signals', id],
    queryFn: () => trackersApi.listSignals(id!),
    enabled: !!id && activeTab === 'signals',
  })

  const { data: auditLog = [], isLoading: auditLoading } = useQuery({
    queryKey: ['tracker-audit', id],
    queryFn: () => trackersApi.listAuditLog(id!),
    enabled: !!id && activeTab === 'audit',
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
  })

  const updateStatusMutation = useMutation({
    mutationFn: (status: string) => trackersApi.updateStatus(id!, { status }),
    onSuccess: () => {
      setStatusChanging(false)
      qc.invalidateQueries({ queryKey: ['tracker', id] })
      qc.invalidateQueries({ queryKey: ['trackers'] })
    },
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
                  to={`/topics/${tracker.topic_id}`}
                  className="text-anveshak-accent hover:underline"
                >
                  View Topic
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
            {contentLoading ? (
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
            {pendingLoading ? (
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

            {notesLoading ? (
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
            {signalsLoading ? (
              <div className="flex justify-center py-10"><Spinner /></div>
            ) : !signals || (signals as unknown[]).length === 0 ? (
              <p className="text-text-muted text-sm">No signals linked to this tracker.</p>
            ) : (
              <div className="space-y-3">
                {(signals as Record<string, unknown>[]).map((signal, i) => (
                  <div key={String(signal.id ?? i)} className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
                    <p className="text-sm text-text-primary">{String(signal.title ?? signal.id ?? 'Signal')}</p>
                    {signal.created_at != null && (
                      <p className="text-xs text-text-muted mt-1">{formatDate(String(signal.created_at))}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Audit Log tab */}
        {activeTab === 'audit' && (
          <div>
            {auditLoading ? (
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
                        <span className="text-xs text-text-muted font-mono">
                          {JSON.stringify(entry.detail)}
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
