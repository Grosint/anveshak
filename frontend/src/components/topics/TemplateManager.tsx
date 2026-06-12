import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { templatesApi, type ScamTemplate } from '../../api/templates'
import { Spinner } from '../ui/Spinner'

interface TemplateManagerProps {
  topicId: string
}

export default function TemplateManager({ topicId }: TemplateManagerProps) {
  const qc = useQueryClient()

  const { data: allTemplates = [], isLoading: loadingAll } = useQuery({
    queryKey: ['templates'],
    queryFn: templatesApi.list,
  })

  const { data: linkedTemplates = [], isLoading: loadingLinked } = useQuery({
    queryKey: ['topic-templates', topicId],
    queryFn: () => templatesApi.listForTopic(topicId),
    enabled: !!topicId,
  })

  const linkedIds = new Set(linkedTemplates.map((t) => t.id))

  const linkMutation = useMutation({
    mutationFn: (templateId: string) => templatesApi.link(topicId, templateId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['topic-templates', topicId] }),
  })

  const unlinkMutation = useMutation({
    mutationFn: (templateId: string) => templatesApi.unlink(topicId, templateId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['topic-templates', topicId] }),
  })

  if (loadingAll || loadingLinked) {
    return <Spinner label="Loading templates…" />
  }

  const toggle = (tpl: ScamTemplate) => {
    if (linkedIds.has(tpl.id)) {
      unlinkMutation.mutate(tpl.id)
    } else {
      linkMutation.mutate(tpl.id)
    }
  }

  return (
    <div>
      <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-3">
        Scam Templates ({linkedIds.size} active)
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {allTemplates.map((tpl) => {
          const active = linkedIds.has(tpl.id)
          return (
            <button
              key={tpl.id}
              onClick={() => toggle(tpl)}
              className={`text-left rounded-lg border p-3 transition-all ${
                active
                  ? 'border-anveshak-accent/40 bg-anveshak-accent/10'
                  : 'border-anveshak-border bg-anveshak-card hover:border-anveshak-border/80'
              }`}
              disabled={linkMutation.isPending || unlinkMutation.isPending}
            >
              <div className="flex items-center justify-between mb-1">
                <span className={`text-xs font-semibold ${active ? 'text-anveshak-accent' : 'text-text-primary'}`}>
                  {tpl.name.replace(/_/g, ' ')}
                </span>
                <span className={`w-2 h-2 rounded-full ${active ? 'bg-anveshak-accent' : 'bg-anveshak-border'}`} />
              </div>
              <p className="text-[10px] text-text-muted line-clamp-2">
                {tpl.display}
              </p>
              <span className={`text-[8px] font-medium mt-1 inline-block rounded px-1 py-0.5 ${
                tpl.severity === 'HIGH' || tpl.severity === 'CRITICAL'
                  ? 'text-red-400 bg-red-500/10'
                  : tpl.severity === 'MEDIUM'
                  ? 'text-amber-400 bg-amber-500/10'
                  : 'text-text-muted bg-white/[0.04]'
              }`}>
                {tpl.severity} · {tpl.category}
              </span>
              {tpl.keywords && tpl.keywords.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {tpl.keywords.slice(0, 4).map((kw) => (
                    <span
                      key={kw}
                      className="text-[8px] text-text-muted bg-white/[0.04] border border-white/[0.06] rounded px-1 py-0.5"
                    >
                      {kw}
                    </span>
                  ))}
                  {tpl.keywords.length > 4 && (
                    <span className="text-[8px] text-text-muted">+{tpl.keywords.length - 4}</span>
                  )}
                </div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
