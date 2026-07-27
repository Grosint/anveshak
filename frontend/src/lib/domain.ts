/**
 * Extracted business logic — imported by both components and tests.
 *
 * Every function here was previously inline inside a React component.
 * Moving them here eliminates the #1 testing problem: tests re-implementing
 * logic that drifts from the real code.
 */
import type { Signal } from '../api/signals'
import type { ContentItem, ContentFilters } from '../api/content'

// ── Signal severity ─────────────────────────────────────────────────────

export function inferSeverity(signal: Signal): string {
  const isc = signal.independent_source_count ?? 0
  if (isc >= 3) return 'HIGH'
  if (isc >= 2) return 'MEDIUM'
  const t = signal.signal_type.toUpperCase()
  // Engine C signal types
  if (t.includes('IDENTIFIER_CONVERGENCE')) return 'HIGH'
  if (t.includes('SCAM_TEMPLATE_MATCH')) return 'MEDIUM'
  if (t.includes('MULTI_SOURCE_CONVERGENCE')) return 'HIGH'
  if (t.includes('HIGH') || t.includes('CRITICAL')) return 'HIGH'
  if (t.includes('MED')) return 'MEDIUM'
  if (t.includes('LOW')) return 'LOW'
  return 'LOW'
}

export type SeverityLevel = 'HIGH' | 'MEDIUM' | 'LOW'

export function inferSeverityFromISC(isc: number): SeverityLevel {
  if (isc >= 3) return 'HIGH'
  if (isc >= 2) return 'MEDIUM'
  return 'LOW'
}

export const SEVERITY_VARIANT: Record<string, 'danger' | 'warning' | 'success' | 'default'> = {
  HIGH: 'danger', MEDIUM: 'warning', LOW: 'success',
}

// ── Confidence badge ────────────────────────────────────────────────────

export function confidenceVariant(score: number): 'success' | 'warning' | 'danger' {
  const pct = Math.round(score * 100)
  if (pct >= 70) return 'success'
  if (pct >= 40) return 'warning'
  return 'danger'
}

// ── Credibility label ───────────────────────────────────────────────────

export interface CredibilityInfo {
  label: string
  color: string
}

export function credibilityLabel(score: number): CredibilityInfo {
  if (score >= 70) return { label: 'High', color: 'bg-cred-high/20 text-cred-high' }
  if (score >= 40) return { label: 'Medium', color: 'bg-cred-mid/20 text-cred-mid' }
  return { label: 'Low', color: 'bg-cred-low/20 text-cred-low' }
}

// ── Deepfake meter ──────────────────────────────────────────────────────

export interface DeepfakeInfo {
  label: string
  color: string
  cssClass: string
}

export function deepfakeLabel(score: number): DeepfakeInfo {
  const pct = Math.max(0, Math.min(1, score))
  if (pct < 0.3)
    return { label: 'Likely authentic', color: '#10b981', cssClass: 'text-cred-high' }
  if (pct < 0.7)
    return { label: 'Inconclusive', color: '#f59e0b', cssClass: 'text-signal-med' }
  return { label: 'Likely synthetic', color: '#ef4444', cssClass: 'text-signal-high' }
}

// ── Time range resolution ───────────────────────────────────────────────

export type TimePreset = 'today' | '7d' | '14d' | '30d' | 'day' | 'custom'

export function resolveTimeRange(
  preset: TimePreset,
  customFrom: string,
  customTo: string,
): { since: string; until: string } {
  const now = new Date()
  const until = now.toISOString()

  if (preset === 'today') {
    const startOfDay = new Date(now)
    startOfDay.setUTCHours(0, 0, 0, 0)
    return { since: startOfDay.toISOString(), until }
  }
  if (preset === 'day') {
    // Single day mode — customFrom holds the YYYY-MM-DD
    if (!customFrom) return resolveTimeRange('today', '', '')
    const dayStart = new Date(customFrom + 'T00:00:00Z')
    const dayEnd = new Date(customFrom + 'T23:59:59Z')
    return { since: dayStart.toISOString(), until: dayEnd.toISOString() }
  }
  if (preset === '7d') {
    const d = new Date(now)
    d.setUTCDate(d.getUTCDate() - 7)
    return { since: d.toISOString(), until }
  }
  if (preset === '14d') {
    const d = new Date(now)
    d.setUTCDate(d.getUTCDate() - 14)
    return { since: d.toISOString(), until }
  }
  if (preset === '30d') {
    const d = new Date(now)
    d.setUTCDate(d.getUTCDate() - 30)
    return { since: d.toISOString(), until }
  }
  const since = customFrom ? new Date(customFrom + 'T00:00:00Z').toISOString() : ''
  const customUntil = customTo
    ? new Date(customTo + 'T23:59:59Z').toISOString()
    : until
  return { since, until: customUntil }
}

// ── Client-side content filtering ───────────────────────────────────────

export function applyClientFilters(items: ContentItem[], filters: ContentFilters): ContentItem[] {
  return items.filter((item) => {
    if (filters.language && item.language !== filters.language) return false
    if (filters.credibility_min !== undefined && item.credibility_score_at_capture < filters.credibility_min) return false
    if (filters.date_from && item.captured_at < filters.date_from) return false
    if (filters.date_to && item.captured_at > filters.date_to) return false
    return true
  })
}
