import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { timelineApi } from '../../api/timeline'
import { Spinner } from '../ui/Spinner'

/**
 * Sentiment Timeline — issue #29.
 *
 * Supporting and opposing volume as separate series, with mean hostility on
 * a secondary axis. Two diverging volume curves show polarisation; a rising
 * hostility line shows escalation independent of which side is growing.
 *
 * Absolute volume is the default so a volume explosion is never hidden by
 * normalisation. Items with no publication time are excluded from the plot
 * and reported as a footnote, because a collection artefact plotted at
 * today's date would read as a spike.
 */

const DAY_OPTIONS = [14, 30, 90, 180, 365] as const

// Recharts renders a legend poorly past a handful of series, and the point
// here is the divergence between two of them.
const SERIES = [
  { key: 'supporting', label: 'Supporting', colour: 'var(--chart-1, #3b82f6)' },
  { key: 'opposing', label: 'Opposing', colour: 'var(--chart-2, #f59e0b)' },
  { key: 'neutral', label: 'Neutral', colour: 'var(--chart-3, #6b7280)' },
] as const

export function SentimentTimeline({ topicId }: { topicId: string }) {
  const [days, setDays] = useState<number>(90)
  const [asPercentage, setAsPercentage] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['sentiment-timeline', topicId, days, asPercentage],
    queryFn: () => timelineApi.get(topicId, { days, as_percentage: asPercentage }),
    staleTime: 60_000,
  })

  const buckets = data?.buckets ?? []
  const hasData = buckets.length > 0

  return (
    <section aria-label="Sentiment timeline">
      <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
        <h2 className="text-[11px] font-bold text-text-muted uppercase tracking-widest">
          Sentiment timeline
        </h2>
        <div className="flex items-center gap-1.5">
          {DAY_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setDays(option)}
              aria-pressed={days === option}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                days === option
                  ? 'bg-anveshak-accent/20 text-anveshak-accent'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {option}d
            </button>
          ))}
          <button
            type="button"
            onClick={() => setAsPercentage((current) => !current)}
            aria-pressed={asPercentage}
            className="px-2 py-0.5 rounded text-[10px] font-medium text-text-muted hover:text-text-primary"
          >
            {asPercentage ? 'Absolute' : 'Percentage'}
          </button>
        </div>
      </div>

      {/* Series key in the DOM rather than inside the chart. Recharts renders
          its legend from measured layout, which makes it unreadable at narrow
          widths and invisible to a screen reader. */}
      {hasData && (
        <ul className="flex flex-wrap gap-3 mb-1.5" aria-label="Series key">
          {[...SERIES, { key: 'mean_hostility', label: 'Mean hostility', colour: 'var(--chart-4, #ef4444)' }].map(
            (series) => (
              <li key={series.key} className="flex items-center gap-1.5 text-[10px] text-text-secondary">
                <span
                  aria-hidden="true"
                  className="inline-block w-2 h-2 rounded-sm"
                  style={{ backgroundColor: series.colour }}
                />
                {series.label}
              </li>
            ),
          )}
        </ul>
      )}

      {isLoading ? (
        <div className="py-8"><Spinner label="Loading timeline..." /></div>
      ) : !hasData ? (
        <p className="text-[11px] text-text-muted py-6">
          No scored content with a publication time in this range yet.
        </p>
      ) : (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={buckets} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid, #1f2937)" />
              <XAxis dataKey="bucket" tick={{ fontSize: 10 }} />
              <YAxis yAxisId="volume" tick={{ fontSize: 10 }} />
              {/* Hostility is 0.0 to 1.0 and belongs on its own axis, or the
                  volume curves flatten it into the baseline. */}
              <YAxis
                yAxisId="hostility"
                orientation="right"
                domain={[0, 1]}
                tick={{ fontSize: 10 }}
              />
              <Tooltip />
              {SERIES.map((series) => (
                <Bar
                  key={series.key}
                  yAxisId="volume"
                  dataKey={series.key}
                  name={series.label}
                  stackId="volume"
                  fill={series.colour}
                />
              ))}
              <Line
                yAxisId="hostility"
                type="monotone"
                dataKey="mean_hostility"
                name="Mean hostility"
                stroke="var(--chart-4, #ef4444)"
                dot={false}
                connectNulls
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="mt-2 space-y-1">
        {data && data.excluded_no_publication_time > 0 && (
          <p className="text-[10px] text-text-muted">
            {data.excluded_no_publication_time} items excluded: the platform gave no
            publication time, so plotting them would put a collection artefact on the chart.
          </p>
        )}
        {data && data.constrained_platforms.length > 0 && (
          <p className="text-[10px] text-signal-med">
            History before{' '}
            {data.constrained_platforms
              .map((p) => `${p.platform} ${(p.earliest_published_at ?? '').slice(0, 10)}`)
              .join(', ')}{' '}
            is limited by that platform's search window. A gap there is missing data, not
            silence.
          </p>
        )}
      </div>
    </section>
  )
}
