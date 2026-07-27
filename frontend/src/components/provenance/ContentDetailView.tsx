import { useQuery } from '@tanstack/react-query'
import { provenanceApi } from '../../api/provenance'
import { useProvenance } from '../../contexts/ProvenanceContext'
import { Spinner } from '../ui/Spinner'
import { Badge } from '../ui/Badge'
import { EmptyState } from '../ui/EmptyState'
import { CredibilityBadge } from '../content/CredibilityBadge'
import { PlatformBadge } from '../content/PlatformBadge'
import { DeepfakeMeter } from '../vision/DeepfakeMeter'
import { ExifTable } from '../vision/ExifTable'
import { format, formatDistanceToNow } from 'date-fns'

const ENTITY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  PERSON: { bg: 'bg-purple-500/15', text: 'text-purple-300', border: 'border-purple-500/25' },
  ORG:    { bg: 'bg-blue-500/15',   text: 'text-blue-300',   border: 'border-blue-500/25'   },
  GPE:    { bg: 'bg-green-500/15',  text: 'text-green-300',  border: 'border-green-500/25'  },
  LOC:    { bg: 'bg-teal-500/15',   text: 'text-teal-300',   border: 'border-teal-500/25'   },
  MISC:   { bg: 'bg-slate-500/15',  text: 'text-slate-300',  border: 'border-slate-500/25'  },
}

const IDENTIFIER_TYPES = new Set([
  'PHONE_IN', 'PHONE_INTL', 'UPI', 'EMAIL', 'CRYPTO_BTC', 'CRYPTO_ETH',
  'CRYPTO_TRC20', 'TELEGRAM_HANDLE', 'INSTAGRAM_HANDLE', 'FACEBOOK_HANDLE',
  'X_HANDLE', 'URL_DOMAIN', 'GSTIN', 'UDYAM', 'PAN', 'IFSC',
  'BANK_ACCOUNT', 'SEBI_REG', 'AIRCRAFT_ID',
])

interface ContentDetailViewProps {
  contentId: string
}

export default function ContentDetailView({ contentId }: ContentDetailViewProps) {
  const { push } = useProvenance()

  const { data, isLoading } = useQuery({
    queryKey: ['provenance', 'content', contentId],
    queryFn: () => provenanceApi.contentProvenance(contentId),
    enabled: !!contentId,
  })

  if (isLoading) return <div className="p-4"><Spinner label="Loading content..." /></div>
  if (!data) return <EmptyState icon="📄" title="Not found" description="Content item not found." />

  const displayText = data.translated_text ?? data.clean_text ?? ''
  const identifiers = data.identifiers.filter((e) => IDENTIFIER_TYPES.has(e.entity_type))
  const entities = data.identifiers.filter((e) => !IDENTIFIER_TYPES.has(e.entity_type))
  const topicId = data.topic_id

  // Group entities by type
  const entityGroups: Record<string, typeof entities> = {}
  for (const e of entities) {
    ;(entityGroups[e.entity_type] ??= []).push(e)
  }

  return (
    <div className="divide-y divide-anveshak-border/30">
      {/* Source card */}
      <div className="px-4 py-3">
        <div className="flex items-center gap-2 mb-2">
          {data.source.platform && <PlatformBadge platform={data.source.platform} />}
          <CredibilityBadge score={data.credibility_score_at_capture} />
          {data.language && data.language !== 'en' && (
            <Badge variant="ghost">{data.language.toUpperCase()}</Badge>
          )}
        </div>

        {data.source.name && (
          <button
            className="text-sm font-semibold text-text-primary hover:text-anveshak-accent transition-colors"
            onClick={() => data.source.id && push({ entityType: 'source', entityId: data.source.id, topicId, label: data.source.name ?? undefined })}
          >
            {data.source.name} →
          </button>
        )}

        <p className="text-[11px] text-text-muted mt-1">
          {data.captured_at && (
            <>
              {format(new Date(data.captured_at), 'dd MMM yyyy, HH:mm')}
              <span className="mx-1.5 text-anveshak-border">·</span>
              {formatDistanceToNow(new Date(data.captured_at), { addSuffix: true })}
            </>
          )}
        </p>
      </div>

      {/* Cluster membership */}
      {data.cluster && (
        <div className="px-4 py-3">
          <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">Narrative Cluster</h3>
          <button
            className="w-full flex items-center justify-between text-left p-2 bg-anveshak-card/50 border border-anveshak-border rounded hover:border-anveshak-accent/40 transition-colors"
            onClick={() => data.narrative_cluster_id && push({
              entityType: 'cluster',
              entityId: data.narrative_cluster_id,
              topicId,
              label: data.cluster?.label || 'Unclassified',
            })}
          >
            <span className="text-[11px] text-text-primary truncate">{data.cluster.label || 'Unclassified'}</span>
            {data.cluster.isc != null && (
              <span className="text-[9px] text-text-muted shrink-0">{data.cluster.isc} ISC</span>
            )}
          </button>
        </div>
      )}

      {/* Extracted identifiers — clickable */}
      {identifiers.length > 0 && (
        <div className="px-4 py-3">
          <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">
            Identifiers ({identifiers.length})
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {identifiers.map((id, i) => (
              <button
                key={i}
                className="text-[10px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-md px-2 py-0.5 hover:bg-amber-500/20 transition-colors"
                onClick={() => push({ entityType: 'identifier', entityId: id.entity_text, topicId, label: id.entity_text })}
              >
                <span className="text-[8px] text-text-muted mr-1">{id.entity_type}</span>
                {id.entity_text}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Key entities (non-identifier NER) */}
      {Object.keys(entityGroups).length > 0 && (
        <div className="px-4 py-3">
          <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">Key Entities</h3>
          <div className="space-y-2">
            {Object.entries(entityGroups).map(([type, ents]) => {
              const colors = ENTITY_COLORS[type] ?? ENTITY_COLORS.MISC
              return (
                <div key={type}>
                  <p className="text-[9px] font-semibold text-text-muted/60 uppercase tracking-wider mb-1">{type}</p>
                  <div className="flex flex-wrap gap-1">
                    {ents.sort((a, b) => b.confidence - a.confidence).map((e, i) => (
                      <span
                        key={i}
                        className={`text-[10px] border rounded-md px-1.5 py-0.5 ${colors.bg} ${colors.text} ${colors.border}`}
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

      {/* Vision results */}
      {data.vision_results.length > 0 && (
        <div className="px-4 py-3">
          <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">
            Media Analysis ({data.vision_results.length})
          </h3>
          <div className="space-y-3">
            {data.vision_results.map((vr, i) => (
              <div key={i} className="space-y-2">
                {vr.deepfake_score != null && (
                  <DeepfakeMeter score={vr.deepfake_score} modelName={vr.deepfake_model} />
                )}
                {vr.yolo_detections && vr.yolo_detections.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {vr.yolo_detections.map((d, j) => (
                      <span key={j} className="text-[9px] text-text-secondary bg-white/[0.04] border border-white/[0.08] rounded px-1.5 py-0.5">
                        {d.label || d.class} {Math.round(d.confidence * 100)}%
                      </span>
                    ))}
                  </div>
                )}
                {vr.clip_labels && Object.keys(vr.clip_labels).length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(vr.clip_labels).sort(([, a], [, b]) => b - a).map(([label, score]) => (
                      <span key={label} className="text-[9px] text-text-secondary bg-white/[0.04] border border-white/[0.08] rounded px-1.5 py-0.5">
                        {label.replace(/_/g, ' ')} {Math.round(score * 100)}%
                      </span>
                    ))}
                  </div>
                )}
                {vr.exif_data && Object.keys(vr.exif_data).length > 0 && (
                  <div>
                    <p className="text-[9px] font-semibold text-text-muted/60 uppercase tracking-wider mb-1">EXIF Metadata</p>
                    <ExifTable exif={vr.exif_data} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Content text */}
      <div className="px-4 py-3">
        <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">Content</h3>
        <div className="text-[11px] text-text-secondary/80 leading-relaxed whitespace-pre-wrap max-h-[30vh] overflow-y-auto">
          {displayText.length > 2000 ? displayText.slice(0, 2000) + '…' : displayText}
        </div>
      </div>
    </div>
  )
}
