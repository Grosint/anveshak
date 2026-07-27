import { useQuery } from '@tanstack/react-query'
import { provenanceApi } from '../../api/provenance'
import { useProvenance } from '../../contexts/ProvenanceContext'
import { Spinner } from '../ui/Spinner'
import { Badge } from '../ui/Badge'
import { EmptyState } from '../ui/EmptyState'
import { CredibilityBadge } from '../content/CredibilityBadge'
import { formatDistanceToNow } from 'date-fns'

const HEALTH_VARIANT: Record<string, 'success' | 'warning' | 'danger' | 'default'> = {
  healthy: 'success',
  degraded: 'warning',
  down: 'danger',
  unverified: 'default',
}

interface SourceDetailProps {
  sourceId: string
  topicId: string
}

export default function SourceDetail({ sourceId, topicId }: SourceDetailProps) {
  const { push } = useProvenance()

  const { data, isLoading } = useQuery({
    queryKey: ['provenance', 'source', sourceId, topicId],
    queryFn: () => provenanceApi.sourceProvenance(sourceId, topicId),
    enabled: !!sourceId && !!topicId,
  })

  if (isLoading) return <div className="p-4"><Spinner label="Loading source..." /></div>
  if (!data) return <EmptyState icon="📡" title="Not found" description="Source not found." />

  return (
    <div className="divide-y divide-anveshak-border/30">
      {/* Header */}
      <div className="px-4 py-3">
        <p className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-1">Source</p>
        <p className="text-sm font-semibold text-text-primary">{data.name}</p>
        <div className="flex items-center gap-2 mt-2">
          <Badge variant="ghost">{data.platform.toUpperCase()}</Badge>
          <CredibilityBadge score={data.credibility_score} />
          <Badge variant={HEALTH_VARIANT[data.health_status] ?? 'default'}>
            {data.health_status}
          </Badge>
        </div>
      </div>

      {/* Recent content */}
      <Section title={`Recent Content (${data.recent_content.length})`}>
        {data.recent_content.length === 0 ? (
          <p className="text-[11px] text-text-muted">No recent content from this source.</p>
        ) : (
          <div className="space-y-1.5">
            {data.recent_content.map((item) => (
              <button
                key={item.id}
                className="w-full text-left p-2 bg-anveshak-card/50 border border-anveshak-border rounded hover:border-anveshak-accent/40 transition-colors"
                onClick={() => push({ entityType: 'content', entityId: item.id, topicId, label: item.title || item.id.slice(0, 8) })}
              >
                <p className="text-[11px] text-text-primary line-clamp-1">{item.title || 'Untitled'}</p>
                <p className="text-[9px] text-text-muted">
                  {formatDistanceToNow(new Date(item.captured_at), { addSuffix: true })}
                </p>
              </button>
            ))}
          </div>
        )}
      </Section>

      {/* Credibility audit log */}
      <Section title={`Credibility History (${data.audit_log.length})`}>
        {data.audit_log.length === 0 ? (
          <p className="text-[11px] text-text-muted">No credibility changes recorded.</p>
        ) : (
          <div className="space-y-1">
            {data.audit_log.map((entry) => (
              <div key={entry.id} className="flex items-center gap-2 text-[10px] text-text-muted">
                <span className={entry.new_score > entry.old_score ? 'text-green-400' : 'text-red-400'}>
                  {entry.old_score.toFixed(1)} → {entry.new_score.toFixed(1)}
                </span>
                <span className="truncate">{entry.reason}</span>
                <span className="shrink-0">
                  {formatDistanceToNow(new Date(entry.created_at), { addSuffix: true })}
                </span>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="px-4 py-3">
      <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">{title}</h3>
      {children}
    </div>
  )
}
