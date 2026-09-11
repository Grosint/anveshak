/**
 * Content feed request contract — issue #49.
 *
 * The date filter belongs in the query, not in the page already fetched, so
 * the feed request must carry the range to the server. A filter applied after
 * fetch filters what has been loaded rather than the topic.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.hoisted(() => vi.fn())

vi.mock('../../api/client', () => ({
  default: { get: mockGet, post: vi.fn() },
}))

import { contentApi } from '../../api/content'

beforeEach(() => {
  mockGet.mockReset()
  mockGet.mockResolvedValue({ data: [] })
})

function lastParams(): Record<string, unknown> {
  return mockGet.mock.calls[0][1].params
}

describe('contentApi.list', () => {
  it('sends the date range to the server', async () => {
    await contentApi.list('topic-1', 0, 50, { date_from: '2026-03-02', date_to: '2026-03-08' })

    expect(lastParams()).toMatchObject({
      offset: 0,
      limit: 50,
      date_from: '2026-03-02',
      date_to: '2026-03-08',
    })
  })

  it('omits date params when no range is set', async () => {
    await contentApi.list('topic-1', 0, 50, { sentiment: 'positive' })

    const params = lastParams()
    expect(params).not.toHaveProperty('date_from')
    expect(params).not.toHaveProperty('date_to')
    expect(params).toMatchObject({ sentiment: 'positive' })
  })

  it('still carries sentiment and sort_by', async () => {
    await contentApi.list('topic-1', 100, 25, { sentiment: 'negative', sort_by: 'relevance' })

    expect(lastParams()).toMatchObject({
      offset: 100,
      limit: 25,
      sentiment: 'negative',
      sort_by: 'relevance',
    })
  })

  it('sends only paging when called without filters', async () => {
    await contentApi.list('topic-1')

    expect(lastParams()).toEqual({ offset: 0, limit: 50 })
  })
})
