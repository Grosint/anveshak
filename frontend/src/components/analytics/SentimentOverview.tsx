import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts'

// Hardcoded hex — Recharts can't resolve CSS var()
const COLORS = {
  positive: '#10b981', // --cred-high
  neutral: '#6b7280',  // --text-muted
  negative: '#ef4444', // --signal-high
}

interface SentimentOverviewProps {
  data: { positive: number; neutral: number; negative: number; total: number }
}

export function SentimentOverview({ data }: SentimentOverviewProps) {
  const chartData = [
    { name: 'Positive', value: data.positive, color: COLORS.positive },
    { name: 'Neutral', value: data.neutral, color: COLORS.neutral },
    { name: 'Negative', value: data.negative, color: COLORS.negative },
  ].filter((d) => d.value > 0)

  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
        Sentiment Distribution
      </h2>
      <div className="h-44">
        {data.total === 0 ? (
          <div className="flex items-center justify-center h-full text-xs text-text-muted">
            No sentiment data
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={35}
                outerRadius={60}
                paddingAngle={2}
                dataKey="value"
                nameKey="name"
              >
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: 6,
                  fontSize: 12,
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        )}
      </div>
      <div className="flex justify-center gap-4 mt-1">
        {[
          { label: 'Positive', value: data.positive, color: COLORS.positive },
          { label: 'Neutral', value: data.neutral, color: COLORS.neutral },
          { label: 'Negative', value: data.negative, color: COLORS.negative },
        ].map((s) => (
          <div key={s.label} className="flex items-center gap-1.5 text-[10px] text-text-muted">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
            {s.label} ({s.value})
          </div>
        ))}
      </div>
    </div>
  )
}
