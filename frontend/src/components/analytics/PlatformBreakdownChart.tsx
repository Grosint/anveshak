import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts'

// Hardcoded hex — Recharts can't resolve CSS var()
const BAR_COLOR = '#3b82f6' // blue

interface PlatformBreakdownChartProps {
  data: { platform: string; count: number }[]
}

export function PlatformBreakdownChart({ data }: PlatformBreakdownChartProps) {
  const sorted = [...data].sort((a, b) => b.count - a.count)

  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
        Content by Platform
      </h2>
      <div className="h-44">
        {sorted.length === 0 ? (
          <div className="flex items-center justify-center h-full text-xs text-text-muted">
            No content data
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={sorted} layout="vertical" margin={{ left: 5, right: 20 }}>
              <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="platform"
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                width={70}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: 6,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="count" fill={BAR_COLOR} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
