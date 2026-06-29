import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useQueries } from '@tanstack/react-query'
import { ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts'
import { sourcesApi, Source, CreateSourcePayload, UpdateSourcePayload, HealthStatus } from '../api/sources'
import { AddSourceModal } from '../components/sources/AddSourceModal'
import { AuditLogTable } from '../components/sources/AuditLogTable'
import { PlatformBadge } from '../components/content/PlatformBadge'
import { CredibilityBadge } from '../components/content/CredibilityBadge'
import { Button } from '../components/ui/Button'
import { Pagination } from '../components/ui/Pagination'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { formatDistanceToNow } from 'date-fns'

// ── Helpers ─────────────────────────────────────────────────────────────────

function CredibilityBar({ score }: { score: number }) {
  const color = score >= 70 ? 'bg-cred-high' : score >= 40 ? 'bg-cred-mid' : 'bg-cred-low'
  return (
    <div
      className="w-full h-1.5 bg-anveshak-muted rounded-full overflow-hidden"
      role="meter"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Credibility: ${score}`}
    >
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${score}%` }} />
    </div>
  )
}

function HealthBadge({ status }: { status: HealthStatus }) {
  const cfg: Record<HealthStatus, { dot: string; label: string; text: string }> = {
    healthy:    { dot: 'bg-cred-high',   label: 'Healthy',    text: 'text-cred-high' },
    degraded:   { dot: 'bg-yellow-400',  label: 'Degraded',   text: 'text-yellow-400' },
    down:       { dot: 'bg-signal-high', label: 'Down',       text: 'text-signal-high' },
    unverified: { dot: 'bg-text-muted',  label: 'Unverified', text: 'text-text-muted' },
  }
  const c = cfg[status] ?? { dot: 'bg-text-muted', label: status, text: 'text-text-muted' }
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${c.text}`}>
      <span className={`w-2 h-2 rounded-full shrink-0 ${c.dot}`} aria-hidden="true" />
      {c.label}
    </span>
  )
}

// ── Filter bar ───────────────────────────────────────────────────────────────

type FilterValue = 'all' | HealthStatus

interface FilterBarProps {
  active: FilterValue
  onChange: (f: FilterValue) => void
  counts: Record<HealthStatus, number>
}

function FilterBar({ active, onChange, counts }: FilterBarProps) {
  const filters: { value: FilterValue; label: string }[] = [
    { value: 'all',        label: 'All' },
    { value: 'healthy',    label: 'Healthy' },
    { value: 'degraded',   label: 'Degraded' },
    { value: 'down',       label: 'Down' },
    { value: 'unverified', label: 'Unverified' },
  ]
  return (
    <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by health status">
      {filters.map((f) => {
        const isActive = active === f.value
        const count = f.value !== 'all' ? counts[f.value as HealthStatus] : undefined
        const isDown = f.value === 'down' && (counts.down ?? 0) > 0
        return (
          <button
            key={f.value}
            onClick={() => onChange(f.value)}
            aria-pressed={isActive}
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              isActive
                ? 'bg-anveshak-accent text-white'
                : 'bg-anveshak-muted text-text-secondary hover:text-text-primary'
            }`}
          >
            {f.label}
            {count !== undefined && count > 0 && (
              <span
                className={`text-[10px] font-bold min-w-[18px] h-[18px] flex items-center justify-center rounded-full ${
                  isDown && !isActive
                    ? 'bg-signal-high text-white'
                    : isActive
                    ? 'bg-white/20 text-white'
                    : 'bg-anveshak-border text-text-muted'
                }`}
              >
                {count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

// ── Source row ───────────────────────────────────────────────────────────────

interface SourceRowProps {
  source: Source
  onSelect: (id: string) => void
  isSelected: boolean
  warningCount: number
}

function SourceRow({ source, onSelect, isSelected, warningCount }: SourceRowProps) {
  return (
    <div
      className={`bg-anveshak-card border rounded-lg p-3 cursor-pointer hover:border-anveshak-accent/40 transition-all ${
        isSelected ? 'border-anveshak-accent' : 'border-anveshak-border'
      }`}
      onClick={() => onSelect(source.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onSelect(source.id)}
      aria-label={`View source: ${source.name}`}
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5 flex-wrap min-w-0">
          <PlatformBadge platform={source.platform} />
          <HealthBadge status={source.health_status} />
          {source.topic_links_count === 0 && (
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-yellow-400/20 text-yellow-400" title="Not linked to any topic — this source will not be scraped">
              No topics
            </span>
          )}
          {warningCount > 0 && (
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-signal-high/20 text-signal-high">
              ⚠ {warningCount}
            </span>
          )}
        </div>
        <CredibilityBadge score={source.credibility_score} />
      </div>

      <p className="font-medium text-text-primary text-sm truncate">{source.name}</p>
      <p className="text-xs text-text-muted font-mono truncate">{source.url_or_handle}</p>

      <div className="mt-2 flex items-center justify-between gap-2">
        <CredibilityBar score={source.credibility_score} />
        {source.consecutive_failures > 0 && (
          <span className="text-[10px] text-signal-high shrink-0">
            {source.consecutive_failures} fail{source.consecutive_failures > 1 ? 's' : ''}
          </span>
        )}
      </div>

      {source.last_checked_at && (
        <p className="text-[10px] text-text-muted mt-1">
          Checked {formatDistanceToNow(new Date(source.last_checked_at), { addSuffix: true })}
        </p>
      )}
    </div>
  )
}

// ── Delete confirm ───────────────────────────────────────────────────────────

interface DeleteConfirmProps {
  sourceName: string
  contentCount: number | null
  onConfirm: (force: boolean) => void
  onCancel: () => void
  isPending: boolean
}

function DeleteConfirm({ sourceName, contentCount, onConfirm, onCancel, isPending }: DeleteConfirmProps) {
  const hasContent = contentCount !== null && contentCount > 0
  return (
    <div className="rounded-lg border border-signal-high/30 bg-signal-high/5 p-4 space-y-3">
      <p className="text-sm font-medium text-signal-high">Delete "{sourceName}"?</p>
      {hasContent && (
        <p className="text-xs text-text-muted">
          This source has <strong className="text-text-primary">{contentCount} content item{contentCount! > 1 ? 's' : ''}</strong>.
          They will be orphaned (source_id set to null).
        </p>
      )}
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="secondary"
          onClick={() => onConfirm(hasContent)}
          loading={isPending}
          className="border-signal-high/40 text-signal-high hover:bg-signal-high/10"
        >
          {hasContent ? 'Delete anyway' : 'Confirm delete'}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={isPending}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

// ── Detail panel ─────────────────────────────────────────────────────────────

type DetailTab = 'overview' | 'audit'

interface DetailPanelProps {
  source: Source
  warningCount: number
  auditLog: any[]
  isLoadingAudit: boolean
  detailTab: DetailTab
  setDetailTab: (t: DetailTab) => void
}

function DetailPanel({
  source, warningCount, auditLog, isLoadingAudit, detailTab, setDetailTab,
}: DetailPanelProps) {
  const qc = useQueryClient()

  // ── credibility update state
  const [newScore, setNewScore] = useState('')
  const [reason, setReason]     = useState('')

  // ── edit state
  const [editName, setEditName]       = useState(source.name)
  const [editUrl, setEditUrl]         = useState(source.url_or_handle)
  const [editDirty, setEditDirty]     = useState(false)

  // ── delete state
  const [deleteMode, setDeleteMode]   = useState(false)
  const [contentCount, setContentCount] = useState<number | null>(null)

  // ── re-check state
  const [recheckError, setRecheckError] = useState<string | null>(null)

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['sources'] })
    qc.invalidateQueries({ queryKey: ['audit', source.id] })
  }

  const updateCred = useMutation({
    mutationFn: ({ score, rsn }: { score: number; rsn: string }) =>
      sourcesApi.updateCredibility(source.id, score, rsn),
    onSuccess: () => { invalidate(); setNewScore(''); setReason('') },
  })

  const updateFields = useMutation({
    mutationFn: (payload: UpdateSourcePayload) => sourcesApi.update(source.id, payload),
    onSuccess: () => { invalidate(); setEditDirty(false) },
  })

  const deleteSrc = useMutation({
    mutationFn: (force: boolean) => sourcesApi.delete(source.id, force),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sources'] })
      // parent will deselect because source is gone
    },
  })

  const recheck = useMutation({
    mutationFn: () => sourcesApi.checkHealth(source.id),
    onSuccess: () => { setRecheckError(null); qc.invalidateQueries({ queryKey: ['sources'] }) },
    onError: (err: unknown) => setRecheckError(err instanceof Error ? err.message : 'Re-check failed'),
  })

  async function handleCredUpdate(e: React.FormEvent) {
    e.preventDefault()
    if (!newScore || !reason.trim()) return
    await updateCred.mutateAsync({ score: Number(newScore), rsn: reason.trim() })
  }

  async function handleFieldsSave(e: React.FormEvent) {
    e.preventDefault()
    const payload: UpdateSourcePayload = {}
    if (editName.trim() !== source.name) payload.name = editName.trim()
    if (editUrl.trim() !== source.url_or_handle) payload.url_or_handle = editUrl.trim()
    if (!Object.keys(payload).length) return
    await updateFields.mutateAsync(payload)
  }

  function handleDeleteClick() {
    // Optimistically show confirm; content count comes from the 409 response if needed
    setContentCount(null)
    setDeleteMode(true)
  }

  async function handleDeleteConfirm(force: boolean) {
    try {
      await deleteSrc.mutateAsync(force)
    } catch (err: any) {
      // 409 → parse content count from detail message
      const detail: string = err?.response?.data?.detail ?? ''
      const match = detail.match(/(\d+) content item/)
      if (match) setContentCount(parseInt(match[1], 10))
    }
  }

  const TABS: { key: DetailTab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'audit',    label: 'Audit log' },
  ]

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <PlatformBadge platform={source.platform} />
          <HealthBadge status={source.health_status} />
          {source.topic_links_count === 0 && (
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-yellow-400/20 text-yellow-400">
              Not linked to any topic
            </span>
          )}
          {warningCount > 0 && (
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-signal-high/20 text-signal-high">
              ⚠ {warningCount} report warning{warningCount > 1 ? 's' : ''}
            </span>
          )}
        </div>
        <h2 className="text-lg font-semibold text-text-primary">{source.name}</h2>
        <p className="text-xs text-text-muted font-mono break-all">{source.url_or_handle}</p>
        <div className="mt-2">
          <CredibilityBar score={source.credibility_score} />
          <p className="text-xs text-text-muted mt-1">Credibility: {source.credibility_score.toFixed(1)} / 100</p>
        </div>
        {source.health_error && (
          <p className="mt-2 text-xs text-yellow-400 bg-yellow-400/10 border border-yellow-400/20 rounded px-2 py-1.5 break-all">
            {source.health_error}
          </p>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-anveshak-border" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={detailTab === t.key}
            onClick={() => setDetailTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none ${
              detailTab === t.key
                ? 'text-anveshak-accent border-b-2 border-anveshak-accent'
                : 'text-text-muted hover:text-text-primary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div role="tabpanel">
        {detailTab === 'overview' && (
          <div className="space-y-6">
            {/* ── Edit name / URL */}
            <form onSubmit={handleFieldsSave} className="space-y-3" aria-label="Edit source details">
              <p className="text-sm font-medium text-text-secondary">Edit source</p>
              <div>
                <label htmlFor="edit-name" className="block text-xs text-text-muted mb-1">Name</label>
                <input
                  id="edit-name"
                  type="text"
                  value={editName}
                  onChange={(e) => { setEditName(e.target.value); setEditDirty(true) }}
                  className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-anveshak-accent"
                />
              </div>
              <div>
                <label htmlFor="edit-url" className="block text-xs text-text-muted mb-1">URL / Handle</label>
                <input
                  id="edit-url"
                  type="text"
                  value={editUrl}
                  onChange={(e) => { setEditUrl(e.target.value); setEditDirty(true) }}
                  className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-anveshak-accent"
                />
              </div>
              <Button
                type="submit"
                variant="secondary"
                size="sm"
                loading={updateFields.isPending}
                disabled={!editDirty || !editName.trim() || !editUrl.trim()}
              >
                Save changes
              </Button>
            </form>

            <hr className="border-anveshak-border" />

            {/* ── Update credibility */}
            <form onSubmit={handleCredUpdate} className="space-y-3" aria-label="Update credibility score">
              <p className="text-sm font-medium text-text-secondary">Update credibility score</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="new-score" className="block text-xs text-text-muted mb-1">New score (0–100)</label>
                  <input
                    id="new-score"
                    type="number"
                    min={0}
                    max={100}
                    value={newScore}
                    onChange={(e) => setNewScore(e.target.value)}
                    placeholder={source.credibility_score.toFixed(0)}
                    className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-anveshak-accent"
                  />
                </div>
                <div>
                  <label htmlFor="reason" className="block text-xs text-text-muted mb-1">Reason</label>
                  <input
                    id="reason"
                    type="text"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="e.g. Amplified deepfake"
                    className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-anveshak-accent"
                  />
                </div>
              </div>
              <Button
                type="submit"
                variant="secondary"
                size="sm"
                loading={updateCred.isPending}
                disabled={!newScore || !reason.trim()}
              >
                Update credibility
              </Button>
              <p className="text-[10px] text-text-muted">Every change is audit-logged and immutable (CLAUDE.md rule 8).</p>
            </form>

            <hr className="border-anveshak-border" />

            {/* ── Re-check health */}
            <div className="space-y-2">
              <p className="text-sm font-medium text-text-secondary">Health check</p>
              <div className="flex items-center gap-3">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => recheck.mutate()}
                  disabled={recheck.isPending}
                  aria-label={`Re-check ${source.name}`}
                >
                  {recheck.isPending ? <Spinner size="sm" /> : 'Re-check now'}
                </Button>
                {source.last_checked_at && (
                  <span className="text-xs text-text-muted">
                    Last: {formatDistanceToNow(new Date(source.last_checked_at), { addSuffix: true })}
                  </span>
                )}
              </div>
              {recheckError && <p className="text-xs text-signal-high">{recheckError}</p>}
            </div>

            <hr className="border-anveshak-border" />

            {/* ── Delete */}
            <div className="space-y-2">
              <p className="text-sm font-medium text-text-secondary">Danger zone</p>
              {deleteMode ? (
                <DeleteConfirm
                  sourceName={source.name}
                  contentCount={contentCount}
                  onConfirm={handleDeleteConfirm}
                  onCancel={() => { setDeleteMode(false); setContentCount(null) }}
                  isPending={deleteSrc.isPending}
                />
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleDeleteClick}
                  className="border border-signal-high/30 text-signal-high hover:bg-signal-high/10"
                  aria-label={`Delete source ${source.name}`}
                >
                  Delete source
                </Button>
              )}
            </div>
          </div>
        )}

        {detailTab === 'audit' && (
          <div>
            {isLoadingAudit ? (
              <div className="flex justify-center py-8"><Spinner size="sm" label="Loading audit log…" /></div>
            ) : (
              <AuditLogTable entries={auditLog} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Health overview charts ──────────────────────────────────────────────────

const HEALTH_COLORS: Record<string, string> = {
  healthy: '#10b981',    // --cred-high
  degraded: '#f59e0b',   // amber
  down: '#ef4444',       // --signal-high
  unverified: '#6b7280', // --text-muted
}

const PLATFORM_BAR_COLOR = '#3b82f6' // blue accent

function SmallChartTooltip({ active, payload, label }: {
  active?: boolean; payload?: { name?: string; value?: number }[]; label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-[#0f172a] border border-[#334155] rounded px-3 py-2 text-xs">
      <p className="text-text-primary font-medium">{label || payload[0]?.name}</p>
      <p className="text-text-muted">{payload[0]?.value}</p>
    </div>
  )
}

function SourceHealthOverview({ sources }: { sources: Source[] }) {
  const [collapsed, setCollapsed] = useState(false)

  const healthDistribution = useMemo(() => {
    const counts: Record<string, number> = {}
    sources.forEach((s) => {
      counts[s.health_status] = (counts[s.health_status] ?? 0) + 1
    })
    return Object.entries(counts).map(([status, count]) => ({
      name: status.charAt(0).toUpperCase() + status.slice(1),
      value: count,
      color: HEALTH_COLORS[status] ?? '#6b7280',
    }))
  }, [sources])

  const platformDistribution = useMemo(() => {
    const counts: Record<string, number> = {}
    sources.forEach((s) => {
      counts[s.platform] = (counts[s.platform] ?? 0) + 1
    })
    return Object.entries(counts)
      .map(([platform, count]) => ({ name: platform, count }))
      .sort((a, b) => b.count - a.count)
  }, [sources])

  if (sources.length === 0) return null

  return (
    <div className="border-b border-anveshak-border">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-2 text-xs font-medium text-text-muted uppercase tracking-wide hover:text-text-secondary transition-colors"
      >
        <span>Health Overview ({sources.length} sources)</span>
        <svg
          className={`w-4 h-4 transition-transform ${collapsed ? '' : 'rotate-180'}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {!collapsed && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 px-4 pb-3">
          {/* Health donut */}
          <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-3">
            <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">
              Health Distribution
            </h3>
            <div className="h-36">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={healthDistribution}
                    cx="50%"
                    cy="50%"
                    innerRadius={35}
                    outerRadius={55}
                    paddingAngle={2}
                    dataKey="value"
                    nameKey="name"
                  >
                    {healthDistribution.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip content={<SmallChartTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap gap-2 mt-1 justify-center">
              {healthDistribution.map((entry) => (
                <div key={entry.name} className="flex items-center gap-1 text-[10px] text-text-muted">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: entry.color }} />
                  {entry.name} ({entry.value})
                </div>
              ))}
            </div>
          </div>

          {/* Platform bar chart */}
          <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-3">
            <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">
              Sources by Platform
            </h3>
            <div className="h-36">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={platformDistribution} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} width={65} />
                  <Tooltip content={<SmallChartTooltip />} />
                  <Bar dataKey="count" fill={PLATFORM_BAR_COLOR} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function SourceManager({ embedded = false }: { embedded?: boolean }) {
  const [showModal, setShowModal]     = useState(false)
  const [selectedId, setSelectedId]   = useState<string | null>(null)
  const [detailTab, setDetailTab]     = useState<DetailTab>('overview')
  const [filter, setFilter]           = useState<FilterValue>('all')
  const qc = useQueryClient()

  const [sourcePage, setSourcePage] = useState(0)
  const SOURCE_PAGE_SIZE = 50

  const { data: sourcesData, isLoading } = useQuery({
    queryKey: ['sources', sourcePage, SOURCE_PAGE_SIZE],
    queryFn: () => sourcesApi.list(sourcePage * SOURCE_PAGE_SIZE, SOURCE_PAGE_SIZE),
    refetchInterval: 60_000,
  })
  const sources = sourcesData?.items ?? []
  const sourcesTotal = sourcesData?.total ?? 0

  // Warning counts for all sources
  const warningCountResults = useQueries({
    queries: sources.map((s) => ({
      queryKey: ['source-warning-count', s.id],
      queryFn: () => sourcesApi.getReportWarningsCount(s.id),
      staleTime: 60_000,
    })),
  })
  const warningCounts: Record<string, number> = {}
  sources.forEach((s, i) => {
    warningCounts[s.id] = warningCountResults[i]?.data?.warning_count ?? 0
  })

  // Health counts for filter bar
  const healthCounts = sources.reduce(
    (acc, s) => { acc[s.health_status] = (acc[s.health_status] ?? 0) + 1; return acc },
    {} as Record<HealthStatus, number>,
  )

  // Sort: down → degraded → unverified → healthy
  const ORDER: Record<HealthStatus, number> = { down: 0, degraded: 1, unverified: 2, healthy: 3 }
  const filtered = sources
    .filter((s) => filter === 'all' || s.health_status === filter)
    .sort((a, b) => (ORDER[a.health_status] ?? 4) - (ORDER[b.health_status] ?? 4))

  const selectedSource = sources.find((s) => s.id === selectedId)

  // When selected source is deleted it disappears from sources → deselect
  if (selectedId && !selectedSource) {
    setSelectedId(null)
  }

  const { data: auditLog = [], isFetching: isLoadingAudit } = useQuery({
    queryKey: ['audit', selectedId],
    queryFn: () => sourcesApi.getAuditLog(selectedId!),
    enabled: !!selectedId && detailTab === 'audit',
  })

  const addSource = useMutation({
    mutationFn: (p: CreateSourcePayload) => sourcesApi.create(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })

  return (
    <div className={embedded ? 'h-full flex flex-col' : 'h-full flex flex-col'}>
      {/* Header */}
      {!embedded && (
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border space-y-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-text-primary">Sources</h1>
            <p className="text-sm text-text-muted mt-0.5">Credibility scoring, health monitoring, and audit trail</p>
          </div>
          <Button onClick={() => setShowModal(true)} aria-label="Add new source">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
              <path d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" />
            </svg>
            Add source
          </Button>
        </div>
        <FilterBar active={filter} onChange={setFilter} counts={healthCounts} />
      </div>
      )}
      {embedded && (
      <div className="px-4 pt-3 pb-3 border-b border-anveshak-border space-y-3">
        <div className="flex items-center justify-between gap-4">
          <FilterBar active={filter} onChange={setFilter} counts={healthCounts} />
          <Button size="sm" onClick={() => setShowModal(true)} aria-label="Add new source">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
              <path d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" />
            </svg>
            Add source
          </Button>
        </div>
      </div>
      )}

      {/* Health overview charts */}
      <SourceHealthOverview sources={sources} />

      <div className="flex-1 flex overflow-hidden">
        {/* Source list */}
        <div className="w-80 shrink-0 border-r border-anveshak-border overflow-y-auto p-3 space-y-2">
          {isLoading ? (
            <div className="flex justify-center py-10"><Spinner label="Loading sources…" /></div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon="📡"
              title={filter === 'all' ? 'No sources yet' : `No ${filter} sources`}
              action={filter === 'all' ? <Button size="sm" onClick={() => setShowModal(true)}>Add first source</Button> : undefined}
            />
          ) : (
            filtered.map((source) => (
              <SourceRow
                key={source.id}
                source={source}
                onSelect={(id) => { setSelectedId(id); setDetailTab('overview') }}
                isSelected={selectedId === source.id}
                warningCount={warningCounts[source.id] ?? 0}
              />
            ))
          )}
          <div className="px-3 pb-3">
            <Pagination page={sourcePage} pageSize={SOURCE_PAGE_SIZE} total={sourcesTotal} onPageChange={setSourcePage} />
          </div>
        </div>

        {/* Detail panel */}
        <div className="flex-1 overflow-y-auto">
          {selectedSource ? (
            <DetailPanel
              key={selectedSource.id}
              source={selectedSource}
              warningCount={warningCounts[selectedSource.id] ?? 0}
              auditLog={auditLog}
              isLoadingAudit={isLoadingAudit}
              detailTab={detailTab}
              setDetailTab={setDetailTab}
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <EmptyState icon="📡" title="Select a source" description="Choose a source from the list to view details, edit, or manage health." />
            </div>
          )}
        </div>
      </div>

      <AddSourceModal
        open={showModal}
        onClose={() => setShowModal(false)}
        onSubmit={(p) => addSource.mutateAsync(p).then(() => undefined)}
      />
    </div>
  )
}
