import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { signalsApi, Signal, SignalStatus } from '../api/signals'
import { useWS } from '../contexts/WSContext'
import { SignalCard } from '../components/signals/SignalCard'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'

// ── Types ────────────────────────────────────────────────────────────────────

type TimePreset = 'today' | '7d' | '30d' | 'custom'

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

// ── Helpers ──────────────────────────────────────────────────────────────────

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10)
}

/** Compute [since, until] ISO strings from the current preset + custom inputs. */
function resolveRange(
  preset: TimePreset,
  customFrom: string,
  customTo: string,
): { since: string; until: string } {
  const now = new Date()
  const until = now.toISOString()

  if (preset === 'today') {
    const startOfDay = new Date(now)
    startOfDay.setUTCHours(0, 0, 0, 0)
    return { since: startOfDay.toISOString(), until }
  }
  if (preset === '7d') {
    const d = new Date(now)
    d.setUTCDate(d.getUTCDate() - 7)
    return { since: d.toISOString(), until }
  }
  if (preset === '30d') {
    const d = new Date(now)
    d.setUTCDate(d.getUTCDate() - 30)
    return { since: d.toISOString(), until }
  }
  // custom
  const since = customFrom ? new Date(customFrom + 'T00:00:00Z').toISOString() : ''
  const customUntil = customTo
    ? new Date(customTo + 'T23:59:59Z').toISOString()
    : until
  return { since, until: customUntil }
}

// ── Component ────────────────────────────────────────────────────────────────

export default function SignalsInbox() {
  const [activeTab, setActiveTab]     = useState<SignalStatus>('new')
  const [newCount, setNewCount]       = useState(0)
  const [preset, setPreset]           = useState<TimePreset>('today')
  const [customFrom, setCustomFrom]   = useState('')
  const [customTo, setCustomTo]       = useState(() => toISODate(new Date()))

  const qc = useQueryClient()
  const { subscribe } = useWS()

  const { since, until } = useMemo(
    () => resolveRange(preset, customFrom, customTo),
    [preset, customFrom, customTo],
  )

  // Custom preset is only "active" once both dates are filled
  const rangeReady = preset !== 'custom' || (customFrom !== '' && customTo !== '')

  const { data: signals = [], isLoading } = useQuery({
    queryKey: ['signals', activeTab, since, until],
    queryFn: () => (rangeReady ? signalsApi.list(activeTab, since, until) : Promise.resolve([])),
    refetchInterval: 30_000,
    enabled: rangeReady,
  })

  // Real-time: WS push → invalidate all signal cache keys + badge counter
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
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border">
        <h1 className="text-xl font-semibold text-text-primary">Signals Inbox</h1>
        <p className="text-sm text-text-muted mt-0.5">
          Threshold-based intelligence alerts — real-time via WebSocket
        </p>
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

        {/* Custom date pickers — visible only when Custom is active */}
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
    </div>
  )
}
