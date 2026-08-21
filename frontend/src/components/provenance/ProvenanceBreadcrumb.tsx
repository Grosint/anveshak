import type { ProvenanceStackEntry, ProvenanceEntityType } from '../../contexts/ProvenanceContext'

const TYPE_LABELS: Record<ProvenanceEntityType, string> = {
  identifier: 'Identifier',
  content: 'Content',
  source: 'Source',
  cluster: 'Cluster',
  signal: 'Signal',
}

const TYPE_COLORS: Record<ProvenanceEntityType, string> = {
  identifier: 'text-amber-400',
  content: 'text-blue-400',
  source: 'text-green-400',
  cluster: 'text-purple-400',
  signal: 'text-red-400',
}

interface ProvenanceBreadcrumbProps {
  stack: ProvenanceStackEntry[]
  onJumpTo: (index: number) => void
}

export function ProvenanceBreadcrumb({ stack, onJumpTo }: ProvenanceBreadcrumbProps) {
  if (stack.length === 0) return null

  return (
    <div className="flex items-center gap-1 text-[10px] overflow-x-auto scrollbar-none px-4 py-1.5 bg-white/[0.02] border-b border-anveshak-border/30">
      <span className="text-text-muted uppercase tracking-widest font-bold shrink-0">Trace</span>
      {stack.map((entry, i) => {
        const isLast = i === stack.length - 1
        const label = entry.label || entry.entityId.slice(0, 8)
        return (
          <span key={i} className="flex items-center gap-1 shrink-0">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3 text-text-muted/40">
              <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
            </svg>
            <button
              onClick={() => !isLast && onJumpTo(i)}
              className={`px-1.5 py-0.5 rounded transition-colors ${
                isLast
                  ? `font-bold ${TYPE_COLORS[entry.entityType]}`
                  : 'text-text-muted hover:text-text-primary hover:bg-white/[0.04] cursor-pointer'
              }`}
              disabled={isLast}
            >
              <span className="opacity-60">{TYPE_LABELS[entry.entityType]}</span>
              {' '}
              <span className="max-w-[120px] truncate inline-block align-bottom">{label}</span>
            </button>
          </span>
        )
      })}
    </div>
  )
}
