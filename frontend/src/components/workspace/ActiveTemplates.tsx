import { useQuery } from '@tanstack/react-query'
import { templatesApi } from '../../api/templates'

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: 'bg-red-500/20 text-red-400 border-red-500/30',
  HIGH: 'bg-signal-high/20 text-signal-high border-signal-high/30',
  MEDIUM: 'bg-signal-med/20 text-signal-med border-signal-med/30',
  LOW: 'bg-white/5 text-text-muted border-white/10',
}

interface ActiveTemplatesProps {
  topicId: string
  onManage: () => void
}

export function ActiveTemplates({ topicId, onManage }: ActiveTemplatesProps) {
  const { data: templates = [], isLoading } = useQuery({
    queryKey: ['topic-templates', topicId],
    queryFn: () => templatesApi.listForTopic(topicId),
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest">
          Templates
        </h3>
        <button
          onClick={onManage}
          className="text-[9px] text-anveshak-accent hover:underline"
        >
          Manage
        </button>
      </div>

      {isLoading ? (
        <p className="text-[11px] text-text-muted">Loading...</p>
      ) : templates.length === 0 ? (
        <p className="text-[11px] text-text-muted">No templates linked</p>
      ) : (
        <div className="flex flex-wrap gap-1">
          {templates.map((tpl) => (
            <span
              key={tpl.id}
              className={`text-[9px] font-medium rounded px-1.5 py-0.5 border ${SEVERITY_COLORS[tpl.severity] ?? SEVERITY_COLORS.LOW}`}
            >
              {tpl.name.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
