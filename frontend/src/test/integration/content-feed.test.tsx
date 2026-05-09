/**
 * Integration tests for content feed seam:
 *
 * Seam 6: API fetch → client-side filters → display
 *
 * Tests the full flow: useInfiniteContent fetches pages → applyClientFilters
 * runs client-side → ContentFeed renders the filtered items.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ContentFeed from '../../pages/ContentFeed'
import { makeContentItem } from '../factories'

const mockContentList = vi.fn()

vi.mock('../../api/content', () => ({
  contentApi: {
    list: (...args: any[]) => mockContentList(...args),
    get: vi.fn(),
    search: vi.fn().mockResolvedValue([]),
    getVision: vi.fn(),
  },
}))

vi.mock('../../api/topics', () => ({
  topicsApi: {
    get: vi.fn().mockResolvedValue({ id: 'topic-1', name: 'Test Topic', status: 'active', signal_threshold: 3, credibility_min: 30, created_at: '2026-05-01T00:00:00Z' }),
    listClusters: vi.fn().mockResolvedValue([]),
    listSources: vi.fn().mockResolvedValue([]),
    sentimentTrend: vi.fn().mockResolvedValue([]),
    trendingKeywords: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    token: 'test-jwt',
    user: { sub: 'analyst-1', exp: Math.floor(Date.now() / 1000) + 3600, iat: Math.floor(Date.now() / 1000) },
    login: vi.fn(),
    logout: vi.fn(),
    secondsUntilExpiry: 3600,
  }),
}))

function renderContentFeed() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/topics/topic-1/feed']}>
        <Routes>
          <Route path="/topics/:topicId/feed" element={<ContentFeed />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mockContentList.mockReset()
})

describe('Seam 6: API fetch → client filter → display', () => {
  it('loads content items and renders them', async () => {
    const items = [
      makeContentItem({ id: 'ci-1', title: 'Article One', language: 'en', credibility_score_at_capture: 80 }),
      makeContentItem({ id: 'ci-2', title: 'Article Two', language: 'hi', credibility_score_at_capture: 50 }),
    ]
    mockContentList.mockResolvedValue(items)

    renderContentFeed()

    await waitFor(() => {
      expect(screen.getByText('Article One')).toBeInTheDocument()
      expect(screen.getByText('Article Two')).toBeInTheDocument()
    })
  })

  it('empty content shows empty state', async () => {
    mockContentList.mockResolvedValue([])

    renderContentFeed()

    await waitFor(() => {
      expect(screen.getByText('No content yet')).toBeInTheDocument()
    })
  })

  it('topicId from URL params flows through to API call', async () => {
    mockContentList.mockResolvedValue([])

    renderContentFeed()

    await waitFor(() => {
      // contentApi.list is called with topicId as first arg
      expect(mockContentList).toHaveBeenCalledWith('topic-1', expect.any(Number), expect.any(Number), undefined)
    })
  })
})
