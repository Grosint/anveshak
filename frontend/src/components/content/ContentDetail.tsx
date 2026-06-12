/**
 * Slide-over panel for content item intelligence view.
 * Shows structured information: title, key entities, quality indicator,
 * and content text only when it's meaningful.
 */
import { useQuery } from '@tanstack/react-query'
import { contentApi, Entity } from '../../api/content'
import { CredibilityBadge } from './CredibilityBadge'
import { PlatformBadge } from './PlatformBadge'
import { Badge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'
import { format, formatDistanceToNow } from 'date-fns'

// ── Entity color map ───────────────────────────────────────────────────

const ENTITY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  PERSON: { bg: 'bg-purple-500/15', text: 'text-purple-300', border: 'border-purple-500/25' },
  ORG:    { bg: 'bg-blue-500/15',   text: 'text-blue-300',   border: 'border-blue-500/25'   },
  GPE:    { bg: 'bg-green-500/15',  text: 'text-green-300',  border: 'border-green-500/25'  },
  LOC:    { bg: 'bg-teal-500/15',   text: 'text-teal-300',   border: 'border-teal-500/25'   },
  WEAPON: { bg: 'bg-red-500/15',    text: 'text-red-300',    border: 'border-red-500/25'    },
  EVENT:  { bg: 'bg-amber-500/15',  text: 'text-amber-300',  border: 'border-amber-500/25'  },
  MISC:   { bg: 'bg-slate-500/15',  text: 'text-slate-300',  border: 'border-slate-500/25'  },
}

const ENTITY_LABELS: Record<string, string> = {
  PERSON: 'People',
  ORG: 'Organisations',
  GPE: 'Countries & Cities',
  LOC: 'Locations',
  WEAPON: 'Weapons & Systems',
  EVENT: 'Events',
  MISC: 'Other',
}

// ── Helpers ─────────────────────────────────────────────────────────────

/** Deduplicate entities by text, keep highest confidence */
function dedupeEntities(entities: Entity[]): Entity[] {
  const map = new Map<string, Entity>()
  for (const e of entities) {
    const key = `${e.entity_type}:${e.entity_text.toLowerCase()}`
    const existing = map.get(key)
    if (!existing || e.confidence > existing.confidence) {
      map.set(key, e)
    }
  }
  return Array.from(map.values())
}

/** Check if content text looks like garbage (nav menus, boilerplate) */
function isGarbageContent(text: string): boolean {
  if (!text || text.length < 50) return true
  // High ratio of short lines = nav menu
  const lines = text.split('\n').filter((l) => l.trim())
  const shortLines = lines.filter((l) => l.trim().length < 20)
  if (lines.length > 5 && shortLines.length / lines.length > 0.6) return true
  return false
}

/** Extract domain from URL */
function extractDomain(url: string): string {
  try { return new URL(url).hostname.replace('www.', '') }
  catch { return url }
}

// ── Component ──────────────────────────────────────────────────────────

interface ContentDetailProps {
  contentId: string
  onClose: () => void
}

export function ContentDetail({ contentId, onClose }: ContentDetailProps) {
  const { data: item, isLoading } = useQuery({
    queryKey: ['content', contentId],
    queryFn: () => contentApi.get(contentId),
  })

  // Group and dedupe entities
  const allEntities = dedupeEntities(item?.extracted_entities ?? [])
  const entityGroups = allEntities.reduce<Record<string, Entity[]>>(
    (acc, e) => { (acc[e.entity_type] ??= []).push(e); return acc },
    {},
  )

  // Sort entity groups by importance
  const groupOrder = ['GPE', 'ORG', 'PERSON', 'WEAPON', 'EVENT', 'LOC', 'MISC']
  const sortedGroups = groupOrder
    .filter((type) => entityGroups[type]?.length)
    .map((type) => ({ type, entities: entityGroups[type] }))

  const displayText = item?.translated_text ?? item?.clean_text ?? ''
  const isGarbage = isGarbageContent(displayText)
  const title = item?.title
  const domain = item?.url ? extractDomain(item.url) : null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside
        className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-lg bg-[#0b1222] border-l border-anveshak-border/50 shadow-2xl flex flex-col animate-fade-in"
        aria-label="Content detail"
        role="complementary"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-anveshak-border/50 bg-[#0f1729]">
          <h2 className="font-semibold text-text-primary text-sm">Intelligence Detail</h2>
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
            <Spinner label="Loading…" />
          </div>
        ) : item ? (
          <div className="flex-1 overflow-y-auto">
            {/* ── Source card ──────────────────────────────────────────── */}
            <div className="px-5 py-4 border-b border-anveshak-border/30">
              <div className="flex items-center gap-2 mb-2">
                {item.platform && <PlatformBadge platform={item.platform} />}
                <CredibilityBadge score={item.credibility_score_at_capture} />
                {item.language && item.language !== 'en' && (
                  <Badge variant="ghost">{item.language.toUpperCase()}</Badge>
                )}
                {item.translated_text && (
                  <Badge variant="warning" className="text-[9px]">Translated</Badge>
                )}
              </div>

              {item.source_name && (
                <p className="text-sm font-semibold text-text-primary">{item.source_name}</p>
              )}

              {domain && (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-anveshak-accent hover:underline"
                >
                  {domain}
                </a>
              )}

              <p className="text-[11px] text-text-muted mt-1">
                {item.captured_at && (
                  <>
                    {format(new Date(item.captured_at), 'dd MMM yyyy, HH:mm')}
                    <span className="mx-1.5 text-anveshak-border">·</span>
                    {formatDistanceToNow(new Date(item.captured_at), { addSuffix: true })}
                  </>
                )}
              </p>
            </div>

            {/* ── Scam template match (Engine C) ────────────────────── */}
            {item.scam_template && (
              <div className="px-5 py-3 border-b border-anveshak-border/30 bg-red-500/[0.03]">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-text-muted uppercase tracking-widest">
                    Template Match
                  </span>
                  <span className="text-[11px] font-semibold text-red-400 bg-red-500/15 border border-red-500/25 rounded-md px-2 py-0.5">
                    {item.scam_template.replace(/_/g, ' ')}
                  </span>
                  {item.template_confidence != null && (
                    <span className="text-[10px] font-mono text-text-muted">
                      {Math.round(item.template_confidence * 100)}% confidence
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* ── Key entities (the intelligence) ─────────────────────── */}
            {sortedGroups.length > 0 && (
              <div className="px-5 py-4 border-b border-anveshak-border/30">
                <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-3">
                  Key Entities
                </h3>
                <div className="space-y-3">
                  {sortedGroups.map(({ type, entities }) => {
                    const colors = ENTITY_COLORS[type] ?? ENTITY_COLORS.MISC
                    return (
                      <div key={type}>
                        <p className="text-[9px] font-semibold text-text-muted/60 uppercase tracking-wider mb-1.5">
                          {ENTITY_LABELS[type] ?? type}
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {entities
                            .sort((a, b) => b.confidence - a.confidence)
                            .map((e) => (
                            <span
                              key={e.id}
                              className={`inline-flex items-center gap-1 text-[11px] border rounded-md px-2 py-0.5 ${colors.bg} ${colors.text} ${colors.border}`}
                            >
                              {e.entity_text}
                              <span className="text-[8px] opacity-50">{Math.round(e.confidence * 100)}%</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* ── Content text ─────────────────────────────────────────── */}
            <div className="px-5 py-4">
              <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-3">
                {title ? 'Article Content' : 'Extracted Text'}
              </h3>

              {/* Title if available */}
              {title && (
                <p className="text-sm font-semibold text-text-primary leading-snug mb-2">
                  {title}
                </p>
              )}

              {/* Quality warning for garbage content */}
              {isGarbage && (
                <div className="rounded-md bg-amber-500/10 border border-amber-500/20 px-3 py-2 mb-3">
                  <p className="text-[11px] text-amber-400">
                    Low quality extraction — this page appears to be a navigation or index page rather than an article. Content may not be meaningful.
                  </p>
                </div>
              )}

              {/* Text content — limited and styled */}
              <div className="text-[12px] text-text-secondary/80 leading-relaxed whitespace-pre-wrap max-h-[40vh] overflow-y-auto pr-2">
                {displayText.length > 2000
                  ? displayText.slice(0, 2000) + '…'
                  : displayText}
              </div>

              {/* Original text (collapsible) when translated */}
              {item.translated_text && (
                <details className="mt-3">
                  <summary className="text-[10px] font-semibold text-text-muted uppercase tracking-wider cursor-pointer hover:text-text-secondary transition-colors">
                    View Original ({item.language?.toUpperCase()})
                  </summary>
                  <p className="text-[12px] text-text-secondary/60 leading-relaxed whitespace-pre-wrap mt-2">
                    {item.clean_text}
                  </p>
                </details>
              )}
            </div>
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
