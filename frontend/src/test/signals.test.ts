/**
 * Unit tests for Signal severity logic — imports the REAL function from lib/domain.
 */
import { describe, it, expect } from 'vitest'
import { inferSeverity } from '../lib/domain'
import type { Signal } from '../api/signals'

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
  cluster_item_count: null,
  executive_summary: null,
  topic_name: null,
  sources: [],
  first_seen: null,
  last_seen: null,
}

describe('inferSeverity', () => {
  it('returns HIGH when independent_source_count >= 3', () => {
    expect(inferSeverity({ ...baseSignal, independent_source_count: 3 })).toBe('HIGH')
    expect(inferSeverity({ ...baseSignal, independent_source_count: 5 })).toBe('HIGH')
  })

  it('returns MEDIUM when independent_source_count = 2', () => {
    expect(inferSeverity({ ...baseSignal, independent_source_count: 2 })).toBe('MEDIUM')
  })

  it('returns HIGH for CRITICAL signal types (isc < 2)', () => {
    expect(inferSeverity({ ...baseSignal, independent_source_count: 1, signal_type: 'critical_threshold' })).toBe('HIGH')
  })

  it('returns HIGH for HIGH signal types (isc < 2)', () => {
    expect(inferSeverity({ ...baseSignal, independent_source_count: 1, signal_type: 'high_velocity_spread' })).toBe('HIGH')
  })

  it('returns MEDIUM for MED signal types', () => {
    expect(inferSeverity({ ...baseSignal, independent_source_count: 1, signal_type: 'medium_cluster_growth' })).toBe('MEDIUM')
  })

  it('returns LOW for LOW signal types', () => {
    expect(inferSeverity({ ...baseSignal, independent_source_count: 1, signal_type: 'low_volume_mention' })).toBe('LOW')
  })

  it('defaults to LOW for unknown signal types', () => {
    expect(inferSeverity({ ...baseSignal, independent_source_count: 1, signal_type: 'narrative_spike' })).toBe('LOW')
  })

  it('null independent_source_count coerces to 0, unknown type defaults to LOW', () => {
    expect(inferSeverity({ ...baseSignal, independent_source_count: null, signal_type: 'narrative_spike' })).toBe('LOW')
  })

  it('returns HIGH for IDENTIFIER_CONVERGENCE (Engine C)', () => {
    expect(inferSeverity({ ...baseSignal, independent_source_count: 1, signal_type: 'IDENTIFIER_CONVERGENCE' })).toBe('HIGH')
  })

  it('returns MEDIUM for SCAM_TEMPLATE_MATCH (Engine C)', () => {
    expect(inferSeverity({ ...baseSignal, independent_source_count: 1, signal_type: 'SCAM_TEMPLATE_MATCH' })).toBe('MEDIUM')
  })

  it('returns HIGH for MULTI_SOURCE_CONVERGENCE (Engine C)', () => {
    expect(inferSeverity({ ...baseSignal, independent_source_count: 1, signal_type: 'MULTI_SOURCE_CONVERGENCE' })).toBe('HIGH')
  })
})
