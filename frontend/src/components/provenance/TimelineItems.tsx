import { format } from 'date-fns'
import { useProvenance } from '../../contexts/ProvenanceContext'

interface TimelineItem {
  id: string
  title?: string | null
  clean_text?: string | null
  captured_at: string
  platform?: string | null
  source_name?: string | null
}

interface TimelineItemsProps {
  items: TimelineItem[]
  topicId: string
  maxHeight?: string
}

export function TimelineItems({ items, topicId, maxHeight }: TimelineItemsProps) {
  const { push } = useProvenance()

  if (items.length === 0) {
    return <p className="text-[11px] text-text-muted">No items.</p>
  }

  return (
    <div
      className="relative pl-3 border-l border-anveshak-border/40 space-y-2"
      style={maxHeight ? { maxHeight, overflowY: 'auto' } : undefined}
    >
      {items.map((item) => (
        <button
          key={item.id}
          className="w-full text-left block relative"
          onClick={() => push({
            entityType: 'content',
            entityId: item.id,
            topicId,
            label: item.title || item.clean_text?.slice(0, 30) || item.id.slice(0, 8),
          })}
        >
          <div className="absolute -left-[13px] top-1.5 w-2 h-2 rounded-full bg-anveshak-accent/60" />
          <div className="pl-2 pb-1 hover:bg-anveshak-card/30 rounded transition-colors">
            <div className="flex items-center gap-2 text-[9px] text-text-muted">
              <span>{format(new Date(item.captured_at), 'MMM d HH:mm')}</span>
              {item.platform && <span className="font-bold">{item.platform.toUpperCase()}</span>}
              {item.source_name && <span className="truncate">{item.source_name}</span>}
            </div>
            {item.title && (
              <p className="text-[11px] font-medium text-text-primary line-clamp-1">{item.title}</p>
            )}
            {item.clean_text && (
              <p className="text-[10px] text-text-secondary/70 line-clamp-2">{item.clean_text}</p>
            )}
          </div>
        </button>
      ))}
    </div>
  )
}
