import { formatDistanceToNow } from 'date-fns'

interface ActivityItem {
  type: string
  description: string
  timestamp: string
  topic_name: string | null
  subtype: string
  resource_id: string
}

const TYPE_CONFIG: Record<string, { icon: string; color: string }> = {
  signal:             { icon: '⚡', color: 'text-yellow-400' },
  report:             { icon: '📄', color: 'text-blue-400' },
  credibility_change: { icon: '🔄', color: 'text-purple-400' },
}

interface RecentActivityFeedProps {
  data: ActivityItem[]
}

export function RecentActivityFeed({ data }: RecentActivityFeedProps) {
  if (data.length === 0) {
    return (
      <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
          Recent Activity
        </h2>
        <p className="text-xs text-text-muted text-center py-6">No recent activity</p>
      </div>
    )
  }

  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-4">
      <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
        Recent Activity
      </h2>
      <div className="space-y-0.5 max-h-72 overflow-y-auto">
        {data.map((item, i) => {
          const cfg = TYPE_CONFIG[item.type] ?? { icon: '•', color: 'text-text-muted' }
          let timeAgo = ''
          try {
            timeAgo = formatDistanceToNow(new Date(item.timestamp), { addSuffix: true })
          } catch (_e: unknown) {
            timeAgo = item.timestamp
          }

          return (
            <div
              key={`${item.resource_id}-${i}`}
              className="flex items-start gap-3 py-2 px-2 rounded hover:bg-anveshak-muted/30 transition-colors"
            >
              <span className="text-sm mt-0.5 shrink-0">{cfg.icon}</span>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-text-primary truncate">
                  {item.description || item.subtype}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  {item.topic_name && (
                    <span className="text-[10px] text-anveshak-accent truncate max-w-[150px]">
                      {item.topic_name}
                    </span>
                  )}
                  <span className="text-[10px] text-text-muted shrink-0">{timeAgo}</span>
                </div>
              </div>
              <span className={`text-[10px] font-medium uppercase ${cfg.color} shrink-0`}>
                {item.type.replace('_', ' ')}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
