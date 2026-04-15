import { ReactNode } from 'react'

type Variant = 'default' | 'accent' | 'success' | 'warning' | 'danger' | 'ghost'

const variantClasses: Record<Variant, string> = {
  default:  'bg-anveshak-muted text-text-secondary',
  accent:   'bg-anveshak-accent/20 text-anveshak-accent',
  success:  'bg-cred-high/20 text-cred-high',
  warning:  'bg-signal-med/20 text-signal-med',
  danger:   'bg-signal-high/20 text-signal-high',
  ghost:    'border border-anveshak-border text-text-secondary',
}

interface BadgeProps {
  variant?: Variant
  children: ReactNode
  className?: string
}

export function Badge({ variant = 'default', children, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  )
}
