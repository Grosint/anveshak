import { format } from 'date-fns'
import { useProvenance } from '../../contexts/ProvenanceContext'
import { PlatformBadge } from '../content/PlatformBadge'
import { deepfakeLabel } from '../../lib/domain'

interface TimelineItem {
  id: string
  title?: string | null
  clean_text?: string | null
  captured_at: string
  platform?: string | null
  source_name?: string | null
  deepfake_score?: number | null
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

  // Group items by date for date markers
  const groups: { date: string; items: TimelineItem[] }[] = []
  for (const item of items) {
    const date = format(new Date(item.captured_at), 'MMM d, yyyy')
    const last = groups[groups.length - 1]
    if (last && last.date === date) {
      last.items.push(item)
    } else {
      groups.push({ date, items: [item] })
    }
  }

  return (
    <div
      className="relative"
      style={maxHeight ? { maxHeight, overflowY: 'auto' } : undefined}
    >
      {/* Center spine */}
      <div className="absolute left-[7px] top-0 bottom-0 w-0.5 bg-gradient-to-b from-anveshak-accent/60 via-anveshak-accent/30 to-anveshak-border/20" />

      <div className="space-y-1">
        {groups.map((group) => (
          <div key={group.date}>
            {/* Date marker on spine */}
            <div className="relative flex items-center mb-2 mt-3 first:mt-0">
              <div className="w-[15px] h-[15px] rounded-full bg-anveshak-accent/20 border-2 border-anveshak-accent flex items-center justify-center shrink-0 z-10">
                <div className="w-1.5 h-1.5 rounded-full bg-anveshak-accent" />
              </div>
              <span className="ml-3 text-[10px] font-bold text-anveshak-accent uppercase tracking-wider">
                {group.date}
              </span>
            </div>

            {/* Items for this date */}
            {group.items.map((item) => (
              <button
                key={item.id}
                className="relative flex w-full text-left group mb-1.5"
                onClick={() => push({
                  entityType: 'content',
                  entityId: item.id,
                  topicId,
                  label: item.title || item.clean_text?.slice(0, 30) || item.id.slice(0, 8),
                })}
              >
                {/* Small dot on spine */}
                <div className="w-[15px] flex items-start justify-center pt-3 shrink-0">
                  <div className="w-2 h-2 rounded-full bg-anveshak-border group-hover:bg-anveshak-accent/80 transition-colors z-10" />
                </div>

                {/* Connector line + card */}
                <div className="flex-1 ml-1 min-w-0">
                  {/* Horizontal connector */}
                  <div className="absolute left-[15px] top-[14px] w-3 h-0.5 bg-anveshak-border/40" />

                  <div className="ml-3 border border-anveshak-border/20 rounded-md p-2 group-hover:border-anveshak-accent/40 group-hover:bg-anveshak-card/30 transition-all">
                    {/* Time + platform */}
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="text-[9px] font-mono text-text-muted">
                        {format(new Date(item.captured_at), 'HH:mm')}
                      </span>
                      {item.platform && <PlatformBadge platform={item.platform} />}
                      {item.source_name && (
                        <span className="text-[9px] text-text-muted truncate">{item.source_name}</span>
                      )}
                      {item.deepfake_score != null && item.deepfake_score >= 0.7 && (() => {
                        const df = deepfakeLabel(item.deepfake_score)
                        return (
                          <span className={`text-[9px] font-bold ${df.cssClass}`}>
                            ⚠ {Math.round(item.deepfake_score * 100)}%
                          </span>
                        )
                      })()}
                    </div>

                    {/* Title */}
                    {item.title && (
                      <p className="text-[11px] font-medium text-text-primary line-clamp-1 leading-snug">
                        {item.title}
                      </p>
                    )}

                    {/* Snippet */}
                    {item.clean_text && (
                      <p className="text-[10px] text-text-secondary/50 line-clamp-1 leading-relaxed">
                        {item.clean_text}
                      </p>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
