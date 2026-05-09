/**
 * Tests for extracted business logic in lib/domain.ts.
 *
 * Every function tested here is the REAL implementation used by components.
 * No inline re-implementations, no drift.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  inferSeverity,
  confidenceVariant,
  credibilityLabel,
  deepfakeLabel,
  resolveTimeRange,
  applyClientFilters,
} from '../../lib/domain'
import { makeSignal, makeContentItem } from '../factories'

// ── inferSeverity ───────────────────────────────────────────────────────

describe('inferSeverity', () => {
  describe('independent_source_count takes priority', () => {
    it('isc >= 3 → HIGH regardless of signal_type', () => {
      expect(inferSeverity(makeSignal({ independent_source_count: 3, signal_type: 'low_volume' }))).toBe('HIGH')
      expect(inferSeverity(makeSignal({ independent_source_count: 5 }))).toBe('HIGH')
    })

    it('isc = 2 → MEDIUM regardless of signal_type', () => {
      expect(inferSeverity(makeSignal({ independent_source_count: 2, signal_type: 'critical_alert' }))).toBe('MEDIUM')
    })
  })

  describe('string matching fallback (isc < 2)', () => {
    it('CRITICAL → HIGH', () => {
      expect(inferSeverity(makeSignal({ independent_source_count: 1, signal_type: 'critical_threshold' }))).toBe('HIGH')
    })

    it('HIGH → HIGH', () => {
      expect(inferSeverity(makeSignal({ independent_source_count: 1, signal_type: 'high_velocity_spread' }))).toBe('HIGH')
    })

    it('MED → MEDIUM', () => {
      expect(inferSeverity(makeSignal({ independent_source_count: 1, signal_type: 'medium_cluster_growth' }))).toBe('MEDIUM')
    })

    it('LOW → LOW', () => {
      expect(inferSeverity(makeSignal({ independent_source_count: 1, signal_type: 'low_volume_mention' }))).toBe('LOW')
    })
  })

  describe('BUG R2: unknown signal types default to HIGH', () => {
    it('narrative_spike (no HIGH/MED/LOW keyword) → HIGH', () => {
      expect(inferSeverity(makeSignal({ independent_source_count: 1, signal_type: 'narrative_spike' }))).toBe('HIGH')
    })

    it('null isc coerces to 0, falls through to string match', () => {
      expect(inferSeverity(makeSignal({ independent_source_count: null, signal_type: 'narrative_spike' }))).toBe('HIGH')
    })

    it('isc = 0 with unknown type → HIGH', () => {
      expect(inferSeverity(makeSignal({ independent_source_count: 0, signal_type: 'new_activity_burst' }))).toBe('HIGH')
    })
  })

  it('case-insensitive string matching', () => {
    expect(inferSeverity(makeSignal({ independent_source_count: 0, signal_type: 'HIGH_ALERT' }))).toBe('HIGH')
    expect(inferSeverity(makeSignal({ independent_source_count: 0, signal_type: 'Medium_growth' }))).toBe('MEDIUM')
  })
})

// ── confidenceVariant ───────────────────────────────────────────────────

describe('confidenceVariant', () => {
  it('high confidence → success', () => expect(confidenceVariant(0.85)).toBe('success'))
  it('medium confidence → warning', () => expect(confidenceVariant(0.55)).toBe('warning'))
  it('low confidence → danger', () => expect(confidenceVariant(0.2)).toBe('danger'))

  describe('boundaries', () => {
    it('0.70 → success (70% rounds to 70)', () => expect(confidenceVariant(0.70)).toBe('success'))
    it('0.695 → success (rounds to 70)', () => expect(confidenceVariant(0.695)).toBe('success'))
    it('0.694 → warning (rounds to 69)', () => expect(confidenceVariant(0.694)).toBe('warning'))
    it('0.40 → warning (40% rounds to 40)', () => expect(confidenceVariant(0.40)).toBe('warning'))
    it('0.395 → warning (rounds to 40)', () => expect(confidenceVariant(0.395)).toBe('warning'))
    it('0.394 → danger (rounds to 39)', () => expect(confidenceVariant(0.394)).toBe('danger'))
  })

  it('0.0 → danger', () => expect(confidenceVariant(0.0)).toBe('danger'))
  it('1.0 → success', () => expect(confidenceVariant(1.0)).toBe('success'))
})

// ── credibilityLabel ────────────────────────────────────────────────────

describe('credibilityLabel', () => {
  it('70 → High', () => expect(credibilityLabel(70).label).toBe('High'))
  it('69 → Medium', () => expect(credibilityLabel(69).label).toBe('Medium'))
  it('40 → Medium', () => expect(credibilityLabel(40).label).toBe('Medium'))
  it('39 → Low', () => expect(credibilityLabel(39).label).toBe('Low'))
  it('0 → Low', () => expect(credibilityLabel(0).label).toBe('Low'))
  it('100 → High', () => expect(credibilityLabel(100).label).toBe('High'))

  it('returns CSS classes for each tier', () => {
    expect(credibilityLabel(80).color).toContain('cred-high')
    expect(credibilityLabel(50).color).toContain('cred-mid')
    expect(credibilityLabel(20).color).toContain('cred-low')
  })
})

// ── deepfakeLabel ───────────────────────────────────────────────────────

describe('deepfakeLabel', () => {
  it('0.0 → green, Likely authentic', () => {
    const info = deepfakeLabel(0.0)
    expect(info.label).toBe('Likely authentic')
    expect(info.color).toBe('#10b981')
  })

  it('0.29 → green (boundary)', () => {
    expect(deepfakeLabel(0.29).label).toBe('Likely authentic')
  })

  it('0.30 → amber, Inconclusive', () => {
    const info = deepfakeLabel(0.30)
    expect(info.label).toBe('Inconclusive')
    expect(info.color).toBe('#f59e0b')
  })

  it('0.69 → amber (boundary)', () => {
    expect(deepfakeLabel(0.69).label).toBe('Inconclusive')
  })

  it('0.70 → red, Likely synthetic', () => {
    const info = deepfakeLabel(0.70)
    expect(info.label).toBe('Likely synthetic')
    expect(info.color).toBe('#ef4444')
  })

  it('1.0 → red', () => {
    expect(deepfakeLabel(1.0).label).toBe('Likely synthetic')
  })

  it('clamps values > 1.0', () => {
    expect(deepfakeLabel(1.5).label).toBe('Likely synthetic')
  })

  it('clamps values < 0.0', () => {
    expect(deepfakeLabel(-0.5).label).toBe('Likely authentic')
  })
})

// ── resolveTimeRange ────────────────────────────────────────────────────

describe('resolveTimeRange', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-09T14:30:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('today → since is start of UTC day', () => {
    const { since, until } = resolveTimeRange('today', '', '')
    expect(since).toBe('2026-05-09T00:00:00.000Z')
    expect(until).toBe('2026-05-09T14:30:00.000Z')
  })

  it('7d → since is 7 days ago', () => {
    const { since } = resolveTimeRange('7d', '', '')
    expect(since).toBe('2026-05-02T14:30:00.000Z')
  })

  it('30d → since is 30 days ago', () => {
    const { since } = resolveTimeRange('30d', '', '')
    expect(since).toBe('2026-04-09T14:30:00.000Z')
  })

  it('custom → adds T00:00:00Z to from and T23:59:59Z to to', () => {
    const { since, until } = resolveTimeRange('custom', '2026-05-01', '2026-05-08')
    expect(since).toBe('2026-05-01T00:00:00.000Z')
    expect(until).toBe('2026-05-08T23:59:59.000Z')
  })

  it('custom with empty from → since is empty string', () => {
    const { since } = resolveTimeRange('custom', '', '2026-05-08')
    expect(since).toBe('')
  })

  it('custom with empty to → until falls back to now', () => {
    const { until } = resolveTimeRange('custom', '2026-05-01', '')
    expect(until).toBe('2026-05-09T14:30:00.000Z')
  })

  it('BUG R8: "today" uses UTC boundaries, not local time', () => {
    // An analyst in UTC+5:30 selecting "Today" at 2:00 AM local gets
    // UTC start of day (previous day 18:30 local). Documenting the behavior.
    const { since } = resolveTimeRange('today', '', '')
    expect(since).toContain('T00:00:00') // UTC midnight, not local midnight
  })
})

// ── applyClientFilters ──────────────────────────────────────────────────

describe('applyClientFilters', () => {
  const items = [
    makeContentItem({ language: 'en', credibility_score_at_capture: 80, captured_at: '2026-05-05T10:00:00Z' }),
    makeContentItem({ language: 'hi', credibility_score_at_capture: 50, captured_at: '2026-05-06T10:00:00Z' }),
    makeContentItem({ language: 'en', credibility_score_at_capture: 30, captured_at: '2026-05-07T10:00:00Z' }),
  ]

  it('filters by language', () => {
    const result = applyClientFilters(items, { language: 'hi' })
    expect(result).toHaveLength(1)
    expect(result[0].language).toBe('hi')
  })

  it('filters by credibility_min', () => {
    const result = applyClientFilters(items, { credibility_min: 50 })
    expect(result).toHaveLength(2)
  })

  it('filters by date_from', () => {
    const result = applyClientFilters(items, { date_from: '2026-05-06T00:00:00Z' })
    expect(result).toHaveLength(2)
  })

  it('filters by date_to', () => {
    const result = applyClientFilters(items, { date_to: '2026-05-06T12:00:00Z' })
    expect(result).toHaveLength(2)
  })

  it('null/undefined filter values pass through', () => {
    const result = applyClientFilters(items, {})
    expect(result).toHaveLength(3)
  })

  it('empty items returns empty', () => {
    const result = applyClientFilters([], { language: 'en' })
    expect(result).toHaveLength(0)
  })

  it('multiple filters compose as AND', () => {
    const result = applyClientFilters(items, { language: 'en', credibility_min: 50 })
    expect(result).toHaveLength(1)
    expect(result[0].credibility_score_at_capture).toBe(80)
  })
})
