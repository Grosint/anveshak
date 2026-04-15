import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { signalsApi, Signal, SignalStatus } from '../api/signals'
import { useWS } from '../contexts/WSContext'
import { SignalCard } from '../components/signals/SignalCard'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'

const TABS: { key: SignalStatus; label: string }[] = [
  { key: 'new',          label: 'New' },
  { key: 'acknowledged', label: 'Acknowledged' },
  { key: 'dismissed',    label: 'Dismissed' },
]

export default function SignalsInbox() {
  const [activeTab, setActiveTab] = useState<SignalStatus>('new')
  const [newCount, setNewCount]   = useState(0)
  const qc = useQueryClient()
  const { subscribe } = useWS()

  const { data: signals = [], isLoading } = useQuery({
    queryKey: ['signals', activeTab],
    queryFn: () => signalsApi.list(activeTab),
    refetchInterval: 30_000,
  })

  // Real-time: WS push → invalidate 'new' tab + badge counter
  useEffect(() => {
    return subscribe((msg) => {
      if (msg.type === 'signal' || msg.type === 'signal_replay') {
        qc.invalidateQueries({ queryKey: ['signals', 'new'] })
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
      const prev = qc.getQueryData<Signal[]>(['signals', 'new'])
      qc.setQueryData<Signal[]>(['signals', 'new'], (old = []) => old.filter((s) => s.id !== id))
      return { prev }
    },
    onError: (_e, _id, ctx) => { if (ctx?.prev) qc.setQueryData(['signals', 'new'], ctx.prev) },
    onSettled: () => qc.invalidateQueries({ queryKey: ['signals'] }),
  })

  // Optimistic dismiss
  const dismiss = useMutation({
    mutationFn: signalsApi.dismiss,
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['signals', activeTab] })
      const prev = qc.getQueryData<Signal[]>(['signals', activeTab])
      qc.setQueryData<Signal[]>(['signals', activeTab], (old = []) => old.filter((s) => s.id !== id))
      return { prev }
    },
    onError: (_e, _id, ctx) => { if (ctx?.prev) qc.setQueryData(['signals', activeTab], ctx.prev) },
    onSettled: () => qc.invalidateQueries({ queryKey: ['signals'] }),
  })

  const isActioning = acknowledge.isPending || dismiss.isPending

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border">
        <h1 className="text-xl font-semibold text-text-primary">Signals Inbox</h1>
        <p className="text-sm text-text-muted mt-0.5">Threshold-based intelligence alerts — real-time via WebSocket</p>
      </div>

      {/* Tabs */}
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

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6" role="tabpanel">
        {isLoading ? (
          <div className="flex justify-center py-20"><Spinner label="Loading signals…" /></div>
        ) : signals.length === 0 ? (
          <EmptyState
            icon="⚡"
            title={activeTab === 'new' ? 'No new signals' : `No ${activeTab} signals`}
            description={activeTab === 'new' ? 'Signals fire when a cluster reaches your source threshold.' : undefined}
          />
        ) : (
          <div className="max-w-2xl space-y-3">
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
