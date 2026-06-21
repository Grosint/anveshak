import { useState } from 'react'
import { ContentItem } from '../../api/content'
import { CredibilityBadge } from './CredibilityBadge'
import { SentimentBadge } from './SentimentBadge'
import { PlatformBadge } from './PlatformBadge'
import { Badge } from '../ui/Badge'
import { formatDistanceToNow } from 'date-fns'
import { visionApi } from '../../api/vision'

interface ContentCardProps {
  item: ContentItem
  onClick: () => void
}

export function ContentCard({ item, onClick }: ContentCardProps) {
  const [analyseStatus, setAnalyseStatus] = useState<'idle' | 'loading' | 'queued' | 'error'>('idle')

  const domain = (() => {
    try { return new URL(item.url).hostname.replace('www.', '') }
    catch { return item.url }
  })()

  const isYouTubeVideo = item.platform === 'youtube' && item.url?.includes('youtube.com/watch')

  const handleAnalyseVideo = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setAnalyseStatus('loading')
    try {
      await visionApi.analyseYoutubeVideo(item.url, item.id)
      setAnalyseStatus('queued')
    } catch {
      setAnalyseStatus('error')
    }
  }

  const displayTitle = item.title || (item.translated_text ?? item.clean_text)
  const displayBody = item.title ? (item.translated_text ?? item.clean_text) : null
  const dupCount = (item.duplicate_count ?? 1) - 1

  return (
    <article
      className="bg-anveshak-card border border-anveshak-border rounded-lg p-4 hover:border-anveshak-accent/40 hover:shadow-card-hover transition-all cursor-pointer group animate-fade-in"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      aria-label={`Content from ${domain}`}
    >
      {/* Top row: badges */}
      <div className="flex items-center gap-2 flex-wrap mb-2">
        {item.platform && <PlatformBadge platform={item.platform} />}
        <CredibilityBadge score={item.credibility_score_at_capture} />
        {item.sentiment && <SentimentBadge compound={item.sentiment.compound} />}
        {item.language && item.language !== 'en' && (
          <Badge variant="ghost">{item.language.toUpperCase()}</Badge>
        )}
        {item.translated_text && (
          <span className="text-[10px] font-medium text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded px-1.5 py-0.5">
            Translated
          </span>
        )}
        {item.backfilled && (
          <Badge variant="default" className="text-[10px]">backfill</Badge>
        )}
        {dupCount > 0 && (
          <Badge variant="ghost" className="text-[10px]">
            +{dupCount} duplicate{dupCount > 1 ? 's' : ''}
          </Badge>
        )}
        {item.scam_template && (
          <span className="text-[10px] font-medium text-red-400 bg-red-500/10 border border-red-500/20 rounded px-1.5 py-0.5">
            {item.scam_template.replace(/_/g, ' ')}
            {item.template_confidence != null && ` ${Math.round(item.template_confidence * 100)}%`}
          </span>
        )}
        {item.topic_relevance_score != null && (
          <span className="text-[10px] font-mono font-medium text-anveshak-accent/80 bg-anveshak-accent/10 border border-anveshak-accent/20 rounded px-1.5 py-0.5">
            {Math.round(item.topic_relevance_score * 100)}% match
          </span>
        )}
      </div>

      {/* Title — primary display */}
      <p className="text-sm text-text-primary font-medium line-clamp-2 group-hover:text-white transition-colors">
        {displayTitle}
      </p>

      {/* Body excerpt — secondary, only shown when title is available */}
      {displayBody && (
        <p className="text-xs text-text-muted mt-1 line-clamp-2">
          {displayBody}
        </p>
      )}

      {/* Keywords */}
      {item.keywords && item.keywords.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap mt-1.5">
          {item.keywords.slice(0, 5).map((kw) => (
            <span
              key={kw}
              className="text-[9px] text-text-muted bg-white/[0.04] border border-white/[0.06] rounded px-1.5 py-0.5"
            >
              {kw}
            </span>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 text-xs text-text-muted">
        <div className="flex items-center gap-2">
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="truncate max-w-[200px] hover:text-anveshak-accent transition-colors"
            aria-label={`Open source: ${domain}`}
          >
            {domain}
          </a>
          {isYouTubeVideo && (
            <button
              onClick={handleAnalyseVideo}
              disabled={analyseStatus !== 'idle'}
              className="text-[10px] font-medium px-2 py-0.5 rounded border transition-colors disabled:opacity-50
                text-anveshak-accent border-anveshak-accent/30 hover:bg-anveshak-accent/10"
            >
              {analyseStatus === 'idle' && 'Analyse Video'}
              {analyseStatus === 'loading' && 'Submitting...'}
              {analyseStatus === 'queued' && 'Queued'}
              {analyseStatus === 'error' && 'Failed'}
            </button>
          )}
        </div>
        <span>{formatDistanceToNow(new Date(item.captured_at), { addSuffix: true })}</span>
      </div>
    </article>
  )
}
