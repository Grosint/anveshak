import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { signalsApi, Signal, SignalStatus } from '../api/signals'
import { useWS } from '../contexts/WSContext'
import { SignalCard } from '../components/signals/SignalCard'
import { SignalTimeline } from '../components/signals/SignalTimeline'
import { SignalGraph } from '../components/signals/SignalGraph'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { resolveTimeRange, type TimePreset } from '../lib/domain'
type ViewMode = 'list' | 'timeline'

const TABS: { key: SignalStatus; label: string }[] = [
  { key: 'new',          label: 'New' },
  { key: 'acknowledged', label: 'Acknowledged' },
  { key: 'dismissed',    label: 'Dismissed' },
]

const TIME_PRESETS: { key: TimePreset; label: string }[] = [
  { key: 'today', label: 'Today' },
  { key: '7d',    label: 'Last 7 days' },
  { key: '30d',   label: 'Last 30 days' },
  { key: 'custom', label: 'Custom' },
]

// ── Helpers ──────────────────────────────────────────────────────────────

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10)
}

// ── Component ────────────────────────────────────────────────────────────

export default function SignalsInbox() {
  const [activeTab, setActiveTab]     = useState<SignalStatus>('new')
  const [newCount, setNewCount]       = useState(0)
  const [preset, setPreset]           = useState<TimePreset>('7d')
  const [customFrom, setCustomFrom]   = useState('')
  const [customTo, setCustomTo]       = useState(() => toISODate(new Date()))
  const [viewMode, setViewMode]       = useState<ViewMode>('timeline')
  const [graphSignalId, setGraphSignalId] = useState<string | null>(null)

  const qc = useQueryClient()
  const { subscribe } = useWS()

  const { since, until } = useMemo(
    () => resolveTimeRange(preset, customFrom, customTo),
    [preset, customFrom, customTo],
  )

  const rangeReady = preset !== 'custom' || (customFrom !== '' && customTo !== '')

  const { data: signals = [], isLoading } = useQuery({
    queryKey: ['signals', activeTab, since, until],
    queryFn: () => (rangeReady ? signalsApi.list(activeTab, since, until) : Promise.resolve([])),
    refetchInterval: 30_000,
    enabled: rangeReady,
  })

  // Real-time: WS push → invalidate
  useEffect(() => {
    return subscribe((msg) => {
      if (msg.type === 'signal' || msg.type === 'signal_replay') {
        qc.invalidateQueries({ queryKey: ['signals'] })
        if (activeTab !== 'new') setNewCount((n) => n + 1)
      }
    })
  }, [subscribe, qc, activeTab])

  useEffect(() => {
    if (activeTab === 'new') setNewCount(0)
  }, [activeTab])

  // Optimistic acknowledge
  const acknowledge = useMutation({
    mutationFn: signalsApi.acknowledge,
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['signals', 'new'] })
      const prev = qc.getQueryData<Signal[]>(['signals', 'new', since, until])
      qc.setQueryData<Signal[]>(['signals', 'new', since, until], (old = []) =>
        old.filter((s) => s.id !== id),
      )
      return { prev }
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(['signals', 'new', since, until], ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['signals'] }),
  })

  // Optimistic dismiss
  const dismiss = useMutation({
    mutationFn: signalsApi.dismiss,
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['signals', activeTab] })
      const prev = qc.getQueryData<Signal[]>(['signals', activeTab, since, until])
      qc.setQueryData<Signal[]>(['signals', activeTab, since, until], (old = []) =>
        old.filter((s) => s.id !== id),
      )
      return { prev }
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(['signals', activeTab, since, until], ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['signals'] }),
  })

  const isActioning = acknowledge.isPending || dismiss.isPending

  return (
    <div className="h-full flex flex-col">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Signals Intelligence</h1>
          <p className="text-sm text-text-muted mt-0.5">
            Threshold-based intelligence alerts — real-time via WebSocket
          </p>
        </div>

        {/* View toggle */}
        <div className="flex items-center bg-anveshak-muted rounded-lg p-0.5">
          {(['list', 'timeline'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                viewMode === mode
                  ? 'bg-anveshak-card text-text-primary shadow-sm'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              {mode === 'list' ? 'List' : 'Timeline'}
            </button>
          ))}
        </div>
      </div>

      {/* ── Status tabs ────────────────────────────────────────────────────── */}
      <div className="flex border-b border-anveshak-border px-6" role="tablist" aria-label="Signal status tabs">
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
            {tab.key === 'new' && newCount > 0 && (
              <span
                aria-label={`${newCount} new signals`}
                className="absolute -top-0.5 -right-1 bg-signal-high text-white text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center"
              >
                {newCount > 9 ? '9+' : newCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Time filter bar ────────────────────────────────────────────────── */}
      <div className="px-6 py-3 border-b border-anveshak-border bg-anveshak-bg/40">
        <div className="flex flex-wrap items-center gap-2">
          {TIME_PRESETS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPreset(p.key)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                preset === p.key
                  ? 'bg-anveshak-accent text-white'
                  : 'bg-anveshak-muted text-text-secondary hover:bg-anveshak-card hover:text-text-primary'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {preset === 'custom' && (
          <div className="flex flex-wrap items-center gap-3 mt-2.5">
            <label className="flex items-center gap-1.5 text-xs text-text-muted">
              From
              <input
                type="date"
                value={customFrom}
                max={customTo || toISODate(new Date())}
                onChange={(e) => setCustomFrom(e.target.value)}
                className="ml-1 px-2 py-1 rounded bg-anveshak-card border border-anveshak-border text-text-primary text-xs focus:outline-none focus:border-anveshak-accent"
              />
            </label>
            <label className="flex items-center gap-1.5 text-xs text-text-muted">
              To
              <input
                type="date"
                value={customTo}
                min={customFrom || undefined}
                max={toISODate(new Date())}
                onChange={(e) => setCustomTo(e.target.value)}
                className="ml-1 px-2 py-1 rounded bg-anveshak-card border border-anveshak-border text-text-primary text-xs focus:outline-none focus:border-anveshak-accent"
              />
            </label>
            {!rangeReady && (
              <span className="text-xs text-text-muted italic">Select a start date to apply filter</span>
            )}
          </div>
        )}
      </div>

      {/* ── Content ────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-6" role="tabpanel">
        {isLoading ? (
          <div className="flex justify-center py-20">
            <Spinner label="Loading signals…" />
          </div>
        ) : signals.length === 0 ? (
          <EmptyState
            icon="⚡"
            title={activeTab === 'new' ? 'No new signals' : `No ${activeTab} signals`}
            description={
              activeTab === 'new'
                ? 'Signals fire when a cluster reaches your source threshold.'
                : undefined
            }
          />
        ) : viewMode === 'timeline' ? (
          <SignalTimeline
            signals={signals}
            onAcknowledge={(id) => acknowledge.mutate(id)}
            onDismiss={(id) => dismiss.mutate(id)}
            isActioning={isActioning}
            onShowGraph={setGraphSignalId}
          />
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {signals.map((signal) => (
              <SignalCard
                key={signal.id}
                signal={signal}
                onAcknowledge={(id) => acknowledge.mutate(id)}
                onDismiss={(id) => dismiss.mutate(id)}
                isActioning={isActioning}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Graph modal ───────────────────────────────────────────────────── */}
      {graphSignalId && (
        <SignalGraph
          signalId={graphSignalId}
          onClose={() => setGraphSignalId(null)}
        />
      )}
    </div>
  )
}
