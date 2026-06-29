import { useState, useMemo, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { systemApi, AuditTrailEntry } from '../../api/system'
import { topicsApi } from '../../api/topics'
import { useAuth } from '../../contexts/AuthContext'

// ── Constants ──────────────────────────────────────────────────────────

const PAGE_SIZE = 25

type SortField = 'created_at' | 'username' | 'action' | 'resource_type' | 'resource_id'
type SortDir = 'asc' | 'desc'

/** Backend returns details as double-encoded JSON string — parse to object. */
function parseDetails(raw: unknown): Record<string, unknown> {
  if (!raw) return {}
  if (typeof raw === 'object' && !Array.isArray(raw)) return raw as Record<string, unknown>
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      if (typeof parsed === 'string') {
        try { return JSON.parse(parsed) } catch { return {} }
      }
      return typeof parsed === 'object' && parsed !== null ? parsed : {}
    } catch { return {} }
  }
  return {}
}

const RESOURCE_TYPES = [
  { value: '', label: 'All' },
  { value: 'source', label: 'Sources' },
  { value: 'topic', label: 'Topics' },
  { value: 'report', label: 'Reports' },
  { value: 'signal', label: 'Signals' },
  { value: 'user', label: 'Users' },
  { value: 'export', label: 'Exports' },
]

const ACTION_COLORS: Record<string, string> = {
  create: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  delete: 'bg-red-500/20 text-red-400 border-red-500/30',
  generate: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  update: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  change: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  acknowledge: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  dismiss: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  export: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  link: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
  unlink: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
}

function getActionColor(action: string): string {
  for (const [key, cls] of Object.entries(ACTION_COLORS)) {
    if (action.includes(key)) return cls
  }
  return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
}

const INPUT_CLASS =
  'bg-white/10 border border-white/20 rounded-md px-3 py-1.5 text-xs text-text-primary ' +
  'placeholder:text-text-muted/50 focus:outline-none focus:ring-1 focus:ring-anveshak-accent focus:border-anveshak-accent'

// ── CSV Export ─────────────────────────────────────────────────────────

function exportCsv(entries: AuditTrailEntry[]) {
  const columns = ['Time', 'Username', 'User ID', 'Action', 'Resource Type', 'Resource ID', 'Details', 'IP']
  const rows = entries.map((e) => [
    format(new Date(e.created_at), 'yyyy-MM-dd HH:mm:ss'),
    e.username || '',
    e.user_id,
    e.action,
    e.resource_type,
    e.resource_id,
    JSON.stringify(parseDetails(e.details)),
    e.ip_address || '',
  ])

  const escape = (v: string) => `"${v.replace(/"/g, '""')}"`
  const csv = [columns.map(escape).join(','), ...rows.map((r) => r.map(escape).join(','))].join('\n')

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `anveshak_audit_trail_${format(new Date(), 'yyyy-MM-dd')}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Sort Arrow ────────────────────────────────────────────────────────

function SortArrow({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="text-text-muted/30 ml-0.5">↕</span>
  return <span className="text-anveshak-accent ml-0.5">{dir === 'asc' ? '▲' : '▼'}</span>
}

// ── Main Component ────────────────────────────────────────────────────

interface Props {
  embedded?: boolean
}

export default function AuditTrailPage({ embedded = false }: Props) {
  const { user } = useAuth()
  const isAnalyst = user?.role === 'analyst'

  // Filters
  const [resourceType, setResourceType] = useState('')
  const [resourceId, setResourceId] = useState('')
  const [limit, setLimit] = useState(250)
  const [selectedActions, setSelectedActions] = useState<Set<string>>(new Set())

  // Sort
  const [sortField, setSortField] = useState<SortField>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  // Pagination
  const [page, setPage] = useState(0)

  // Modal
  const [selectedEntry, setSelectedEntry] = useState<AuditTrailEntry | null>(null)

  // Topics for analyst picker
  const { data: topics = [] } = useQuery({
    queryKey: ['topics'],
    queryFn: topicsApi.list,
    staleTime: 60_000,
  })

  const canQuery = !isAnalyst || resourceId.trim().length > 0

  const { data: entries = [], isLoading, error } = useQuery({
    queryKey: ['audit-trail', resourceType, resourceId, limit],
    queryFn: () =>
      systemApi.getAuditTrail({
        resource_type: resourceType || undefined,
        resource_id: resourceId || undefined,
        limit,
      }),
    refetchInterval: 30000,
    enabled: canQuery,
  })

  // Unique action types for filter chips
  const actionTypes = useMemo(
    () => [...new Set(entries.map((e) => e.action))].sort(),
    [entries],
  )

  const toggleAction = useCallback((action: string) => {
    setSelectedActions((prev) => {
      const next = new Set(prev)
      if (next.has(action)) next.delete(action)
      else next.add(action)
      return next
    })
    setPage(0)
  }, [])

  // Filter → sort → paginate
  const processed = useMemo(() => {
    let list = [...entries]

    // Action filter
    if (selectedActions.size > 0) {
      list = list.filter((e) => selectedActions.has(e.action))
    }

    // Sort
    list.sort((a, b) => {
      let av: string, bv: string
      if (sortField === 'username') {
        av = a.username || a.user_id
        bv = b.username || b.user_id
      } else {
        av = String((a as unknown as Record<string, unknown>)[sortField] ?? '')
        bv = String((b as unknown as Record<string, unknown>)[sortField] ?? '')
      }
      const cmp = av.localeCompare(bv)
      return sortDir === 'asc' ? cmp : -cmp
    })

    return list
  }, [entries, selectedActions, sortField, sortDir])

  // Pagination
  const totalPages = Math.max(1, Math.ceil(processed.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages - 1)
  const pageEntries = processed.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE)
  const showingFrom = processed.length === 0 ? 0 : safePage * PAGE_SIZE + 1
  const showingTo = Math.min((safePage + 1) * PAGE_SIZE, processed.length)

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir('asc')
    }
    setPage(0)
  }

  const SORTABLE_HEADERS: { field: SortField; label: string; align?: string }[] = [
    { field: 'created_at', label: 'Time' },
    { field: 'username', label: 'User' },
    { field: 'action', label: 'Action' },
    { field: 'resource_type', label: 'Resource' },
    { field: 'resource_id', label: 'Resource ID' },
  ]

  return (
    <div className={embedded ? 'h-full flex flex-col' : 'h-full flex flex-col p-6'}>
      {!embedded && (
        <>
          <h1 className="text-xl font-semibold text-text-primary">Audit Trail</h1>
          <p className="text-sm text-text-muted mt-0.5 mb-4">
            Complete record of all system actions
          </p>
        </>
      )}

      {/* ── Filters ────────────────────────────────────────────────────── */}
      <div className="px-4 py-3 border-b border-anveshak-border bg-anveshak-bg/50 space-y-2">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider">Resource</label>
            <select
              value={resourceType}
              onChange={(e) => { setResourceType(e.target.value); setPage(0) }}
              className={INPUT_CLASS}
            >
              {RESOURCE_TYPES.map((rt) => (
                <option key={rt.value} value={rt.value}>{rt.label}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider">
              {isAnalyst ? 'Topic' : 'ID'}
            </label>
            {isAnalyst ? (
              <select
                value={resourceId}
                onChange={(e) => {
                  setResourceId(e.target.value)
                  if (e.target.value) setResourceType('topic')
                  setPage(0)
                }}
                className={`${INPUT_CLASS} w-64`}
              >
                <option value="">Select a topic...</option>
                {topics.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={resourceId}
                onChange={(e) => { setResourceId(e.target.value); setPage(0) }}
                placeholder="Filter by resource ID..."
                className={`${INPUT_CLASS} w-52`}
              />
            )}
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider">Limit</label>
            <select
              value={limit}
              onChange={(e) => { setLimit(Number(e.target.value)); setPage(0) }}
              className={INPUT_CLASS}
            >
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={250}>250</option>
              <option value={500}>500</option>
            </select>
          </div>

          {/* Export CSV */}
          {processed.length > 0 && (
            <button
              onClick={() => exportCsv(processed)}
              className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white/5 border border-white/10 text-text-secondary text-xs hover:bg-white/10 hover:border-white/20 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Export CSV
            </button>
          )}
        </div>

        {/* Action filter chips */}
        {actionTypes.length > 1 && (
          <div className="flex flex-wrap gap-1.5">
            {actionTypes.map((action) => {
              const isActive = selectedActions.has(action)
              return (
                <button
                  key={action}
                  onClick={() => toggleAction(action)}
                  className={`px-2.5 py-0.5 rounded-full border text-[10px] font-semibold transition-colors ${
                    isActive
                      ? getActionColor(action)
                      : 'bg-white/5 border-white/10 text-text-muted hover:bg-white/10'
                  }`}
                >
                  {action}
                </button>
              )
            })}
            {selectedActions.size > 0 && (
              <button
                onClick={() => { setSelectedActions(new Set()); setPage(0) }}
                className="px-2 py-0.5 text-[10px] text-text-muted hover:text-text-primary transition-colors"
              >
                Clear
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Table ──────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-auto">
        {isLoading && (
          <p className="text-sm text-text-muted py-12 text-center">Loading audit trail...</p>
        )}

        {error && (
          <p className="text-sm text-red-400 py-12 text-center">
            {(error as any)?.response?.status === 403
              ? 'Select a resource type or ID above to view audit entries.'
              : `Failed to load audit trail: ${(error as any)?.response?.data?.detail || (error as Error).message}`}
          </p>
        )}

        {!isLoading && !error && !canQuery && (
          <p className="text-sm text-text-muted py-12 text-center">
            Select a topic above to view its audit trail.
          </p>
        )}

        {!isLoading && !error && canQuery && entries.length === 0 && (
          <p className="text-sm text-text-muted py-12 text-center">No audit entries found.</p>
        )}

        {!isLoading && pageEntries.length > 0 && (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-anveshak-bg z-10 shadow-[0_1px_0_0_rgba(255,255,255,0.06)]">
              <tr className="text-left">
                {SORTABLE_HEADERS.map((h) => (
                  <th
                    key={h.field}
                    onClick={() => handleSort(h.field)}
                    className="py-3 px-3 font-medium text-text-muted uppercase tracking-wider text-[10px] cursor-pointer hover:text-text-primary transition-colors select-none"
                  >
                    {h.label}
                    <SortArrow active={sortField === h.field} dir={sortDir} />
                  </th>
                ))}
                <th className="py-3 px-3 font-medium text-text-muted uppercase tracking-wider text-[10px]">Details</th>
                <th className="py-3 px-3 font-medium text-text-muted uppercase tracking-wider text-[10px] text-right">IP</th>
              </tr>
            </thead>
            <tbody>
              {pageEntries.map((entry, idx) => (
                <tr
                  key={entry.id}
                  className={`border-b border-white/[0.04] hover:bg-white/[0.05] transition-colors ${
                    idx % 2 === 0 ? 'bg-white/[0.02]' : ''
                  }`}
                >
                  <td className="py-3 px-3 text-text-muted font-mono whitespace-nowrap text-[11px]">
                    {format(new Date(entry.created_at), 'dd MMM HH:mm:ss')}
                  </td>
                  <td
                    className="py-3 px-3 text-text-secondary text-[11px] max-w-[180px] truncate"
                    title={`${entry.username || 'Unknown'} (${entry.user_id})`}
                  >
                    {entry.username || entry.user_id.slice(0, 12) + '…'}
                  </td>
                  <td className="py-3 px-3">
                    <span
                      className={`inline-block px-2.5 py-0.5 rounded-full border text-[10px] font-semibold tracking-wide ${getActionColor(entry.action)}`}
                    >
                      {entry.action}
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    <span className="text-text-secondary bg-white/5 px-2 py-0.5 rounded text-[11px]">
                      {entry.resource_type}
                    </span>
                  </td>
                  <td
                    className="py-3 px-3 text-text-muted font-mono text-[11px] max-w-[180px] truncate"
                    title={entry.resource_id}
                  >
                    {entry.resource_id}
                  </td>
                  <td className="py-3 px-3">
                    <DetailsButton details={parseDetails(entry.details)} action={entry.action} onClick={() => setSelectedEntry(entry)} />
                  </td>
                  <td className="py-3 px-3 text-text-muted font-mono text-[11px] text-right">
                    {entry.ip_address || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Pagination ─────────────────────────────────────────────────── */}
      {processed.length > PAGE_SIZE && (
        <div className="flex items-center justify-between px-4 py-2.5 border-t border-anveshak-border bg-anveshak-bg/50 text-xs">
          <span className="text-text-muted">
            Showing {showingFrom}–{showingTo} of {processed.length}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(0)}
              disabled={safePage === 0}
              className="px-2 py-1 rounded text-text-muted hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              ««
            </button>
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={safePage === 0}
              className="px-2 py-1 rounded text-text-muted hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              ‹
            </button>
            <span className="px-3 py-1 text-text-secondary font-medium">
              {safePage + 1} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={safePage >= totalPages - 1}
              className="px-2 py-1 rounded text-text-muted hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              ›
            </button>
            <button
              onClick={() => setPage(totalPages - 1)}
              disabled={safePage >= totalPages - 1}
              className="px-2 py-1 rounded text-text-muted hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              »»
            </button>
          </div>
        </div>
      )}

      {/* ── Details Modal ──────────────────────────────────────────────── */}
      {selectedEntry && (
        <DetailsModal entry={selectedEntry} onClose={() => setSelectedEntry(null)} />
      )}
    </div>
  )
}


function DetailsButton({ details, action, onClick }: { details: Record<string, unknown>; action: string; onClick: () => void }) {
  if (!details || Object.keys(details).length === 0) {
    return <span className="text-text-muted/40">—</span>
  }

  if (action.includes('credibility') && details.old_score !== undefined) {
    const oldScore = Number(details.old_score)
    const newScore = Number(details.new_score)
    const delta = newScore - oldScore
    const reason = String(details.reason || '')
    return (
      <button onClick={onClick} className="text-left cursor-pointer hover:bg-white/5 rounded px-1 -mx-1 transition-colors">
        <span className="text-text-secondary text-[11px]">{oldScore.toFixed(0)}</span>
        <span className="mx-1 text-text-muted">→</span>
        <span className="text-text-primary font-medium text-[11px]">{newScore.toFixed(0)}</span>
        <span className={`ml-1.5 text-[10px] font-semibold ${delta >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          {delta >= 0 ? '+' : ''}{delta.toFixed(0)}
        </span>
        {reason && (
          <span className="ml-2 text-text-muted text-[10px] truncate inline-block max-w-[180px] align-bottom" title={reason}>
            {reason}
          </span>
        )}
      </button>
    )
  }

  const keyCount = Object.keys(details).length
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/5 border border-white/10
                 text-text-secondary text-[10px] hover:bg-white/10 hover:border-white/20 transition-colors cursor-pointer"
    >
      <svg className="w-3 h-3 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      {keyCount} {keyCount === 1 ? 'field' : 'fields'}
    </button>
  )
}


function DetailsModal({ entry, onClose }: { entry: AuditTrailEntry; onClose: () => void }) {
  const details = useMemo(() => parseDetails(entry.details), [entry.details])
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-[#1a1f2e] border border-white/10 rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">Audit Entry Details</h3>
            <p className="text-[11px] text-text-muted mt-0.5 font-mono">
              {format(new Date(entry.created_at), 'dd MMM yyyy HH:mm:ss')}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-white/10 text-text-muted hover:text-text-primary transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-5 py-4 grid grid-cols-2 gap-3 border-b border-white/10">
          <MetaField label="Action">
            <span className={`inline-block px-2.5 py-0.5 rounded-full border text-[10px] font-semibold ${getActionColor(entry.action)}`}>
              {entry.action}
            </span>
          </MetaField>
          <MetaField label="Resource Type">
            <span className="bg-white/5 px-2 py-0.5 rounded text-[11px] text-text-secondary">{entry.resource_type}</span>
          </MetaField>
          <MetaField label="User">
            <span className="text-[11px] text-text-secondary">{entry.username || 'Unknown'}</span>
            <span className="font-mono text-[10px] text-text-muted ml-1">({entry.user_id})</span>
          </MetaField>
          <MetaField label="IP Address">
            <span className="font-mono text-[11px] text-text-secondary">{entry.ip_address || '—'}</span>
          </MetaField>
          <div className="col-span-2">
            <MetaField label="Resource ID">
              <span className="font-mono text-[11px] text-text-secondary break-all">{entry.resource_id}</span>
            </MetaField>
          </div>
        </div>

        <div className="px-5 py-4">
          <p className="text-[10px] font-medium text-text-muted uppercase tracking-wider mb-2">Details</p>
          {Object.keys(details).length > 0 ? (
            <div className="bg-black/30 rounded-lg border border-white/5 p-4 max-h-64 overflow-auto">
              <div className="space-y-2">
                {Object.entries(details).map(([key, value]) => (
                  <div key={key} className="flex gap-3">
                    <span className="text-anveshak-accent font-mono text-[11px] font-medium shrink-0">{key}:</span>
                    <span className="text-text-secondary font-mono text-[11px] break-all">
                      {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-text-muted/50 text-xs">No additional details recorded.</p>
          )}
        </div>
      </div>
    </div>
  )
}


function MetaField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] font-medium text-text-muted uppercase tracking-wider mb-1">{label}</p>
      {children}
    </div>
  )
}
