import { useState, useMemo } from 'react'
import { Signal } from '../../api/signals'
import { SignalCard } from './SignalCard'
import { Badge } from '../ui/Badge'
import { format } from 'date-fns'

// ── Constants ──────────────────────────────────────────────────────────

const DOTS_PER_ROW = 12
const DOT_SIZE = 14

const severityColor: Record<string, string> = {
  HIGH: 'var(--signal-high, #ef4444)',
  MEDIUM: 'var(--signal-med, #f59e0b)',
  LOW: 'var(--signal-low, #10b981)',
}

// ── Helpers ─────────────────────────────────────────────────────────────

function inferSeverity(signal: Signal): string {
  const isc = signal.independent_source_count ?? 0
  if (isc >= 3) return 'HIGH'
  if (isc >= 2) return 'MEDIUM'
  return 'HIGH'
}

interface TopicGroup {
  topic_id: string
  topic_name: string
  signals: Signal[]
}

function groupByTopic(signals: Signal[]): TopicGroup[] {
  const map = new Map<string, TopicGroup>()
  for (const s of signals) {
    const key = s.topic_id
    if (!map.has(key)) {
      map.set(key, {
        topic_id: key,
        topic_name: s.topic_name || 'Unknown Topic',
        signals: [],
      })
    }
    map.get(key)!.signals.push(s)
  }
  // Sort topics by signal count descending
  return Array.from(map.values()).sort((a, b) => b.signals.length - a.signals.length)
}

// ── Topic color palette (muted, military-aesthetic) ────────────────────

const TOPIC_COLORS = [
  '#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b',
  '#ec4899', '#6366f1', '#14b8a6', '#f97316', '#a855f7',
]

// ── Snake Row Component ────────────────────────────────────────────────

function SnakeRow({
  signals,
  rowIndex,
  totalRows,
  timeRange,
  topicColor,
  selectedId,
  onSelect,
}: {
  signals: Signal[]
  rowIndex: number
  totalRows: number
  timeRange: { min: number; max: number }
  topicColor: string
  selectedId: string | null
  onSelect: (id: string | null) => void
}) {
  const isReversed = rowIndex % 2 === 1
  const range = timeRange.max - timeRange.min || 1

  // Position dots along the row based on timestamp
  const positioned = signals.map((s) => {
    const ts = new Date(s.created_at).getTime()
    const pct = ((ts - timeRange.min) / range) * 100
    return { signal: s, pct: Math.max(2, Math.min(98, pct)) }
  })

  // Reverse positioning for odd rows (snake pattern)
  const dots = isReversed
    ? positioned.map((d) => ({ ...d, pct: 100 - d.pct }))
    : positioned

  // Compute time labels for this row's range segment
  const rowFraction = 1 / (totalRows || 1)
  const rowStartTime = timeRange.min + rowIndex * rowFraction * range
  const rowEndTime = timeRange.min + (rowIndex + 1) * rowFraction * range
  const leftTime = isReversed ? rowEndTime : rowStartTime
  const rightTime = isReversed ? rowStartTime : rowEndTime

  return (
    <div className="relative">
      {/* Time labels on the line */}
      <div className="flex items-center justify-between px-0.5 mb-0.5">
        <span className="text-[9px] text-text-muted font-mono">
          {format(new Date(leftTime), 'MMM d HH:mm')}
        </span>
        <span className="text-[9px] text-text-muted font-mono">
          {format(new Date(rightTime), 'MMM d HH:mm')}
        </span>
      </div>

      {/* Timeline line */}
      <div className="relative h-10 flex items-center">
        <div
          className="absolute inset-x-0 top-1/2 h-[2px] -translate-y-1/2 opacity-30"
          style={{ backgroundColor: topicColor }}
        />

        {/* Snake connector from previous row */}
        {rowIndex > 0 && (
          <div
            className="absolute h-8 w-[2px] opacity-20"
            style={{
              backgroundColor: topicColor,
              [isReversed ? 'right' : 'left']: 0,
              top: '-1.5rem',
            }}
          />
        )}

        {/* Signal dots */}
        {dots.map(({ signal, pct }) => {
          const severity = inferSeverity(signal)
          const isSelected = selectedId === signal.id
          return (
            <button
              key={signal.id}
              className="absolute -translate-x-1/2 -translate-y-1/2 top-1/2 z-10 group/dot"
              style={{ left: `${pct}%` }}
              onClick={(e) => {
                e.stopPropagation()
                onSelect(isSelected ? null : signal.id)
              }}
              aria-label={signal.cluster_label || signal.description}
            >
              {/* Pulse ring for new signals */}
              {signal.status === 'new' && (
                <span
                  className="absolute inset-0 rounded-full animate-ping opacity-30"
                  style={{
                    width: DOT_SIZE + 8,
                    height: DOT_SIZE + 8,
                    marginLeft: -(DOT_SIZE + 8) / 2 + DOT_SIZE / 2,
                    marginTop: -(DOT_SIZE + 8) / 2 + DOT_SIZE / 2,
                    backgroundColor: severityColor[severity],
                  }}
                />
              )}

              {/* Dot */}
              <span
                className="block rounded-full border-2 border-anveshak-bg transition-all duration-200"
                style={{
                  width: isSelected ? DOT_SIZE + 4 : DOT_SIZE,
                  height: isSelected ? DOT_SIZE + 4 : DOT_SIZE,
                  backgroundColor: severityColor[severity],
                  boxShadow: isSelected
                    ? `0 0 12px ${severityColor[severity]}80`
                    : `0 0 4px ${severityColor[severity]}40`,
                }}
              />

              {/* Hover tooltip */}
              <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 rounded bg-anveshak-card border border-anveshak-border text-[10px] text-text-primary whitespace-nowrap opacity-0 group-hover/dot:opacity-100 transition-opacity pointer-events-none z-20 shadow-lg">
                {signal.cluster_label || signal.signal_type}
                <br />
                <span className="text-text-muted">
                  {format(new Date(signal.created_at), 'MMM d, HH:mm')}
                </span>
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── Topic Lane Component ───────────────────────────────────────────────

function TopicLane({
  group,
  colorIndex,
  selectedId,
  onSelect,
  onAcknowledge,
  onDismiss,
  isActioning,
  onShowGraph,
}: {
  group: TopicGroup
  colorIndex: number
  selectedId: string | null
  onSelect: (id: string | null) => void
  onAcknowledge: (id: string) => void
  onDismiss: (id: string) => void
  isActioning: boolean
  onShowGraph: (id: string) => void
}) {
  const [collapsed, setCollapsed] = useState(false)
  const color = TOPIC_COLORS[colorIndex % TOPIC_COLORS.length]

  // Sort signals by time
  const sorted = useMemo(
    () => [...group.signals].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
    [group.signals],
  )

  // Global time range across all signals in this topic
  const timeRange = useMemo(() => {
    const times = sorted.map((s) => new Date(s.created_at).getTime())
    return { min: Math.min(...times), max: Math.max(...times) }
  }, [sorted])

  // Break into rows (snake segments)
  const rows: Signal[][] = []
  for (let i = 0; i < sorted.length; i += DOTS_PER_ROW) {
    rows.push(sorted.slice(i, i + DOTS_PER_ROW))
  }

  const selectedSignal = sorted.find((s) => s.id === selectedId) ?? null

  return (
    <div className="mb-4">
      {/* Topic header */}
      <button
        className="flex items-center gap-2 mb-1 px-1 w-full text-left group/lane"
        onClick={() => setCollapsed(!collapsed)}
      >
        <span
          className="w-3 h-3 rounded-sm shrink-0"
          style={{ backgroundColor: color }}
        />
        <span className="text-sm font-semibold text-text-primary group-hover/lane:text-white transition-colors truncate">
          {group.topic_name}
        </span>
        <Badge variant="ghost" className="text-[10px]">
          {group.signals.length}
        </Badge>
        <span className="text-text-muted text-xs ml-auto">
          {collapsed ? '▸' : '▾'}
        </span>
      </button>

      {/* Timeline rows (snake pattern) */}
      {!collapsed && (
        <div className="pl-5">
          {rows.map((rowSignals, idx) => (
            <SnakeRow
              key={idx}
              signals={rowSignals}
              rowIndex={idx}
              totalRows={rows.length}
              timeRange={timeRange}
              topicColor={color}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}

          {/* Expanded signal detail */}
          {selectedSignal && (
            <div className="mt-2 mb-3 animate-fade-in">
              <div className="flex items-center gap-2 mb-1">
                <button
                  className="text-[10px] text-anveshak-accent hover:underline"
                  onClick={() => onShowGraph(selectedSignal.id)}
                >
                  View Graph
                </button>
              </div>
              <SignalCard
                signal={selectedSignal}
                onAcknowledge={onAcknowledge}
                onDismiss={onDismiss}
                isActioning={isActioning}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main Timeline Component ────────────────────────────────────────────

interface SignalTimelineProps {
  signals: Signal[]
  onAcknowledge: (id: string) => void
  onDismiss: (id: string) => void
  isActioning: boolean
  onShowGraph: (id: string) => void
}

export function SignalTimeline({
  signals,
  onAcknowledge,
  onDismiss,
  isActioning,
  onShowGraph,
}: SignalTimelineProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const topicGroups = useMemo(() => groupByTopic(signals), [signals])

  if (signals.length === 0) return null

  // Time range labels
  const allTimes = signals.map((s) => new Date(s.created_at).getTime())
  const minTime = new Date(Math.min(...allTimes))
  const maxTime = new Date(Math.max(...allTimes))

  return (
    <div>
      {/* Global time range header */}
      <div className="flex items-center justify-between text-[10px] text-text-muted mb-3 px-1">
        <span>{format(minTime, 'MMM d, HH:mm')}</span>
        <div className="flex-1 mx-3 h-[1px] bg-anveshak-border" />
        <span>{format(maxTime, 'MMM d, HH:mm')}</span>
      </div>

      {/* Topic swim lanes */}
      {topicGroups.map((group, idx) => (
        <TopicLane
          key={group.topic_id}
          group={group}
          colorIndex={idx}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onAcknowledge={onAcknowledge}
          onDismiss={onDismiss}
          isActioning={isActioning}
          onShowGraph={onShowGraph}
        />
      ))}
    </div>
  )
}
