import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { topicsApi } from '../../api/topics'

const DAY_OPTIONS = [3, 7, 14, 30] as const

interface TrendingKeywordsProps {
  topicId: string
}

export function TrendingKeywords({ topicId }: TrendingKeywordsProps) {
  const [days, setDays] = useState<number>(7)

  const { data, isLoading } = useQuery({
    queryKey: ['trending-keywords', topicId, days],
    queryFn: () => topicsApi.trendingKeywords(topicId, days),
    staleTime: 60_000,
  })

  const maxFreq = data && data.length > 0 ? data[0].frequency : 1

  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wide">
          Trending Keywords
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
          No keyword data yet
        </div>
      ) : (
        <div className="space-y-1.5 max-h-[160px] overflow-y-auto">
          {data.map((kw: { keyword: string; frequency: number }) => (
            <div key={kw.keyword} className="flex items-center gap-2">
              <span className="text-xs text-text-primary truncate min-w-[100px] max-w-[160px]">
                {kw.keyword}
              </span>
              <div className="flex-1 h-3 bg-anveshak-muted rounded-sm overflow-hidden">
                <div
                  className="h-full bg-anveshak-accent/40 rounded-sm transition-all"
                  style={{ width: `${(kw.frequency / maxFreq) * 100}%` }}
                />
              </div>
              <span className="text-[10px] text-text-muted tabular-nums w-6 text-right">
                {kw.frequency}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
