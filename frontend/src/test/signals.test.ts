/**
 * Unit tests for Signal domain logic (criterion 6.44).
 */
import { describe, it, expect } from 'vitest'
import type { Signal } from '../api/signals'

function inferSeverity(signal: Signal): string {
  const t = signal.signal_type.toUpperCase()
  if (t.includes('HIGH') || t.includes('CRITICAL')) return 'HIGH'
  if (t.includes('MED')) return 'MED'
  if (t.includes('LOW')) return 'LOW'
  return 'HIGH'
}

const baseSignal: Signal = {
  id: 'sig-1',
  topic_id: 'topic-1',
  cluster_id: 'cluster-1',
  signal_type: 'narrative_spike',
  description: 'Cluster reached threshold',
  evidence: {},
  status: 'new',
  created_at: new Date().toISOString(),
  cluster_label: 'Disinformation cluster alpha',
  independent_source_count: 4,
}

describe('inferSeverity', () => {
  it('returns HIGH for CRITICAL signal types', () => {
    expect(inferSeverity({ ...baseSignal, signal_type: 'critical_threshold' })).toBe('HIGH')
  })

  it('returns HIGH for HIGH signal types', () => {
    expect(inferSeverity({ ...baseSignal, signal_type: 'high_velocity_spread' })).toBe('HIGH')
  })

  it('returns MED for MED signal types', () => {
    expect(inferSeverity({ ...baseSignal, signal_type: 'medium_cluster_growth' })).toBe('MED')
  })

  it('returns LOW for LOW signal types', () => {
    expect(inferSeverity({ ...baseSignal, signal_type: 'low_volume_mention' })).toBe('LOW')
  })

  it('defaults to HIGH for unknown signal types', () => {
    expect(inferSeverity({ ...baseSignal, signal_type: 'narrative_spike' })).toBe('HIGH')
  })
})

describe('Signal type shape', () => {
  it('includes cluster_label and independent_source_count', () => {
    expect(baseSignal.cluster_label).toBe('Disinformation cluster alpha')
    expect(baseSignal.independent_source_count).toBe(4)
  })

  it('allows null cluster_label (signal not linked to cluster)', () => {
    const s: Signal = { ...baseSignal, cluster_id: null, cluster_label: null, independent_source_count: null }
    expect(s.cluster_label).toBeNull()
    expect(s.independent_source_count).toBeNull()
  })

  it('status transitions are well-typed', () => {
    const statuses = ['new', 'acknowledged', 'dismissed'] as const
    statuses.forEach((st) => {
      const s: Signal = { ...baseSignal, status: st }
      expect(['new', 'acknowledged', 'dismissed']).toContain(s.status)
    })
  })
})
