import type { IntelLocation } from '../../api/intelligence'

interface LocationPillsProps {
  locations: IntelLocation[]
  onSelectLocation: (location: IntelLocation) => void
  onOpenMap?: () => void
}

export function LocationPills({ locations, onSelectLocation, onOpenMap }: LocationPillsProps) {
  if (locations.length === 0) return null

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[11px] font-bold text-text-muted uppercase tracking-widest">
          Locations
        </h2>
        {onOpenMap && (
          <button onClick={onOpenMap} className="text-[10px] text-anveshak-accent hover:underline">
            Open Map →
          </button>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {locations.map((loc) => (
          <button
            key={`${loc.location_name}-${loc.latitude}-${loc.longitude}`}
            onClick={() => onSelectLocation(loc)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-anveshak-card border border-anveshak-border rounded-full text-xs hover:border-anveshak-accent/40 transition-colors"
          >
            <span className="text-[13px]">📍</span>
            <span className="text-text-primary">{loc.location_name}</span>
            <span className="text-text-muted font-mono">({loc.content_count})</span>
          </button>
        ))}
      </div>
    </section>
  )
}
