import { ContentFilters } from '../../api/content'

interface FilterBarProps {
  filters: ContentFilters
  onChange: (filters: ContentFilters) => void
  clusterView: boolean
  onToggleCluster: () => void
}

const LANGUAGES = [
  { code: '', label: 'All languages' },
  { code: 'en', label: 'EN' },
  { code: 'ru', label: 'RU' },
  { code: 'zh', label: 'ZH' },
  { code: 'hi', label: 'HI' },
  { code: 'ar', label: 'AR' },
]

export function FilterBar({ filters, onChange, clusterView, onToggleCluster }: FilterBarProps) {
  return (
    <div className="flex items-center gap-3 flex-wrap py-3 px-6 border-b border-anveshak-border bg-anveshak-bg/50">
      {/* Language */}
      <select
        value={filters.language ?? ''}
        onChange={(e) => onChange({ ...filters, language: e.target.value || undefined })}
        className="bg-anveshak-card border border-anveshak-border rounded px-2 py-1.5 text-xs text-text-primary focus:outline-none focus:border-anveshak-accent"
        aria-label="Filter by language"
      >
        {LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>{l.label}</option>
        ))}
      </select>

      {/* Min credibility */}
      <div className="flex items-center gap-1.5">
        <label htmlFor="cred-filter" className="text-xs text-text-muted">Cred ≥</label>
        <input
          id="cred-filter"
          type="number"
          min={0}
          max={100}
          value={filters.credibility_min ?? ''}
          onChange={(e) =>
            onChange({
              ...filters,
              credibility_min: e.target.value ? Number(e.target.value) : undefined,
            })
          }
          placeholder="0"
          className="w-14 bg-anveshak-card border border-anveshak-border rounded px-2 py-1.5 text-xs text-text-primary focus:outline-none focus:border-anveshak-accent"
          aria-label="Minimum credibility score"
        />
      </div>

      {/* Date range */}
      <div className="flex items-center gap-1.5">
        <label htmlFor="date-from" className="text-xs text-text-muted">From</label>
        <input
          id="date-from"
          type="date"
          value={filters.date_from ?? ''}
          onChange={(e) => onChange({ ...filters, date_from: e.target.value || undefined })}
          className="bg-anveshak-card border border-anveshak-border rounded px-2 py-1.5 text-xs text-text-primary focus:outline-none focus:border-anveshak-accent"
          aria-label="From date"
        />
        <label htmlFor="date-to" className="text-xs text-text-muted">To</label>
        <input
          id="date-to"
          type="date"
          value={filters.date_to ?? ''}
          onChange={(e) => onChange({ ...filters, date_to: e.target.value || undefined })}
          className="bg-anveshak-card border border-anveshak-border rounded px-2 py-1.5 text-xs text-text-primary focus:outline-none focus:border-anveshak-accent"
          aria-label="To date"
        />
      </div>

      {/* Clear */}
      {(filters.language || filters.credibility_min || filters.date_from || filters.date_to) && (
        <button
          onClick={() => onChange({})}
          className="text-xs text-signal-high hover:underline"
          aria-label="Clear all filters"
        >
          Clear filters
        </button>
      )}

      <div className="ml-auto">
        <button
          onClick={onToggleCluster}
          className={`px-3 py-1.5 rounded text-xs font-medium border transition-colors ${
            clusterView
              ? 'bg-anveshak-accent/20 text-anveshak-accent border-anveshak-accent/40'
              : 'border-anveshak-border text-text-muted hover:text-text-primary'
          }`}
          aria-pressed={clusterView}
        >
          Cluster view
        </button>
      </div>
    </div>
  )
}
