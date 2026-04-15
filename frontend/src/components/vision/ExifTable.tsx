/**
 * EXIF metadata table. Flags anomalous fields:
 * - Missing GPS (expected for outdoor imagery)
 * - AI-generation software tags
 */

const AI_SOFTWARE_PATTERNS = ['stable diffusion', 'dall-e', 'midjourney', 'firefly', 'imagen']

function isAiSoftware(val: string): boolean {
  const lower = String(val).toLowerCase()
  return AI_SOFTWARE_PATTERNS.some((p) => lower.includes(p))
}

function anomalyHint(key: string, val: unknown): string | null {
  const k = key.toLowerCase()
  if ((k === 'software' || k === 'make' || k === 'model') && isAiSoftware(String(val))) {
    return 'AI-generation tool detected'
  }
  return null
}

interface ExifTableProps {
  exif: Record<string, unknown>
}

export function ExifTable({ exif }: ExifTableProps) {
  const hasGPS = Object.keys(exif).some((k) => k.toLowerCase().includes('gps'))
  const entries = Object.entries(exif).slice(0, 30) // cap display

  if (entries.length === 0) {
    return <p className="text-sm text-text-muted">No EXIF metadata available.</p>
  }

  return (
    <div className="space-y-2">
      {!hasGPS && (
        <div className="bg-signal-med/10 border border-signal-med/30 rounded px-3 py-2 text-xs text-signal-med">
          ⚠ GPS data absent — location stripped or camera not GPS-equipped
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-xs" aria-label="EXIF metadata">
          <thead>
            <tr className="border-b border-anveshak-border">
              <th className="text-left py-2 pr-4 font-medium text-text-muted w-1/3">Field</th>
              <th className="text-left py-2 font-medium text-text-muted">Value</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([key, val]) => {
              const hint = anomalyHint(key, val)
              return (
                <tr key={key} className={`border-b border-anveshak-border/50 ${hint ? 'bg-signal-high/5' : ''}`}>
                  <td className="py-1.5 pr-4 text-text-muted font-mono">{key}</td>
                  <td className="py-1.5 text-text-primary">
                    {String(val)}
                    {hint && (
                      <span className="ml-2 text-signal-high text-[10px]">⚑ {hint}</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
