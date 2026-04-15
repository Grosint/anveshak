interface CredibilityBadgeProps {
  score: number
  showValue?: boolean
}

export function CredibilityBadge({ score, showValue = true }: CredibilityBadgeProps) {
  const color =
    score >= 70
      ? 'bg-cred-high/20 text-cred-high'
      : score >= 40
      ? 'bg-cred-mid/20 text-cred-mid'
      : 'bg-cred-low/20 text-cred-low'

  const label = score >= 70 ? 'High' : score >= 40 ? 'Medium' : 'Low'

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${color}`}
      title={`Source credibility: ${score}/100`}
      aria-label={`Credibility: ${label} (${score})`}
    >
      {showValue ? score : label}
    </span>
  )
}
