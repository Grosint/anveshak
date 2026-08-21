interface SentimentBadgeProps {
  compound: number
}

export function SentimentBadge({ compound }: SentimentBadgeProps) {
  const color =
    compound >= 0.05
      ? 'bg-cred-high/20 text-cred-high'
      : compound <= -0.05
      ? 'bg-signal-high/20 text-signal-high'
      : 'bg-anveshak-muted text-text-secondary'

  const label = compound >= 0.05 ? 'Positive' : compound <= -0.05 ? 'Negative' : 'Neutral'

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${color}`}
      title={`Sentiment: ${compound.toFixed(2)}`}
      aria-label={`Sentiment: ${label} (${compound.toFixed(2)})`}
    >
      {label} {Math.round(Math.abs(compound) * 100)}%
    </span>
  )
}
