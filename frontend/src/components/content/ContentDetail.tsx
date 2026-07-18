/**
 * Slide-over panel for content item intelligence view.
 * Shows structured information: title, key entities, quality indicator,
 * and content text only when it's meaningful.
 */
import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { contentApi, Entity } from '../../api/content'
import { visionApi } from '../../api/vision'
import api from '../../api/client'
import { CredibilityBadge } from './CredibilityBadge'
import { PlatformBadge } from './PlatformBadge'
import { Badge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'
import { DeepfakeMeter } from '../vision/DeepfakeMeter'
import { format, formatDistanceToNow } from 'date-fns'

/** Fetch image via authenticated axios, render as blob URL */
function AuthImage({ src, alt, className }: { src: string; alt: string; className?: string }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  useEffect(() => {
    let revoke: string | null = null
    api.get(src, { responseType: 'blob' })
      .then((res) => {
        const url = URL.createObjectURL(res.data)
        revoke = url
        setBlobUrl(url)
      })
      .catch(() => setBlobUrl(null))
    return () => { if (revoke) URL.revokeObjectURL(revoke) }
  }, [src])
  if (!blobUrl) return null
  return <img src={blobUrl} alt={alt} className={className} />
}

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

  // Fetch vision data — returns empty array quickly if no media assets
  const { data: visionResults } = useQuery({
    queryKey: ['vision', contentId],
    queryFn: () => contentApi.getVision(contentId),
    enabled: !!contentId,
  })

  // pHash reverse search for the first vision result with a phash
  const firstPhash = visionResults?.find((v) => v.phash)?.phash ?? null
  const { data: pHashDuplicates } = useQuery({
    queryKey: ['phash-dupes', firstPhash],
    queryFn: () => visionApi.reverseSearch(firstPhash!, 10),
    enabled: !!firstPhash,
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

            {/* ── Media analysis (collapsible) ─────────────────────────── */}
            {visionResults && visionResults.length > 0 && (
              <details className="px-5 py-4 border-b border-anveshak-border/30">
                <summary className="text-[10px] font-bold text-text-muted uppercase tracking-widest cursor-pointer hover:text-text-secondary transition-colors flex items-center gap-2">
                  <span>📷 Media Analysis</span>
                  <span className="text-[9px] font-normal text-cyan-400">
                    {visionResults.length} asset{visionResults.length > 1 ? 's' : ''}
                  </span>
                </summary>

                <div className="mt-3 space-y-4">
                  {visionResults.map((vr) => (
                    <div key={vr.vision_result_id} className="space-y-3">
                      {/* Media thumbnail */}
                      {vr.asset_type === 'image' && (
                        <AuthImage
                          src={`/api/v1/content/media/${vr.media_asset_id}`}
                          alt="Analysed media"
                          className="w-full max-h-48 object-contain rounded border border-anveshak-border/30 bg-black/30"
                        />
                      )}

                      {/* Deepfake meter */}
                      {vr.deepfake_score != null && (
                        <DeepfakeMeter score={vr.deepfake_score} modelName={vr.deepfake_model} />
                      )}

                      {/* YOLO detection summary (text only, no canvas) */}
                      {vr.yolo_detections && vr.yolo_detections.length > 0 && (
                        <div>
                          <p className="text-[10px] font-semibold text-text-muted uppercase mb-1">
                            Objects Detected
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {vr.yolo_detections.map((d, i) => (
                              <span
                                key={i}
                                className="text-[10px] text-text-secondary bg-white/[0.04] border border-white/[0.08] rounded px-1.5 py-0.5"
                              >
                                {d.label || (d as unknown as Record<string, string>).class} {Math.round(d.confidence * 100)}%
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* CLIP labels */}
                      {vr.clip_labels && Object.keys(vr.clip_labels as Record<string, number>).length > 0 && (
                        <div>
                          <p className="text-[10px] font-semibold text-text-muted uppercase mb-1">
                            Content Classification
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {Object.entries(vr.clip_labels as Record<string, number>)
                              .sort(([, a], [, b]) => b - a)
                              .map(([label, score]) => (
                                <span
                                  key={label}
                                  className={`text-[10px] bg-white/[0.04] border rounded px-1.5 py-0.5 ${
                                    label === 'fabricated'
                                      ? 'text-red-400 border-red-500/30'
                                      : 'text-text-secondary border-white/[0.08]'
                                  }`}
                                >
                                  {label.replace(/_/g, ' ')} {Math.round(score * 100)}%
                                </span>
                              ))}
                          </div>
                        </div>
                      )}

                      {/* EXIF metadata / anomalies */}
                      {vr.exif_data && (
                        <div>
                          <p className="text-[10px] font-semibold text-text-muted uppercase mb-1">
                            EXIF Metadata
                          </p>
                          {(() => {
                            const exif = (typeof vr.exif_data === 'string' ? JSON.parse(vr.exif_data) : vr.exif_data) as Record<string, unknown>
                            return (
                              <div className="bg-white/[0.02] border border-white/[0.06] rounded p-2 space-y-1">
                                {'Software' in exif && (
                                  <p className="text-[10px] text-amber-400">
                                    <span className="text-text-muted">Software:</span> {String(exif.Software)}
                                  </p>
                                )}
                                {'GPS' in exif && (
                                  <p className="text-[10px] text-text-secondary">
                                    <span className="text-text-muted">GPS:</span> {String(exif.GPS)}
                                  </p>
                                )}
                                {'ImageDescription' in exif && (
                                  <p className="text-[10px] text-text-secondary">
                                    <span className="text-text-muted">Description:</span> {String(exif.ImageDescription)}
                                  </p>
                                )}
                                {Array.isArray(exif.anomalies) && (
                                  <div className="mt-1 pt-1 border-t border-white/[0.06]">
                                    <p className="text-[9px] font-semibold text-red-400 uppercase mb-0.5">Anomalies</p>
                                    {(exif.anomalies as string[]).map((a, i) => (
                                      <p key={i} className="text-[9px] text-red-300/80">⚠ {a}</p>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )
                          })()}
                        </div>
                      )}

                      {/* Processed timestamp */}
                      <p className="text-[9px] text-text-muted">
                        Analysed locally · {vr.processed_at && format(new Date(vr.processed_at), 'dd MMM yyyy, HH:mm')}
                      </p>
                    </div>
                  ))}

                  {/* pHash near-duplicates */}
                  {pHashDuplicates && pHashDuplicates.length > 1 && (
                    <div className="bg-cyan-500/[0.04] border border-cyan-500/15 rounded-md px-3 py-2">
                      <p className="text-[10px] font-semibold text-cyan-400">
                        This image also appears in {pHashDuplicates.length - 1} other content item{pHashDuplicates.length > 2 ? 's' : ''}
                      </p>
                      <div className="mt-1 space-y-0.5">
                        {pHashDuplicates
                          .filter((d) => d.content_item_id !== contentId)
                          .slice(0, 5)
                          .map((d) => (
                            <p key={d.media_asset_id} className="text-[9px] text-text-muted truncate">
                              {d.url || d.content_item_id} (distance: {d.hamming_distance})
                            </p>
                          ))}
                      </div>
                    </div>
                  )}

                  {/* Link to full analysis */}
                  <a
                    href="/image-analysis"
                    className="inline-block text-[10px] font-medium text-anveshak-accent hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    View full analysis →
                  </a>
                </div>
              </details>
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
