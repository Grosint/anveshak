/**
 * Contract shape tests — verify that the fields frontend components ACCESS
 * actually exist on the TypeScript interfaces returned by API modules.
 *
 * Seam 10: Backend Pydantic → Frontend TypeScript interface.
 *
 * These are compile-time + runtime checks. If a field is removed from the
 * interface but a component still reads it, TypeScript catches it at build.
 * These tests catch the RUNTIME case: mock factories returning wrong shapes.
 */
import { describe, it, expect } from 'vitest'
import { makeSignal, makeTopic, makeSource, makeContentItem, makeReport } from '../factories'

describe('Signal shape contract', () => {
  it('has all fields accessed by SignalCard', () => {
    const signal = makeSignal()
    // Every field SignalCard.tsx reads:
    expect(signal).toHaveProperty('id')
    expect(signal).toHaveProperty('topic_id')
    expect(signal).toHaveProperty('cluster_id')
    expect(signal).toHaveProperty('signal_type')
    expect(signal).toHaveProperty('description')
    expect(signal).toHaveProperty('status')
    expect(signal).toHaveProperty('created_at')
    expect(signal).toHaveProperty('cluster_label')
    expect(signal).toHaveProperty('independent_source_count')
    expect(signal).toHaveProperty('cluster_item_count')
    expect(signal).toHaveProperty('executive_summary')
    expect(signal).toHaveProperty('topic_name')
    expect(signal).toHaveProperty('sources')
    expect(signal).toHaveProperty('first_seen')
    expect(signal).toHaveProperty('last_seen')
  })

  it('sources array contains required sub-fields', () => {
    const signal = makeSignal({
      sources: [{ source_name: 'Test', platform: 'web', credibility_score: 75 }],
    })
    const src = signal.sources[0]
    expect(src).toHaveProperty('source_name')
    expect(src).toHaveProperty('platform')
    expect(src).toHaveProperty('credibility_score')
  })

  it('status is a valid SignalStatus value', () => {
    const signal = makeSignal()
    expect(['new', 'acknowledged', 'dismissed']).toContain(signal.status)
  })
})

describe('Topic shape contract', () => {
  it('has all fields accessed by TopicsDashboard', () => {
    const topic = makeTopic()
    expect(topic).toHaveProperty('id')
    expect(topic).toHaveProperty('name')
    expect(topic).toHaveProperty('status')
    expect(topic).toHaveProperty('signal_threshold')
    expect(topic).toHaveProperty('credibility_min')
    expect(topic).toHaveProperty('created_at')
    expect(topic).toHaveProperty('content_count')
    expect(topic).toHaveProperty('signal_count')
  })

  it('status is a valid TopicStatus value', () => {
    const topic = makeTopic()
    expect(['active', 'paused', 'archived']).toContain(topic.status)
  })
})

describe('Source shape contract', () => {
  it('has all fields accessed by SourceManager', () => {
    const source = makeSource()
    expect(source).toHaveProperty('id')
    expect(source).toHaveProperty('name')
    expect(source).toHaveProperty('url_or_handle')
    expect(source).toHaveProperty('platform')
    expect(source).toHaveProperty('credibility_score')
    expect(source).toHaveProperty('is_active')
    expect(source).toHaveProperty('health_status')
    expect(source).toHaveProperty('consecutive_failures')
    expect(source).toHaveProperty('health_error')
    expect(source).toHaveProperty('last_checked_at')
    expect(source).toHaveProperty('topic_links_count')
  })

  it('health_status is a valid value', () => {
    const source = makeSource()
    expect(['healthy', 'degraded', 'down', 'unverified']).toContain(source.health_status)
  })
})

describe('ContentItem shape contract', () => {
  it('has all fields accessed by ContentCard and filtering', () => {
    const item = makeContentItem()
    expect(item).toHaveProperty('id')
    expect(item).toHaveProperty('url')
    expect(item).toHaveProperty('clean_text')
    expect(item).toHaveProperty('language')
    expect(item).toHaveProperty('credibility_score_at_capture')
    expect(item).toHaveProperty('captured_at')
    expect(item).toHaveProperty('backfilled')
  })

  it('credibility_score_at_capture is a number for filter comparison', () => {
    const item = makeContentItem()
    expect(typeof item.credibility_score_at_capture).toBe('number')
  })
})

describe('Report shape contract', () => {
  it('has all fields accessed by ReportBuilder', () => {
    const report = makeReport()
    expect(report).toHaveProperty('id')
    expect(report).toHaveProperty('topic_id')
    expect(report).toHaveProperty('report_type')
    expect(report).toHaveProperty('generated_at')
    expect(report).toHaveProperty('generation_status')
    expect(report).toHaveProperty('generation_error')
    expect(report).toHaveProperty('content_md')
    expect(report).toHaveProperty('confidence_score')
    expect(report).toHaveProperty('content_item_count')
    expect(report).toHaveProperty('source_warnings')
    expect(report).toHaveProperty('created_at')
  })

  it('generation_status is a valid value', () => {
    const report = makeReport()
    expect(['queued', 'complete', 'failed']).toContain(report.generation_status)
  })
})

describe('WSSignalMessage shape contract', () => {
  it('has all fields accessed by SignalsInbox WS handler', () => {
    // This is the shape WSContext dispatches to subscribers
    const msg = {
      type: 'signal' as const,
      signal_id: 'sig-1',
      topic_id: 'topic-1',
      cluster_id: null,
      signal_type: 'narrative_spike',
      created_at: '2026-05-09T12:00:00Z',
    }
    // SignalsInbox handler checks msg.type for 'signal' or 'signal_replay'
    expect(msg).toHaveProperty('type')
    expect(msg).toHaveProperty('signal_id')
    expect(msg).toHaveProperty('topic_id')
    expect(['signal', 'signal_replay']).toContain(msg.type)
  })
})

describe('Mock factory shapes match API unwrap pattern', () => {
  it('factories return plain objects, not wrapped in { data: ... }', () => {
    // R5 fix verification — all API functions do .then(r => r.data) internally
    const signal = makeSignal()
    expect(signal).not.toHaveProperty('data')
    expect(typeof signal.id).toBe('string')

    const topic = makeTopic()
    expect(topic).not.toHaveProperty('data')

    const source = makeSource()
    expect(source).not.toHaveProperty('data')
  })
})
