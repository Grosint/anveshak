import { useQuery } from '@tanstack/react-query'
import { contentApi, ContentItem } from '../../api/content'
import { PlatformBadge } from '../content/PlatformBadge'
import { formatDistanceToNow } from 'date-fns'

interface RecentContentProps {
  topicId: string
  onSelectContent: (contentId: string, title?: string) => void
  onShowAll?: () => void
}

export function RecentContent({ topicId, onSelectContent, onShowAll }: RecentContentProps) {
  const { data } = useQuery({
    queryKey: ['recent-content', topicId],
    queryFn: () => contentApi.list(topicId, 0, 5, undefined, 'captured_at'),
    staleTime: 60_000,
  })

  const items: ContentItem[] = data ?? []

  if (items.length === 0) return null

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[11px] font-bold text-text-muted uppercase tracking-widest">
          Recent Content
        </h2>
        {onShowAll && (
          <button onClick={onShowAll} className="text-[10px] text-anveshak-accent hover:underline">
            Show all →
          </button>
        )}
      </div>
      <div className="space-y-1.5">
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelectContent(item.id, item.title ?? undefined)}
            className="w-full text-left bg-anveshak-card border border-anveshak-border rounded-lg p-2.5 hover:border-anveshak-accent/40 transition-all"
          >
            <div className="flex items-center gap-2 mb-1">
              {item.platform && <PlatformBadge platform={item.platform} />}
              {item.source_name && (
                <span className="text-[10px] text-text-muted truncate">
                  {item.source_name.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}
                </span>
              )}
              <span className="text-[10px] text-text-muted ml-auto shrink-0">
                {formatDistanceToNow(new Date(item.captured_at), { addSuffix: true })}
              </span>
            </div>
            {item.title && (
              <p className="text-[11px] font-medium text-text-primary line-clamp-1">
                {item.title}
              </p>
            )}
          </button>
        ))}
      </div>
    </section>
  )
}
