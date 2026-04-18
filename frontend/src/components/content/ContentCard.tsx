import { ContentItem } from '../../api/content'
import { CredibilityBadge } from './CredibilityBadge'
import { PlatformBadge } from './PlatformBadge'
import { Badge } from '../ui/Badge'
import { formatDistanceToNow } from 'date-fns'

interface ContentCardProps {
  item: ContentItem
  onClick: () => void
}

export function ContentCard({ item, onClick }: ContentCardProps) {
  const domain = (() => {
    try { return new URL(item.url).hostname.replace('www.', '') }
    catch { return item.url }
  })()

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
      </div>

      {/* Text preview — show translation when available */}
      <p className="text-sm text-text-primary line-clamp-3 group-hover:text-white transition-colors">
        {item.translated_text ?? item.clean_text}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 text-xs text-text-muted">
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
        <span>{formatDistanceToNow(new Date(item.captured_at), { addSuffix: true })}</span>
      </div>
    </article>
  )
}
