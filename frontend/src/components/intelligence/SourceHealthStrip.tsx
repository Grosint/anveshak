import type { IntelSourceHealth } from '../../api/intelligence'

const STATUS_COLORS: Record<string, string> = {
  healthy: 'bg-cred-high',
  degraded: 'bg-signal-med',
  down: 'bg-signal-high',
  unverified: 'bg-text-muted',
}

interface SourceHealthStripProps {
  sources: IntelSourceHealth[]
  onManage?: () => void
}

export function SourceHealthStrip({ sources, onManage }: SourceHealthStripProps) {
  if (sources.length === 0) return null

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[11px] font-bold text-text-muted uppercase tracking-widest">
          Sources
        </h2>
        {onManage && (
          <button
            onClick={onManage}
            className="text-text-muted hover:text-text-primary transition-colors"
            aria-label="Manage sources"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path fillRule="evenodd" d="M7.84 1.804A1 1 0 018.82 1h2.36a1 1 0 01.98.804l.331 1.652a6.993 6.993 0 011.929 1.115l1.598-.54a1 1 0 011.186.447l1.18 2.044a1 1 0 01-.205 1.251l-1.267 1.113a7.047 7.047 0 010 2.228l1.267 1.113a1 1 0 01.206 1.25l-1.18 2.045a1 1 0 01-1.187.447l-1.598-.54a6.993 6.993 0 01-1.929 1.115l-.33 1.652a1 1 0 01-.98.804H8.82a1 1 0 01-.98-.804l-.331-1.652a6.993 6.993 0 01-1.929-1.115l-1.598.54a1 1 0 01-1.186-.447l-1.18-2.044a1 1 0 01.205-1.251l1.267-1.114a7.05 7.05 0 010-2.227L1.821 7.773a1 1 0 01-.206-1.25l1.18-2.045a1 1 0 011.187-.447l1.598.54A6.993 6.993 0 017.51 3.456l.33-1.652zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
            </svg>
          </button>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {sources.map((src) => (
          <div
            key={src.id}
            className="group relative"
            title={`${src.name} — ${src.platform.toUpperCase()} · ${src.health_status} · cred ${Math.round(src.credibility_score)}`}
          >
            <span
              className={`block w-3 h-3 rounded-full cursor-default ${STATUS_COLORS[src.health_status] ?? STATUS_COLORS.unverified}`}
            />
            {/* Tooltip on hover */}
            <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-1 bg-anveshak-card border border-anveshak-border rounded text-[10px] text-text-primary whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
              {src.name}
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}
