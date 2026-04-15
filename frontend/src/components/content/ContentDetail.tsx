/**
 * Slide-over panel for full content item detail + entity highlighting.
 */
import { useQuery } from '@tanstack/react-query'
import { contentApi, Entity } from '../../api/content'
import { CredibilityBadge } from './CredibilityBadge'
import { PlatformBadge } from './PlatformBadge'
import { Badge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'
import { format } from 'date-fns'

const ENTITY_COLORS: Record<string, string> = {
  PERSON:   'bg-purple-500/20 text-purple-300 border-purple-500/30',
  ORG:      'bg-blue-500/20 text-blue-300 border-blue-500/30',
  GPE:      'bg-green-500/20 text-green-300 border-green-500/30',
  LOC:      'bg-teal-500/20 text-teal-300 border-teal-500/30',
  WEAPON:   'bg-red-500/20 text-red-300 border-red-500/30',
  MISC:     'bg-amber-500/20 text-amber-300 border-amber-500/30',
}

function highlightEntities(text: string, entities: Entity[]): React.ReactNode {
  if (!entities.length) return text

  // Build sorted list of (start, end, entity) ranges by finding exact text matches
  const matches: Array<{ start: number; end: number; entity: Entity }> = []
  const lower = text.toLowerCase()

  for (const entity of entities) {
    const search = entity.entity_text.toLowerCase()
    let pos = 0
    while ((pos = lower.indexOf(search, pos)) !== -1) {
      matches.push({ start: pos, end: pos + search.length, entity })
      pos += search.length
    }
  }

  if (!matches.length) return text

  // Sort and deduplicate overlapping ranges
  matches.sort((a, b) => a.start - b.start)
  const deduped: typeof matches = []
  let lastEnd = 0
  for (const m of matches) {
    if (m.start >= lastEnd) { deduped.push(m); lastEnd = m.end }
  }

  const nodes: React.ReactNode[] = []
  let cursor = 0
  for (const { start, end, entity } of deduped) {
    if (cursor < start) nodes.push(text.slice(cursor, start))
    const color = ENTITY_COLORS[entity.entity_type] ?? ENTITY_COLORS.MISC
    nodes.push(
      <mark
        key={`${start}-${end}`}
        className={`border rounded px-0.5 mx-0.5 not-italic ${color}`}
        title={`${entity.entity_type} (${Math.round(entity.confidence * 100)}%)`}
      >
        {text.slice(start, end)}
      </mark>,
    )
    cursor = end
  }
  if (cursor < text.length) nodes.push(text.slice(cursor))
  return nodes
}

interface ContentDetailProps {
  contentId: string
  onClose: () => void
}

export function ContentDetail({ contentId, onClose }: ContentDetailProps) {
  const { data: item, isLoading } = useQuery({
    queryKey: ['content', contentId],
    queryFn: () => contentApi.get(contentId),
  })

  const entityTypeGroups = item?.extracted_entities?.reduce<Record<string, Entity[]>>(
    (acc, e) => { (acc[e.entity_type] ??= []).push(e); return acc },
    {},
  ) ?? {}

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside
        className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-lg bg-anveshak-card border-l border-anveshak-border shadow-card-hover flex flex-col animate-fade-in"
        aria-label="Content detail"
        role="complementary"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-anveshak-border">
          <h2 className="font-semibold text-text-primary">Content Detail</h2>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary transition-colors"
            aria-label="Close panel"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5" aria-hidden="true">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <Spinner label="Loading content…" />
          </div>
        ) : item ? (
          <div className="flex-1 overflow-y-auto">
            {/* Meta */}
            <div className="px-5 py-4 border-b border-anveshak-border space-y-2">
              <div className="flex flex-wrap gap-2">
                {item.platform && <PlatformBadge platform={item.platform} />}
                <CredibilityBadge score={item.credibility_score_at_capture} />
                {item.language && <Badge variant="ghost">{item.language.toUpperCase()}</Badge>}
              </div>
              {item.source_name && (
                <p className="text-sm text-text-secondary font-medium">{item.source_name}</p>
              )}
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-anveshak-accent hover:underline break-all"
              >
                {item.url}
              </a>
              <p className="text-xs text-text-muted">
                {item.captured_at
                  ? format(new Date(item.captured_at), 'dd MMM yyyy, HH:mm')
                  : ''}
              </p>
            </div>

            {/* Full text with entity highlighting */}
            <div className="px-5 py-4 border-b border-anveshak-border">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Content</h3>
              <p className="text-sm text-text-primary leading-relaxed whitespace-pre-wrap">
                {highlightEntities(item.clean_text, item.extracted_entities ?? [])}
              </p>
            </div>

            {/* Entities */}
            {Object.keys(entityTypeGroups).length > 0 && (
              <div className="px-5 py-4">
                <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
                  Extracted entities
                </h3>
                <div className="space-y-3">
                  {Object.entries(entityTypeGroups).map(([type, entities]) => {
                    const color = ENTITY_COLORS[type] ?? ENTITY_COLORS.MISC
                    return (
                      <div key={type}>
                        <p className="text-[10px] font-semibold text-text-muted uppercase mb-1.5">{type}</p>
                        <div className="flex flex-wrap gap-1.5">
                          {entities.map((e) => (
                            <span
                              key={e.id}
                              className={`text-xs border rounded px-2 py-0.5 ${color}`}
                              title={`Confidence: ${Math.round(e.confidence * 100)}%`}
                            >
                              {e.entity_text}
                            </span>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-text-muted text-sm">Content not found</p>
          </div>
        )}
      </aside>
    </>
  )
}
