/**
 * Mock API factories — return vi.fn() mocks with correct response shapes.
 *
 * CRITICAL: All real API functions do `.then(r => r.data)` internally,
 * so mocks must return the unwrapped shape (arrays/objects, NOT { data: [] }).
 * This was the root cause of R5 — mock shape mismatch.
 */
import { vi } from 'vitest'
import type { Topic } from '../../api/topics'
import type { Signal } from '../../api/signals'
import type { Source } from '../../api/sources'

export function mockTopicsApi(overrides?: Record<string, any>) {
  return {
    list: vi.fn().mockResolvedValue([] as Topic[]),
    create: vi.fn().mockResolvedValue({ id: 'new-topic', name: 'New', status: 'active' }),
    get: vi.fn().mockResolvedValue(null),
    updateStatus: vi.fn().mockResolvedValue({ topic_id: '', status: 'active' }),
    listClusters: vi.fn().mockResolvedValue([]),
    listSources: vi.fn().mockResolvedValue([]),
    linkSource: vi.fn().mockResolvedValue({ topic_id: '', source_id: '', status: 'linked' }),
    unlinkSource: vi.fn().mockResolvedValue({ topic_id: '', source_id: '', status: 'unlinked' }),
    sentimentTrend: vi.fn().mockResolvedValue([]),
    trendingKeywords: vi.fn().mockResolvedValue([]),
    ...overrides,
  }
}

export function mockSignalsApi(overrides?: Record<string, any>) {
  return {
    list: vi.fn().mockResolvedValue([] as Signal[]),
    acknowledge: vi.fn().mockResolvedValue({ signal_id: '', status: 'acknowledged' }),
    dismiss: vi.fn().mockResolvedValue({ signal_id: '', status: 'dismissed' }),
    connections: vi.fn().mockResolvedValue({ nodes: [], edges: [] }),
    ...overrides,
  }
}

export function mockSourcesApi(overrides?: Record<string, any>) {
  return {
    list: vi.fn().mockResolvedValue([] as Source[]),
    create: vi.fn().mockResolvedValue({ id: 'new-source', name: 'New' }),
    updateCredibility: vi.fn().mockResolvedValue({ source_id: '', old_score: 0, new_score: 0 }),
    getAuditLog: vi.fn().mockResolvedValue([]),
    toggleActive: vi.fn().mockResolvedValue({ source_id: '', is_active: true }),
    getReportWarningsCount: vi.fn().mockResolvedValue({ source_id: '', warning_count: 0 }),
    checkHealth: vi.fn().mockResolvedValue({ source_id: '', health_status: 'healthy', consecutive_failures: 0, health_error: null, checked_at: '' }),
    update: vi.fn().mockResolvedValue({ source_id: '' }),
    delete: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}
