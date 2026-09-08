/**
 * Sentiment Timeline chart — issue #29.
 *
 * Covers rendering, the empty state, and the excluded-items footnote. The
 * footnote is the point of the publication-time work: an analyst who cannot
 * see how much was excluded cannot judge the chart.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SentimentTimeline } from '../../components/intelligence/SentimentTimeline'

const mockGet = vi.fn()
vi.mock('../../api/timeline', () => ({
  timelineApi: { get: (...args: any[]) => mockGet(...args) },
}))

// Recharts measures its container, which jsdom reports as zero.
vi.mock('recharts', async () => {
  const actual = await vi.importActual<any>('recharts')
  return {
    ...actual,
    ResponsiveContainer: ({ children }: any) => (
      <div style={{ width: 800, height: 300 }}>{children}</div>
    ),
  }
})

function makeTimeline(overrides = {}) {
  return {
    topic_id: 'topic-1',
    bucket: 'day',
    days: 90,
    as_percentage: false,
    buckets: [
      {
        bucket: '2026-03-01',
        supporting: 12,
        opposing: 4,
        neutral: 2,
        unsupported_language: 1,
        unscored: 0,
        total: 19,
        mean_hostility: 0.22,
        hostility_sample_count: 18,
      },
      {
        bucket: '2026-03-02',
        supporting: 9,
        opposing: 18,
        neutral: 3,
        unsupported_language: 0,
        unscored: 0,
        total: 30,
        mean_hostility: 0.48,
        hostility_sample_count: 30,
      },
    ],
    excluded_no_publication_time: 0,
    constrained_platforms: [],
    ...overrides,
  }
}

function renderTimeline() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(
    <QueryClientProvider client={client}>
      <SentimentTimeline topicId="topic-1" />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mockGet.mockReset()
})

describe('Rendering', () => {
  it('renders the chart when there is data', async () => {
    mockGet.mockResolvedValue(makeTimeline())
    renderTimeline()
    await waitFor(() => expect(screen.getByText('Supporting')).toBeInTheDocument())
    expect(screen.getByLabelText('Sentiment timeline')).toBeInTheDocument()
    expect(screen.getByText('Opposing')).toBeInTheDocument()
  })

  it('overlays mean hostility', async () => {
    mockGet.mockResolvedValue(makeTimeline())
    renderTimeline()
    await waitFor(() => expect(screen.getByText('Mean hostility')).toBeInTheDocument())
  })

  it('defaults to absolute volume', async () => {
    mockGet.mockResolvedValue(makeTimeline())
    renderTimeline()
    await waitFor(() => expect(mockGet).toHaveBeenCalled())
    expect(mockGet.mock.calls[0][1].as_percentage).toBe(false)
  })

  it('offers a percentage view', async () => {
    mockGet.mockResolvedValue(makeTimeline())
    renderTimeline()
    await waitFor(() => expect(screen.getByText('Percentage')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Percentage'))
    await waitFor(() =>
      expect(mockGet.mock.calls.at(-1)?.[1].as_percentage).toBe(true),
    )
  })

  it('changes the range', async () => {
    mockGet.mockResolvedValue(makeTimeline())
    renderTimeline()
    await waitFor(() => expect(screen.getByText('30d')).toBeInTheDocument())
    fireEvent.click(screen.getByText('30d'))
    await waitFor(() => expect(mockGet.mock.calls.at(-1)?.[1].days).toBe(30))
  })
})

describe('Empty state', () => {
  it('says nothing is scored yet rather than drawing an empty chart', async () => {
    mockGet.mockResolvedValue(makeTimeline({ buckets: [] }))
    renderTimeline()
    await waitFor(() =>
      expect(screen.getByText(/No scored content with a publication time/i)).toBeInTheDocument(),
    )
  })
})

describe('Excluded items footnote', () => {
  it('reports items with no publication time', async () => {
    mockGet.mockResolvedValue(makeTimeline({ excluded_no_publication_time: 47 }))
    renderTimeline()
    await waitFor(() => expect(screen.getByText(/47 items excluded/)).toBeInTheDocument())
  })

  it('explains why they are excluded rather than plotted', async () => {
    mockGet.mockResolvedValue(makeTimeline({ excluded_no_publication_time: 47 }))
    renderTimeline()
    await waitFor(() =>
      expect(screen.getByText(/collection artefact/i)).toBeInTheDocument(),
    )
  })

  it('shows no footnote when nothing was excluded', async () => {
    mockGet.mockResolvedValue(makeTimeline({ excluded_no_publication_time: 0 }))
    renderTimeline()
    await waitFor(() => expect(screen.getByText('Supporting')).toBeInTheDocument())
    expect(screen.queryByText(/items excluded/)).not.toBeInTheDocument()
  })
})

describe('Data availability', () => {
  it('labels the portion constrained by a platform search window', async () => {
    mockGet.mockResolvedValue(
      makeTimeline({
        constrained_platforms: [
          { platform: 'twitter', earliest_published_at: '2026-02-25T00:00:00Z', item_count: 40 },
        ],
      }),
    )
    renderTimeline()
    await waitFor(() =>
      expect(screen.getByText(/missing data, not/i)).toBeInTheDocument(),
    )
    expect(screen.getByText(/twitter 2026-02-25/)).toBeInTheDocument()
  })
})
