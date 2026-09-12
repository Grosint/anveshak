/**
 * Actor View — issue #35.
 *
 * Reached from any handle in the Provenance Panel so an investigation trail
 * stays continuous. A query, not a stored entity: nothing here creates or
 * displays a persistent per-person record.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ActorDetail from '../../components/provenance/ActorDetail'
import { isHandleIdentifier } from '../../lib/domain'

const mockGetActor = vi.fn()
vi.mock('../../api/actors', () => ({
  actorsApi: { get: (...args: any[]) => mockGetActor(...args) },
}))

const push = vi.fn()
vi.mock('../../contexts/provenance', () => ({
  useProvenance: () => ({ push }),
}))

function renderActor(handle = 'publicaccount', topicId = 'topic-1') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(
    <QueryClientProvider client={client}>
      <ActorDetail handle={handle} topicId={topicId} />
    </QueryClientProvider>,
  )
}

const ACTOR = {
  handle: 'publicaccount',
  topic_id: 'topic-1',
  summary: {
    post_count: 12,
    source_count: 2,
    platform_count: 2,
    platforms: ['twitter', 'telegram'],
    first_seen: '2026-01-01T00:00:00Z',
    last_seen: '2026-03-01T00:00:00Z',
    total_likes: 340,
    total_views: 9000,
    total_shares: 55,
  },
  content: [
    {
      id: 'ci-1',
      url: 'https://x.com/i/web/status/1',
      title: null,
      clean_text: 'A public post about the fuel price protest.',
      language: 'en',
      captured_at: '2026-03-01T00:00:00Z',
      published_at: '2026-02-28T00:00:00Z',
      stance: 'supporting',
      hostility: 0.2,
      source_name: 'ANI on X',
      platform: 'twitter',
      cluster_label: 'Fuel price protest',
      narrative_cluster_id: 'cl-1',
      engagement: { likes: 20 },
    },
  ],
  activity: [
    { day: '2026-02-28T00:00:00Z', post_count: 1, approximate_count: 0, total_likes: 20 },
  ],
}

beforeEach(() => {
  mockGetActor.mockReset()
  push.mockReset()
})

describe('ActorDetail', () => {
  it('shows the handle', async () => {
    mockGetActor.mockResolvedValue(ACTOR)
    renderActor()
    await waitFor(() => expect(screen.getByText('@publicaccount')).toBeInTheDocument())
  })

  it('shows the post count and platforms', async () => {
    mockGetActor.mockResolvedValue(ACTOR)
    renderActor()
    await waitFor(() => expect(screen.getByText('12')).toBeInTheDocument())
    expect(screen.getAllByText(/twitter/i).length).toBeGreaterThan(0)
  })

  it('shows engagement', async () => {
    mockGetActor.mockResolvedValue(ACTOR)
    renderActor()
    await waitFor(() => expect(screen.getByText(/340/)).toBeInTheDocument())
  })

  it('lists the content', async () => {
    mockGetActor.mockResolvedValue(ACTOR)
    renderActor()
    await waitFor(() =>
      expect(screen.getByText(/A public post about the fuel price protest/)).toBeInTheDocument(),
    )
  })

  it('continues the trail into a content item', async () => {
    mockGetActor.mockResolvedValue(ACTOR)
    renderActor()
    await waitFor(() =>
      expect(screen.getByText(/A public post about the fuel price protest/)).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByText(/A public post about the fuel price protest/))
    expect(push).toHaveBeenCalledWith(
      expect.objectContaining({ entityType: 'content', entityId: 'ci-1' }),
    )
  })

  it('states that nothing is stored about the person', async () => {
    mockGetActor.mockResolvedValue(ACTOR)
    renderActor()
    await waitFor(() => expect(screen.getByText(/no record is stored/i)).toBeInTheDocument())
  })

  it('handles an actor with no content', async () => {
    mockGetActor.mockResolvedValue({ ...ACTOR, content: [], activity: [], summary: {} })
    renderActor()
    await waitFor(() => expect(screen.getByText('@publicaccount')).toBeInTheDocument())
    expect(screen.getByText(/no public content/i)).toBeInTheDocument()
  })

  it('scopes the query to the topic', async () => {
    mockGetActor.mockResolvedValue(ACTOR)
    renderActor('publicaccount', 'topic-42')
    await waitFor(() => expect(mockGetActor).toHaveBeenCalledWith('topic-42', 'publicaccount'))
  })
})

describe('Which identifiers open an Actor View', () => {
  it('recognises a handle', () => {
    expect(isHandleIdentifier('TELEGRAM_HANDLE')).toBe(true)
    expect(isHandleIdentifier('INSTAGRAM_HANDLE')).toBe(true)
  })

  it('does not treat a phone number as a handle', () => {
    expect(isHandleIdentifier('PHONE_INTL')).toBe(false)
    expect(isHandleIdentifier('UPI_ID')).toBe(false)
  })

  it('is case insensitive', () => {
    expect(isHandleIdentifier('telegram_handle')).toBe(true)
  })
})
