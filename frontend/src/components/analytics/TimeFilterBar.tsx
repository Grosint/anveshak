interface TimeFilterBarProps {
  days: number
  onChange: (days: number) => void
}

const PRESETS = [
  { label: '7d', value: 7 },
  { label: '30d', value: 30 },
  { label: '90d', value: 90 },
]

export function TimeFilterBar({ days, onChange }: TimeFilterBarProps) {
  return (
    <div className="flex gap-1.5" role="group" aria-label="Time range">
      {PRESETS.map((p) => (
        <button
          key={p.value}
          onClick={() => onChange(p.value)}
          aria-pressed={days === p.value}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
            days === p.value
              ? 'bg-anveshak-accent text-white'
              : 'bg-anveshak-muted text-text-secondary hover:text-text-primary'
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}
