import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from 'recharts'
import { topicsApi } from '../../api/topics'

const DAY_OPTIONS = [7, 14, 30, 90] as const

interface SentimentTrendProps {
  topicId: string
}

export function SentimentTrend({ topicId }: SentimentTrendProps) {
  const [days, setDays] = useState<number>(30)

  const { data, isLoading } = useQuery({
    queryKey: ['sentiment-trend', topicId, days],
    queryFn: () => topicsApi.sentimentTrend(topicId, days),
    staleTime: 60_000,
  })

  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wide">
          Sentiment Trend
        </h3>
        <div className="flex gap-1">
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                days === d
                  ? 'bg-anveshak-accent/20 text-anveshak-accent'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="h-40 flex items-center justify-center text-xs text-text-muted">
          Loading...
        </div>
      ) : !data || data.length === 0 ? (
        <div className="h-40 flex items-center justify-center text-xs text-text-muted">
          No sentiment data yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: '#94a3b8' }}
              tickFormatter={(v: string) => v.slice(5)}
            />
            <YAxis
              domain={[-1, 1]}
              tick={{ fontSize: 10, fill: '#94a3b8' }}
              tickFormatter={(v: number) => v.toFixed(1)}
              width={32}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '6px',
                fontSize: '11px',
              }}
              labelStyle={{ color: '#94a3b8' }}
              formatter={(value: number, _name: string) => [value.toFixed(3), 'Compound']}
            />
            <ReferenceLine y={0} stroke="#475569" strokeDasharray="3 3" />
            <Line
              type="monotone"
              dataKey="avg_compound"
              stroke="#38bdf8"
              strokeWidth={2}
              dot={{ r: 3, fill: '#38bdf8' }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
