import { useQuery } from '@tanstack/react-query'
import api from '../../api/client'
import { formatDistanceToNow } from 'date-fns'

interface AuditEntry {
  id: string
  user_id: string
  action: string
  resource_type: string
  resource_id: string
  details: string | Record<string, unknown>
  ip_address: string
  created_at: string
}

const ACTION_COLORS: Record<string, string> = {
  create: 'text-green-400',
  generate: 'text-blue-400',
  delete: 'text-red-400',
  update: 'text-amber-400',
  acknowledge: 'text-purple-400',
  dismiss: 'text-text-muted',
  export: 'text-cyan-400',
  link: 'text-teal-400',
  unlink: 'text-orange-400',
}

function actionColor(action: string): string {
  for (const [key, color] of Object.entries(ACTION_COLORS)) {
    if (action.includes(key)) return color
  }
  return 'text-text-muted'
}

interface RecentActivityProps {
  topicId: string
}

export function RecentActivity({ topicId }: RecentActivityProps) {
  const { data: entries = [], isLoading } = useQuery({
    queryKey: ['audit-mini', topicId],
    queryFn: () =>
      api
        .get<AuditEntry[]>('/api/v1/system/audit-trail', {
          params: { resource_id: topicId, limit: 5 },
        })
        .then((r) => r.data)
        .catch(() => [] as AuditEntry[]),
    staleTime: Infinity,
    retry: false,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
  })

  return (
    <div>
      <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">
        Recent Activity
      </h3>

      {isLoading ? (
        <p className="text-[11px] text-text-muted">Loading...</p>
      ) : entries.length === 0 ? (
        <p className="text-[11px] text-text-muted">No activity</p>
      ) : (
        <div className="space-y-1">
          {entries.map((e) => (
            <div key={e.id} className="flex items-center gap-2 text-[10px]">
              <span className={`font-medium ${actionColor(e.action)}`}>
                {e.action.split('.').pop()}
              </span>
              <span className="text-text-muted truncate flex-1">
                {e.resource_type}
              </span>
              <span className="text-text-muted shrink-0">
                {formatDistanceToNow(new Date(e.created_at), { addSuffix: true })}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
