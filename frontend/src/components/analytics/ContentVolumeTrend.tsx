import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'

// Hardcoded hex — Recharts can't resolve CSS var()
const AREA_COLOR = '#F5A623' // --anveshak-accent
const GRID_COLOR = '#1e293b' // subtle grid

interface ContentVolumeTrendProps {
  data: { date: string; count: number }[]
}

export function ContentVolumeTrend({ data }: ContentVolumeTrendProps) {
  const formatted = data.map((d) => ({
    ...d,
    label: new Date(d.date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
  }))

  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
        Content Volume
      </h2>
      <div className="h-52">
        {formatted.length === 0 ? (
          <div className="flex items-center justify-center h-full text-xs text-text-muted">
            No content in this period
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={formatted} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
                width={35}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: 6,
                  fontSize: 12,
                }}
                labelStyle={{ color: '#e2e8f0' }}
                itemStyle={{ color: AREA_COLOR }}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke={AREA_COLOR}
                fill={AREA_COLOR}
                fillOpacity={0.15}
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
