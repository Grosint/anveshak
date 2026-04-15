/**
 * Semicircular SVG gauge for deepfake probability score (0.0–1.0).
 * Green < 0.3 · Amber 0.3–0.7 · Red > 0.7
 */
interface DeepfakeMeterProps {
  score: number // 0.0–1.0
  modelName?: string | null
}

export function DeepfakeMeter({ score, modelName }: DeepfakeMeterProps) {
  const pct = Math.max(0, Math.min(1, score))
  const percent = Math.round(pct * 100)

  // SVG arc: half-circle (180°) inside a 120×70 viewBox
  const R = 50
  const cx = 60
  const cy = 60
  const startAngle = Math.PI        // 180° (left)
  const angle = startAngle - pct * Math.PI // fills left→right

  const arcX = cx + R * Math.cos(angle)
  const arcY = cy + R * Math.sin(angle)

  // Arc path: always large-arc=0 because pct ≤ 1
  const trackD = `M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${cx + R} ${cy}`
  const fillD  = pct === 0
    ? ''
    : `M ${cx - R} ${cy} A ${R} ${R} 0 ${pct > 0.5 ? 1 : 0} 1 ${arcX} ${arcY}`

  const color =
    pct < 0.3 ? '#10b981' :
    pct < 0.7 ? '#f59e0b' :
                '#ef4444'

  const label =
    pct < 0.3 ? 'Likely authentic' :
    pct < 0.7 ? 'Inconclusive'    :
                'Likely synthetic'

  return (
    <div className="flex flex-col items-center gap-2">
      <svg viewBox="0 0 120 65" className="w-48 h-24" aria-hidden="true">
        {/* Track */}
        <path d={trackD} fill="none" stroke="#2d3748" strokeWidth="10" strokeLinecap="round" />
        {/* Fill */}
        {pct > 0 && (
          <path d={fillD} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round" />
        )}
        {/* Center text */}
        <text x={cx} y={cy - 4} textAnchor="middle" fill="white" fontSize="18" fontWeight="700">
          {percent}%
        </text>
        <text x={cx} y={cy + 12} textAnchor="middle" fill="#94a3b8" fontSize="7">
          {label}
        </text>
      </svg>
      <p
        className={`text-xs font-semibold ${
          pct < 0.3 ? 'text-cred-high' : pct < 0.7 ? 'text-signal-med' : 'text-signal-high'
        }`}
        role="status"
        aria-live="polite"
        aria-label={`Deepfake score: ${percent}% — ${label}`}
      >
        Deepfake probability: {percent}%
      </p>
      {modelName && (
        <p className="text-[10px] text-text-muted">Model: {modelName}</p>
      )}
    </div>
  )
}
