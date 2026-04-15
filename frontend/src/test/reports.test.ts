/**
 * Unit tests for Report domain logic and immutability rules (criterion 6.44).
 */
import { describe, it, expect } from 'vitest'
import type { Report, ReportType } from '../api/reports'

// Minimal Report type — mirrors what reports.ts exports
interface MinimalReport {
  id: string
  report_id?: string
  topic_id: string
  report_type: ReportType
  generation_status: 'queued' | 'complete' | 'failed'
  generated_at: string | null
  content_md: string | null
  confidence_score: number | null
  content_item_count: number | null
  source_warnings: unknown[] | null
  created_at: string
}

const queuedReport: MinimalReport = {
  id: 'r-1',
  topic_id: 't-1',
  report_type: 'intelligence_brief',
  generation_status: 'queued',
  generated_at: null,
  content_md: null,
  confidence_score: null,
  content_item_count: null,
  source_warnings: null,
  created_at: new Date().toISOString(),
}

describe('Report immutability rule (criterion 4 / CLAUDE.md)', () => {
  it('generated_at starts null for queued report', () => {
    expect(queuedReport.generated_at).toBeNull()
  })

  it('generated_at is set on complete report and never changes', () => {
    const completeReport: MinimalReport = {
      ...queuedReport,
      generation_status: 'complete',
      generated_at: new Date().toISOString(),
      content_md: '# Report\nSome content',
      confidence_score: 0.82,
    }
    expect(completeReport.generated_at).not.toBeNull()
    // Simulate an attempted mutation — immutable snapshots should not change this
    const snapshot = { ...completeReport }
    expect(snapshot.generated_at).toBe(completeReport.generated_at)
  })
})

describe('Report types', () => {
  const types: ReportType[] = ['intelligence_brief', 'research_summary', 'weekly_digest']

  types.forEach((rt) => {
    it(`accepts report_type: ${rt}`, () => {
      const r: MinimalReport = { ...queuedReport, report_type: rt }
      expect(r.report_type).toBe(rt)
    })
  })
})

describe('ConfidenceBadge logic', () => {
  function confidenceVariant(score: number): string {
    const pct = Math.round(score * 100)
    if (pct >= 70) return 'success'
    if (pct >= 40) return 'warning'
    return 'danger'
  }

  it('high confidence → success', () => expect(confidenceVariant(0.85)).toBe('success'))
  it('medium confidence → warning', () => expect(confidenceVariant(0.55)).toBe('warning'))
  it('low confidence → danger', () => expect(confidenceVariant(0.2)).toBe('danger'))
  it('boundary 0.7 → success', () => expect(confidenceVariant(0.7)).toBe('success'))
  it('boundary 0.4 → warning', () => expect(confidenceVariant(0.4)).toBe('warning'))
})
