import { SourceWarning } from '../../api/reports'

interface SourceWarningsBannerProps {
  warnings: SourceWarning[]
}

export function SourceWarningsBanner({ warnings }: SourceWarningsBannerProps) {
  // Defensive: asyncpg may return json_agg columns as a JSON string if the
  // connection pool has no JSON codec registered. Parse it if needed.
  const list: SourceWarning[] = Array.isArray(warnings)
    ? warnings
    : typeof warnings === 'string'
      ? (JSON.parse(warnings) as SourceWarning[])
      : []

  if (!list.length) return null

  return (
    <div
      role="alert"
      className="bg-signal-med/10 border border-signal-med/40 rounded-lg px-4 py-3 text-sm"
    >
      <div className="flex items-start gap-2">
        <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-signal-med shrink-0 mt-0.5" aria-hidden="true">
          <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
        </svg>
        <div>
          <p className="font-medium text-signal-med">Source credibility changed since report generation</p>
          <ul className="mt-1.5 space-y-1 text-xs text-text-secondary">
            {list.map((w) => (
              <li key={w.id}>
                <span className="font-medium">{w.source_name}</span>
                {' '}credibility changed: {w.old_score.toFixed(0)} → {w.new_score.toFixed(0)}
                {' '}({w.warning_type.replace(/_/g, ' ')})
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
