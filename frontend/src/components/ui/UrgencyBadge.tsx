import type { HealthStatus } from '../../lib/domain'

const healthConfig: Record<HealthStatus, { dot: string; label: string }> = {
  healthy:  { dot: 'bg-cred-high',   label: 'Sources healthy' },
  degraded: { dot: 'bg-signal-med',  label: 'Sources degraded' },
  down:     { dot: 'bg-signal-high', label: 'Sources down' },
}

interface SourceHealthDotProps {
  status: HealthStatus
}

export function SourceHealthDot({ status }: SourceHealthDotProps) {
  const { dot, label } = healthConfig[status]
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full ${dot}`}
      title={label}
      aria-label={label}
    />
  )
}

interface SignalBadgeProps {
  count: number
}

export function SignalBadge({ count }: SignalBadgeProps) {
  if (count <= 0) return null
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-bold bg-signal-high/20 text-signal-high"
      aria-label={`${count} unacknowledged signal${count === 1 ? '' : 's'}`}
    >
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-signal-high animate-pulse" aria-hidden="true" />
      {count}
    </span>
  )
}

interface NewContentBadgeProps {
  count: number
}

export function NewContentBadge({ count }: NewContentBadgeProps) {
  if (count <= 0) return null
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-anveshak-accent/15 text-anveshak-accent"
      aria-label={`${count} new item${count === 1 ? '' : 's'} in last 24h`}
    >
      +{count} new
    </span>
  )
}
