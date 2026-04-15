import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sourcesApi, Source, CreateSourcePayload } from '../api/sources'
import { useQueries } from '@tanstack/react-query'
import { AddSourceModal } from '../components/sources/AddSourceModal'
import { AuditLogTable } from '../components/sources/AuditLogTable'
import { PlatformBadge } from '../components/content/PlatformBadge'
import { CredibilityBadge } from '../components/content/CredibilityBadge'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { formatDistanceToNow } from 'date-fns'

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

interface SourceRowProps {
  source: Source
  onSelect: (id: string) => void
  isSelected: boolean
  warningCount: number
}

function SourceRow({ source, onSelect, isSelected, warningCount }: SourceRowProps) {
  return (
    <div
      className={`bg-anveshak-card border rounded-lg p-4 cursor-pointer hover:border-anveshak-accent/40 transition-all ${
        isSelected ? 'border-anveshak-accent' : 'border-anveshak-border'
      }`}
      onClick={() => onSelect(source.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onSelect(source.id)}
      aria-label={`View source: ${source.name}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <PlatformBadge platform={source.platform} />
            <span className={`w-2 h-2 rounded-full shrink-0 ${source.is_active ? 'bg-cred-high' : 'bg-text-muted'}`}
              title={source.is_active ? 'Active' : 'Inactive'} aria-label={source.is_active ? 'Active' : 'Inactive'} />
            {warningCount > 0 && (
              <span
                className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-signal-high/20 text-signal-high"
                title={`${warningCount} report warning(s)`}
                aria-label={`${warningCount} report warnings`}
              >
                ⚠ {warningCount}
              </span>
            )}
          </div>
          <p className="font-medium text-text-primary text-sm truncate">{source.name}</p>
          {source.last_checked_at && (
            <p className="text-xs text-text-muted mt-1">
              Last checked {formatDistanceToNow(new Date(source.last_checked_at), { addSuffix: true })}
            </p>
          )}
        </div>
        <div className="text-right shrink-0">
          <CredibilityBadge score={source.credibility_score} />
        </div>
      </div>
      <CredibilityBar score={source.credibility_score} />
    </div>
  )
}

type DetailTab = 'overview' | 'audit'

export default function SourceManager() {
  const [showModal, setShowModal]     = useState(false)
  const [selectedId, setSelectedId]   = useState<string | null>(null)
  const [detailTab, setDetailTab]     = useState<DetailTab>('overview')
  const [newScore, setNewScore]       = useState('')
  const [reason, setReason]           = useState('')
  const qc = useQueryClient()

  const { data: sources = [], isLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: sourcesApi.list,
  })

  // Fetch report warning counts for all sources (criteria 6.37)
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

  const selectedSource = sources.find((s) => s.id === selectedId)

  const { data: auditLog = [], isFetching: isLoadingAudit } = useQuery({
    queryKey: ['audit', selectedId],
    queryFn: () => sourcesApi.getAuditLog(selectedId!),
    enabled: !!selectedId && detailTab === 'audit',
  })

  const addSource = useMutation({
    mutationFn: (p: CreateSourcePayload) => sourcesApi.create(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })

  const updateCred = useMutation({
    mutationFn: ({ id, score, reason }: { id: string; score: number; reason: string }) =>
      sourcesApi.updateCredibility(id, score, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sources'] })
      qc.invalidateQueries({ queryKey: ['audit', selectedId] })
      setNewScore('')
      setReason('')
    },
  })

  async function handleCredUpdate(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedId || !newScore || !reason.trim()) return
    await updateCred.mutateAsync({ id: selectedId, score: Number(newScore), reason: reason.trim() })
  }

  const DETAIL_TABS: { key: DetailTab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'audit',    label: 'Audit log' },
  ]

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Source Manager</h1>
          <p className="text-sm text-text-muted mt-0.5">Credibility scoring and audit trail</p>
        </div>
        <Button onClick={() => setShowModal(true)} aria-label="Add new source">
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
            <path d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" />
          </svg>
          Add source
        </Button>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* ── Source list ─────────────────────────────────────────────────── */}
        <div className="w-80 shrink-0 border-r border-anveshak-border overflow-y-auto p-4 space-y-2">
          {isLoading ? (
            <div className="flex justify-center py-10"><Spinner label="Loading sources…" /></div>
          ) : sources.length === 0 ? (
            <EmptyState
              icon="📡"
              title="No sources yet"
              action={<Button size="sm" onClick={() => setShowModal(true)}>Add first source</Button>}
            />
          ) : (
            sources.map((source) => (
              <SourceRow
                key={source.id}
                source={source}
                onSelect={(id) => { setSelectedId(id); setDetailTab('overview') }}
                isSelected={selectedId === source.id}
                warningCount={warningCounts[source.id] ?? 0}
              />
            ))
          )}
        </div>

        {/* ── Detail panel ────────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto">
          {selectedSource ? (
            <div className="p-6 space-y-4">
              {/* Source title */}
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <PlatformBadge platform={selectedSource.platform} />
                  <h2 className="text-lg font-semibold text-text-primary">{selectedSource.name}</h2>
                </div>
                <CredibilityBar score={selectedSource.credibility_score} />
                <p className="text-xs text-text-muted mt-1">
                  Credibility: {selectedSource.credibility_score.toFixed(1)} / 100
                </p>
              </div>

              {/* Detail tabs */}
              <div className="flex border-b border-anveshak-border" role="tablist">
                {DETAIL_TABS.map((t) => (
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
                          placeholder={selectedSource.credibility_score.toFixed(0)}
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
                    <p className="text-[10px] text-text-muted">
                      Every change is audit-logged and immutable (CLAUDE.md rule 8).
                    </p>
                  </form>
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
          ) : (
            <div className="flex items-center justify-center h-full">
              <EmptyState icon="📡" title="Select a source" description="Choose a source from the list to view details and audit history." />
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
