import { credibilityLabel } from '../../lib/domain'

interface CredibilityBadgeProps {
  score: number
  showValue?: boolean
}

export function CredibilityBadge({ score, showValue = true }: CredibilityBadgeProps) {
  const { label, color } = credibilityLabel(score)

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
