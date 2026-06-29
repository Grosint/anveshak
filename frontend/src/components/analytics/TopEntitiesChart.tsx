import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts'

// Hardcoded hex — Recharts can't resolve CSS var()
const BAR_COLOR = '#8b5cf6' // purple accent

interface TopEntitiesChartProps {
  data: { entity_type: string; entity_text: string; mention_count: number }[]
}

export function TopEntitiesChart({ data }: TopEntitiesChartProps) {
  const top15 = data.slice(0, 15).map((d) => ({
    name: d.entity_text.length > 20 ? d.entity_text.slice(0, 18) + '...' : d.entity_text,
    fullName: d.entity_text,
    count: d.mention_count,
    type: d.entity_type,
  }))

  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
        Top Entities
      </h2>
      <div className="h-64">
        {top15.length === 0 ? (
          <div className="flex items-center justify-center h-full text-xs text-text-muted">
            No entities extracted yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={top15} layout="vertical" margin={{ left: 5, right: 20, top: 0, bottom: 0 }}>
              <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                width={110}
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
