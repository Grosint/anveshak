import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { topicsApi } from '../../api/topics'

const DAY_OPTIONS = [3, 7, 14, 30] as const

interface TrendingKeywordsProps {
  topicId: string
}

/** Map frequency ratio (0–1) to font size in px. */
function pillFontSize(ratio: number): number {
  return 11 + ratio * 4 // 11px → 15px
}

/** Map frequency ratio (0–1) to background opacity. */
function pillOpacity(ratio: number): number {
  return 0.15 + ratio * 0.45 // 0.15 → 0.60
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
        <div className="flex flex-wrap gap-2">
          {data.map((kw: { keyword: string; frequency: number }) => {
            const ratio = kw.frequency / maxFreq
            return (
              <span
                key={kw.keyword}
                className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-text-primary cursor-default transition-colors hover:brightness-125"
                style={{
                  fontSize: `${pillFontSize(ratio)}px`,
                  backgroundColor: `color-mix(in srgb, var(--anveshak-accent) ${Math.round(pillOpacity(ratio) * 100)}%, transparent)`,
                }}
              >
                {kw.keyword}
                <span
                  className="text-text-muted tabular-nums"
                  style={{ fontSize: `${Math.max(pillFontSize(ratio) - 2, 9)}px` }}
                >
                  {kw.frequency}
                </span>
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
}
