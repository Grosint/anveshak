/**
 * Data factories for tests — produce minimally valid domain objects.
 * Each factory returns a complete object with all required fields.
 * Use Partial<T> overrides to customise for specific test cases.
 */
import type { Topic } from '../api/topics'
import type { Signal, SignalStatus } from '../api/signals'
import type { Source, Platform, HealthStatus } from '../api/sources'
import type { ContentItem } from '../api/content'
import type { Report, ReportType, ReportStatus } from '../api/reports'

let counter = 0
function nextId(prefix: string): string {
  return `${prefix}-${++counter}`
}

export function makeTopic(overrides?: Partial<Topic>): Topic {
  return {
    id: nextId('topic'),
    name: 'Test Topic',
    status: 'active',
    signal_threshold: 3,
    credibility_min: 30,
    created_at: new Date().toISOString(),
    content_count: 0,
    signal_count: 0,
    ...overrides,
  }
}

export function makeSignal(overrides?: Partial<Signal>): Signal {
  return {
    id: nextId('sig'),
    topic_id: 'topic-1',
    cluster_id: 'cluster-1',
    signal_type: 'narrative_spike',
    description: 'Cluster reached threshold',
    evidence: {},
    status: 'new' as SignalStatus,
    created_at: new Date().toISOString(),
    cluster_label: 'Test cluster',
    independent_source_count: 1,
    cluster_item_count: null,
    executive_summary: null,
    topic_name: null,
    sources: [],
    first_seen: null,
    last_seen: null,
    ...overrides,
  }
}

export function makeSource(overrides?: Partial<Source>): Source {
  return {
    id: nextId('src'),
    name: 'Test Source',
    url_or_handle: 'https://example.com',
    platform: 'web' as Platform,
    credibility_score: 75,
    is_active: true,
    health_status: 'healthy' as HealthStatus,
    consecutive_failures: 0,
    health_error: null,
    last_checked_at: new Date().toISOString(),
    topic_links_count: 1,
    ...overrides,
  }
}

export function makeContentItem(overrides?: Partial<ContentItem>): ContentItem {
  return {
    id: nextId('ci'),
    url: 'https://example.com/article',
    title: 'Test Article',
    clean_text: 'Test content for analysis',
    language: 'en',
    credibility_score_at_capture: 75,
    captured_at: new Date().toISOString(),
    backfilled: false,
    ...overrides,
  }
}

export function makeReport(overrides?: Partial<Report>): Report {
  return {
    id: nextId('rpt'),
    topic_id: 'topic-1',
    report_type: 'intelligence_brief' as ReportType,
    generated_at: null,
    generation_status: 'queued' as ReportStatus,
    generation_error: null,
    content_md: null,
    confidence_score: null,
    content_item_count: null,
    credibility_min_filter: 30,
    time_window_start: new Date(Date.now() - 86400000).toISOString(),
    time_window_end: new Date().toISOString(),
    source_snapshot: null,
    source_warnings: [],
    geojson: null,
    created_at: new Date().toISOString(),
    ...overrides,
  }
}
