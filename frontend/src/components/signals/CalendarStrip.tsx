import { useState, useMemo, useRef, useEffect } from 'react'
import {
  format, subDays, isSameDay, startOfDay, startOfMonth, endOfMonth,
  addMonths, subMonths, eachDayOfInterval, getDay,
} from 'date-fns'

// ── Constants ──────────────────────────────────────────────────────────

const DAY_WIDTH = 56 // px per day cell in strip

// ── Types ──────────────────────────────────────────────────────────────

interface DailyCount {
  date: string // YYYY-MM-DD
  count: number
}

interface CalendarStripProps {
  /** Per-day signal counts from backend (not limited by LIMIT 500) */
  dailyCounts: DailyCount[]
  /** Number of days to show in the strip (matches range preset) */
  windowDays: number
  /** Currently selected day (YYYY-MM-DD) or null for no day filter */
  selectedDay: string | null
  /** Called when user clicks a day cell */
  onSelectDay: (day: string | null) => void
}

// ── Mini Month Calendar ────────────────────────────────────────────────

const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']

function MiniCalendar({
  selectedDay,
  signalCounts,
  onSelectDay,
  onClose,
}: {
  selectedDay: string | null
  signalCounts: Map<string, number>
  onSelectDay: (day: string) => void
  onClose: () => void
}) {
  const [viewMonth, setViewMonth] = useState(() => startOfMonth(new Date()))
  const ref = useRef<HTMLDivElement>(null)
  const today = startOfDay(new Date())

  // Close on click outside
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const monthStart = startOfMonth(viewMonth)
  const monthEnd = endOfMonth(viewMonth)
  const daysInMonth = eachDayOfInterval({ start: monthStart, end: monthEnd })
  const startPad = getDay(monthStart) // 0=Sun

  return (
    <div
      ref={ref}
      className="absolute top-full mt-1 right-0 z-50 bg-anveshak-card border border-anveshak-border rounded-lg shadow-xl p-3 w-[280px]"
    >
      {/* Month nav */}
      <div className="flex items-center justify-between mb-2">
        <button
          className="p-1 text-text-muted hover:text-text-primary text-sm"
          onClick={() => setViewMonth((m) => subMonths(m, 1))}
        >
          ◀
        </button>
        <span className="text-xs font-semibold text-text-primary">
          {format(viewMonth, 'MMMM yyyy')}
        </span>
        <button
          className="p-1 text-text-muted hover:text-text-primary text-sm"
          onClick={() => setViewMonth((m) => addMonths(m, 1))}
          disabled={viewMonth >= startOfMonth(new Date())}
        >
          ▶
        </button>
      </div>

      {/* Weekday header */}
      <div className="grid grid-cols-7 gap-0.5 mb-1">
        {WEEKDAYS.map((wd) => (
          <span key={wd} className="text-[9px] text-text-muted text-center font-medium">
            {wd}
          </span>
        ))}
      </div>

      {/* Day grid */}
      <div className="grid grid-cols-7 gap-0.5">
        {/* Empty cells for padding */}
        {Array.from({ length: startPad }).map((_, i) => (
          <div key={`pad-${i}`} />
        ))}

        {daysInMonth.map((day) => {
          const key = format(day, 'yyyy-MM-dd')
          const count = signalCounts.get(key) || 0
          const isToday = isSameDay(day, today)
          const isFuture = day > today
          const isSelected = selectedDay === key

          return (
            <button
              key={key}
              disabled={isFuture}
              onClick={() => {
                onSelectDay(key)
                onClose()
              }}
              className={`relative flex flex-col items-center py-1 rounded text-xs transition-colors ${
                isFuture
                  ? 'text-text-muted/30 cursor-not-allowed'
                  : isSelected
                    ? 'bg-anveshak-accent text-white'
                    : isToday
                      ? 'bg-anveshak-accent/20 text-anveshak-accent font-bold'
                      : 'text-text-secondary hover:bg-anveshak-muted'
              }`}
            >
              <span>{format(day, 'd')}</span>
              {count > 0 && (
                <span
                  className={`w-1.5 h-1.5 rounded-full mt-0.5 ${
                    isSelected ? 'bg-white' : 'bg-anveshak-accent'
                  }`}
                />
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── Main Calendar Strip ────────────────────────────────────────────────

export function CalendarStrip({
  dailyCounts,
  windowDays,
  selectedDay,
  onSelectDay,
}: CalendarStripProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [calendarOpen, setCalendarOpen] = useState(false)

  // Build date range: today back to windowDays
  const days = useMemo(() => {
    const today = startOfDay(new Date())
    const result: Date[] = []
    for (let i = windowDays - 1; i >= 0; i--) {
      result.push(subDays(today, i))
    }
    return result
  }, [windowDays])

  // Build count map from backend daily counts
  const countByDay = useMemo(() => {
    const map = new Map<string, number>()
    for (const dc of dailyCounts) {
      map.set(dc.date, dc.count)
    }
    return map
  }, [dailyCounts])

  // Max count for normalizing bar heights
  const maxCount = useMemo(() => {
    let max = 0
    for (const c of countByDay.values()) {
      if (c > max) max = c
    }
    return max || 1
  }, [countByDay])

  // Scroll to end (today) on mount
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth
    }
  }, [windowDays])

  const today = startOfDay(new Date())

  return (
    <div className="flex items-start gap-2">
      {/* Day strip */}
      <div
        ref={scrollRef}
        className="flex-1 flex overflow-x-auto gap-0.5 py-1 scrollbar-thin scrollbar-thumb-anveshak-border scrollbar-track-transparent"
      >
        {days.map((day) => {
          const key = format(day, 'yyyy-MM-dd')
          const count = countByDay.get(key) || 0
          const isToday = isSameDay(day, today)
          const isSelected = selectedDay === key
          const hasDaySelected = selectedDay !== null
          const isDimmed = hasDaySelected && !isSelected
          const barHeight = count > 0 ? Math.max(4, Math.round((count / maxCount) * 20)) : 0

          return (
            <button
              key={key}
              onClick={() => onSelectDay(isSelected ? null : key)}
              className={`flex flex-col items-center shrink-0 rounded-md px-1 py-1 transition-colors ${
                isSelected
                  ? 'bg-anveshak-accent/20 ring-2 ring-anveshak-accent'
                  : isDimmed
                    ? 'opacity-40 hover:opacity-70'
                    : isToday
                      ? 'bg-anveshak-card'
                      : 'hover:bg-anveshak-muted/50'
              }`}
              style={{ width: DAY_WIDTH }}
              title={`${format(day, 'MMM d')}${count > 0 ? ` — ${count} signal${count > 1 ? 's' : ''}` : ''}`}
            >
              {/* Day of week */}
              <span className={`text-[9px] font-medium ${
                isSelected ? 'text-anveshak-accent' : isToday && !isDimmed ? 'text-anveshak-accent' : 'text-text-muted'
              }`}>
                {format(day, 'EEE')}
              </span>

              {/* Date number */}
              <span className={`text-xs font-semibold ${
                isSelected
                  ? 'text-anveshak-accent'
                  : isToday && !isDimmed
                    ? 'text-text-primary'
                    : 'text-text-secondary'
              }`}>
                {format(day, 'd')}
              </span>

              {/* Activity bar area */}
              <div className="w-full h-5 flex items-end justify-center mt-0.5">
                {count > 0 && (
                  <div
                    className="w-3/4 rounded-sm transition-all"
                    style={{
                      height: barHeight,
                      backgroundColor: isSelected
                        ? 'var(--anveshak-accent, #3b82f6)'
                        : count > maxCount * 0.7
                          ? 'var(--signal-high, #ef4444)'
                          : count > maxCount * 0.3
                            ? 'var(--signal-med, #f59e0b)'
                            : 'var(--signal-low, #10b981)',
                    }}
                  />
                )}
              </div>

              {/* Signal count */}
              {count > 0 && (
                <span className={`text-[8px] mt-0.5 ${isDimmed ? 'text-text-muted/50' : 'text-text-muted'}`}>{count}</span>
              )}
            </button>
          )
        })}
      </div>

      {/* Calendar picker button */}
      <div className="relative shrink-0 pt-1">
        <button
          onClick={() => setCalendarOpen((v) => !v)}
          className={`flex items-center gap-1 px-2 py-1.5 rounded-md text-xs font-medium transition-colors ${
            calendarOpen
              ? 'bg-anveshak-accent text-white'
              : 'bg-anveshak-muted text-text-secondary hover:bg-anveshak-card hover:text-text-primary'
          }`}
          title="Open calendar"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </button>

        {calendarOpen && (
          <MiniCalendar
            selectedDay={selectedDay}
            signalCounts={countByDay}
            onSelectDay={(day) => onSelectDay(day)}
            onClose={() => setCalendarOpen(false)}
          />
        )}
      </div>
    </div>
  )
}
