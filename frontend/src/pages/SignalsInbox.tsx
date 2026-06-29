import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { signalsApi, Signal, SignalStatus } from '../api/signals'
import { topicsApi } from '../api/topics'
import { useWS } from '../contexts/WSContext'
import { SignalCard } from '../components/signals/SignalCard'
import { SignalTimeline } from '../components/signals/SignalTimeline'
import { SignalGraph } from '../components/signals/SignalGraph'
import { CalendarStrip } from '../components/signals/CalendarStrip'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { resolveTimeRange, type TimePreset } from '../lib/domain'
type ViewMode = 'list' | 'timeline'

const TABS: { key: SignalStatus; label: string }[] = [
  { key: 'new',          label: 'New' },
  { key: 'acknowledged', label: 'Acknowledged' },
  { key: 'dismissed',    label: 'Dismissed' },
]

const RANGE_PRESETS: { key: TimePreset; label: string; days: number }[] = [
  { key: '7d',  label: '7 days',  days: 7  },
  { key: '14d', label: '14 days', days: 14 },
  { key: '30d', label: '30 days', days: 30 },
]

// ── Component ────────────────────────────────────────────────────────────

export default function SignalsInbox() {
  const [activeTab, setActiveTab]     = useState<SignalStatus>('new')
  const [newCount, setNewCount]       = useState(0)
  const [preset, setPreset]           = useState<TimePreset>('7d')
  const [selectedDay, setSelectedDay] = useState<string | null>(null)
  const [viewMode, setViewMode]       = useState<ViewMode>('timeline')
  const [graphSignalId, setGraphSignalId] = useState<string | null>(null)
  const [activeTopicsOnly, setActiveTopicsOnly] = useState(true)

  // Calendar strip window size (days)
  const windowDays = useMemo(() => {
    const found = RANGE_PRESETS.find((p) => p.key === preset)
    return found?.days ?? 7
  }, [preset])

  const qc = useQueryClient()
  const { subscribe } = useWS()

  // Fetch topics to build status map for filtering signals by topic status
  const { data: topics = [] } = useQuery({
    queryKey: ['topics'],
    queryFn: topicsApi.list,
    staleTime: 60_000,
  })

  const topicStatusMap = useMemo(
    () => Object.fromEntries(topics.map((t) => [t.id, t.status])),
    [topics],
  )

  // Time range: day selected → single day, otherwise range preset
  const { since, until } = useMemo(
    () => selectedDay
      ? resolveTimeRange('day', selectedDay, '')
      : resolveTimeRange(preset, '', ''),
    [selectedDay, preset],
  )

  // Daily counts for the full range (calendar strip — no LIMIT, lightweight)
  const { since: rangeSince, until: rangeUntil } = useMemo(
    () => resolveTimeRange(preset, '', ''),
    [preset],
  )

  const { data: dailyCounts = [] } = useQuery({
    queryKey: ['signal-daily-counts', activeTab, rangeSince, rangeUntil],
    queryFn: () => signalsApi.dailyCounts(activeTab, rangeSince, rangeUntil),
    refetchInterval: 60_000,
  })

  const { data: signals = [], isLoading } = useQuery({
    queryKey: ['signals', activeTab, since, until],
    queryFn: () => signalsApi.list(activeTab, since, until),
    refetchInterval: 30_000,
  })

  // Real-time: WS push → invalidate
  useEffect(() => {
    return subscribe((msg) => {
      if (msg.type === 'signal' || msg.type === 'signal_replay') {
        qc.invalidateQueries({ queryKey: ['signals'] })
        qc.invalidateQueries({ queryKey: ['signal-daily-counts'] })
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

  const filteredSignals = useMemo(
    () => activeTopicsOnly
      ? signals.filter((s) => topicStatusMap[s.topic_id] === 'active')
      : signals,
    [signals, activeTopicsOnly, topicStatusMap],
  )

  const hiddenCount = signals.length - filteredSignals.length

  const isActioning = acknowledge.isPending || dismiss.isPending

  // Total signal count from daily-counts (true count, no LIMIT)
  const totalSignalCount = useMemo(
    () => dailyCounts.reduce((sum, dc) => sum + dc.count, 0),
    [dailyCounts],
  )

  return (
    <div className="h-full flex flex-col">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">
            Signals Intelligence
            {totalSignalCount > 0 && (
              <span className="ml-2 text-sm font-normal text-text-muted">
                {totalSignalCount.toLocaleString()} {activeTab}
              </span>
            )}
          </h1>
          <p className="text-sm text-text-muted mt-0.5">
            Real-time intelligence alerts from monitored sources
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
      <div className="px-6 py-3 border-b border-anveshak-border bg-anveshak-bg/40 space-y-2">
        {/* Range chips + active topics toggle */}
        <div className="flex flex-wrap items-center gap-2">
          {RANGE_PRESETS.map((p) => (
            <button
              key={p.key}
              onClick={() => {
                setPreset(p.key)
                setSelectedDay(null) // clear day selection when range changes
              }}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                preset === p.key
                  ? 'bg-anveshak-accent text-white'
                  : 'bg-anveshak-muted text-text-secondary hover:bg-anveshak-card hover:text-text-primary'
              }`}
            >
              {p.label}
            </button>
          ))}

          {selectedDay && (
            <span className="text-xs text-anveshak-accent font-medium ml-1">
              → {selectedDay}
            </span>
          )}

          <span className="mx-1 text-anveshak-border">|</span>

          <button
            onClick={() => setActiveTopicsOnly((v) => !v)}
            aria-pressed={activeTopicsOnly}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              activeTopicsOnly
                ? 'bg-cred-high/20 text-cred-high border border-cred-high/30'
                : 'bg-anveshak-muted text-text-secondary hover:bg-anveshak-card hover:text-text-primary'
            }`}
          >
            Active topics only
            {hiddenCount > 0 && !activeTopicsOnly && (
              <span className="ml-1 text-text-muted">({hiddenCount} from paused)</span>
            )}
          </button>
        </div>

        {/* Calendar strip */}
        <CalendarStrip
          dailyCounts={dailyCounts}
          windowDays={windowDays}
          selectedDay={selectedDay}
          onSelectDay={setSelectedDay}
        />
      </div>

      {/* ── Content ────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-6" role="tabpanel">
        {isLoading ? (
          <div className="flex justify-center py-20">
            <Spinner label="Loading signals…" />
          </div>
        ) : filteredSignals.length === 0 ? (
          <EmptyState
            icon="⚡"
            title={activeTab === 'new' ? 'No new signals' : `No ${activeTab} signals`}
            description={
              activeTopicsOnly && signals.length > 0
                ? `${signals.length} signal${signals.length > 1 ? 's' : ''} from paused topics hidden. Toggle "Active topics only" to see all.`
                : activeTab === 'new'
                  ? 'Signals fire when a cluster reaches your source threshold.'
                  : undefined
            }
          />
        ) : viewMode === 'timeline' ? (
          <SignalTimeline
            signals={filteredSignals}
            onAcknowledge={(id) => acknowledge.mutate(id)}
            onDismiss={(id) => dismiss.mutate(id)}
            isActioning={isActioning}
            onShowGraph={setGraphSignalId}
          />
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {filteredSignals.map((signal) => (
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
