import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { actorsApi } from '../../api/actors'
import { useProvenance } from '../../contexts/ProvenanceContext'
import { Badge } from '../ui/Badge'
import { EmptyState } from '../ui/EmptyState'
import { Spinner } from '../ui/Spinner'

/**
 * Actor View — issue #35.
 *
 * Public content authored by one handle within one Topic. Everything here is
 * derived on demand from content items: no actor record exists to display,
 * and the footer says so, because an analyst reading this panel is entitled
 * to know what the system keeps.
 */

interface ActorDetailProps {
  handle: string
  topicId: string
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="px-4 py-3">
      <p className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">
        {title}
      </p>
      {children}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex-1 min-w-[70px]">
      <p className="text-sm font-semibold text-text-primary">{value}</p>
      <p className="text-[10px] text-text-muted">{label}</p>
    </div>
  )
}

export default function ActorDetail({ handle, topicId }: ActorDetailProps) {
  const { push } = useProvenance()

  const { data, isLoading } = useQuery({
    queryKey: ['actor', topicId, handle],
    queryFn: () => actorsApi.get(topicId, handle),
    enabled: !!handle && !!topicId,
  })

  if (isLoading) {
    return <div className="p-4"><Spinner label="Loading actor..." /></div>
  }
  if (!data) {
    return (
      <EmptyState
        icon="👤"
        title="Not found"
        description="No public content for this handle in this topic."
      />
    )
  }

  const summary = data.summary ?? {}
  const platforms = summary.platforms ?? []
  const approximate = data.activity.reduce((n, point) => n + (point.approximate_count ?? 0), 0)

  return (
    <div className="divide-y divide-anveshak-border/30">
      <div className="px-4 py-3">
        <p className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-1">
          Actor
        </p>
        <p className="text-sm font-mono font-semibold text-amber-400 break-all">
          @{data.handle}
        </p>
        {platforms.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {platforms.map((platform) => (
              <Badge key={platform} variant="ghost">{platform}</Badge>
            ))}
          </div>
        )}
      </div>

      <Section title="Activity">
        <div className="flex flex-wrap gap-3">
          <Stat label="posts" value={summary.post_count ?? 0} />
          <Stat label="sources" value={summary.source_count ?? 0} />
          <Stat label="likes" value={summary.total_likes ?? 0} />
          <Stat label="views" value={summary.total_views ?? 0} />
          <Stat label="shares" value={summary.total_shares ?? 0} />
        </div>
        {summary.first_seen && summary.last_seen && (
          <p className="text-[10px] text-text-muted mt-2">
            First {formatDistanceToNow(new Date(summary.first_seen), { addSuffix: true })}
            {' · '}
            latest {formatDistanceToNow(new Date(summary.last_seen), { addSuffix: true })}
          </p>
        )}
        {approximate > 0 && (
          <p className="text-[10px] text-signal-med mt-1">
            {approximate} posts plotted at collection time: the platform gave no publication
            time.
          </p>
        )}
      </Section>

      <Section title={`Public content (${data.content.length})`}>
        {data.content.length === 0 ? (
          <p className="text-[11px] text-text-muted">No public content in this topic.</p>
        ) : (
          <div className="space-y-2">
            {data.content.map((item) => (
              <button
                key={item.id}
                className="w-full text-left bg-anveshak-card/50 border border-anveshak-border rounded-lg p-2.5 hover:border-anveshak-accent/40 transition-colors"
                onClick={() =>
                  push({
                    entityType: 'content',
                    entityId: item.id,
                    topicId,
                    label: item.title || item.clean_text.slice(0, 30),
                  })
                }
              >
                <div className="flex items-center justify-between mb-1 gap-2">
                  <span className="text-[9px] font-bold text-text-muted">
                    {(item.platform ?? '').toUpperCase()}
                  </span>
                  <span className="text-[9px] text-text-muted">
                    {formatDistanceToNow(new Date(item.published_at ?? item.captured_at), {
                      addSuffix: true,
                    })}
                  </span>
                </div>
                <p className="text-[10px] text-text-secondary/80 line-clamp-3">
                  {item.clean_text}
                </p>
                <div className="flex items-center gap-2 mt-1.5">
                  {item.cluster_label && (
                    <span className="text-[9px] text-text-muted truncate">
                      {item.cluster_label}
                    </span>
                  )}
                  {item.stance && <Badge variant="ghost">{item.stance}</Badge>}
                </div>
              </button>
            ))}
          </div>
        )}
      </Section>

      <div className="px-4 py-3">
        <p className="text-[10px] text-text-muted leading-relaxed">
          This view is a query over public content in this topic. No record is stored about
          the person behind the handle.
        </p>
      </div>
    </div>
  )
}
