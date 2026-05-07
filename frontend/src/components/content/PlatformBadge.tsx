const PLATFORM_CONFIG: Record<string, { label: string; color: string }> = {
  telegram: { label: 'Telegram', color: 'text-sky-400 bg-sky-400/10' },
  reddit:   { label: 'Reddit',   color: 'text-orange-400 bg-orange-400/10' },
  twitter:  { label: 'X/Twitter', color: 'text-text-secondary bg-anveshak-muted' },
  bluesky:  { label: 'Bluesky',  color: 'text-blue-400 bg-blue-400/10' },
  web:      { label: 'Web',      color: 'text-green-400 bg-green-400/10' },
  rss:      { label: 'RSS',      color: 'text-amber-400 bg-amber-400/10' },
  upload:   { label: 'Upload',   color: 'text-purple-400 bg-purple-400/10' },
  darkweb:  { label: 'Dark Web', color: 'text-red-400 bg-red-400/10' },
}

interface PlatformBadgeProps {
  platform: string
}

export function PlatformBadge({ platform }: PlatformBadgeProps) {
  const cfg = PLATFORM_CONFIG[platform.toLowerCase()] ?? { label: platform, color: 'text-text-muted bg-anveshak-muted' }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cfg.color}`}>
      {cfg.label}
    </span>
  )
}
