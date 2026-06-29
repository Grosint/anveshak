import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts'

// Hardcoded hex — Recharts can't resolve CSS var()
const COLORS = {
  new: '#f59e0b',         // amber — new signals
  acknowledged: '#10b981', // green — acknowledged
  dismissed: '#6b7280',    // gray — dismissed
  grid: '#1e293b',
}

interface SignalActivityTrendProps {
  data: { date: string; new_count: number; ack_count: number; dismissed_count: number }[]
}

export function SignalActivityTrend({ data }: SignalActivityTrendProps) {
  const formatted = data.map((d) => ({
    ...d,
    label: new Date(d.date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
  }))

  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
        Signal Activity
      </h2>
      <div className="h-52">
        {formatted.length === 0 ? (
          <div className="flex items-center justify-center h-full text-xs text-text-muted">
            No signals in this period
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={formatted} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
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
                width={25}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: 6,
                  fontSize: 12,
                }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Legend
                wrapperStyle={{ fontSize: 11, color: '#94a3b8' }}
              />
              <Bar dataKey="new_count" name="New" fill={COLORS.new} stackId="signals" radius={[0, 0, 0, 0]} />
              <Bar dataKey="ack_count" name="Acknowledged" fill={COLORS.acknowledged} stackId="signals" radius={[0, 0, 0, 0]} />
              <Bar dataKey="dismissed_count" name="Dismissed" fill={COLORS.dismissed} stackId="signals" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
