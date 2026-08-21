import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TopicsDashboard from '../../pages/TopicsDashboard'
import { renderWithProviders } from '../test-utils'

// ── Mock data ──────────────────────────────────────────────────────────
const mockTopics = vi.hoisted(() => [
  {
    id: 't1', name: 'Ukraine conflict', status: 'active' as const,
    signal_threshold: 3, credibility_min: 30, created_at: '2026-01-15T00:00:00Z',
    content_count: 150, signal_count: 8,
    new_content_24h: 12, worst_source_health: 'healthy' as const,
    last_activity: '2026-07-27T10:00:00Z',
  },
  {
    id: 't2', name: 'South China Sea', status: 'active' as const,
    signal_threshold: 2, credibility_min: 40, created_at: '2026-03-01T00:00:00Z',
    content_count: 90, signal_count: 3,
    new_content_24h: 5, worst_source_health: 'degraded' as const,
    last_activity: '2026-07-27T08:00:00Z',
  },
  {
    id: 't3', name: 'Cybersecurity threats', status: 'paused' as const,
    signal_threshold: 4, credibility_min: 50, created_at: '2026-02-10T00:00:00Z',
    content_count: 45, signal_count: 0,
    new_content_24h: 0, worst_source_health: 'down' as const,
    last_activity: '2026-07-20T00:00:00Z',
  },
  {
    id: 't4', name: 'Border surveillance', status: 'paused' as const,
    signal_threshold: 3, credibility_min: 35, created_at: '2026-04-01T00:00:00Z',
    content_count: 20, signal_count: 1,
    new_content_24h: 0, worst_source_health: 'healthy' as const,
    last_activity: null,
  },
])

vi.mock('../../api/topics', () => ({
  topicsApi: {
    list: vi.fn().mockResolvedValue(mockTopics),
    create: vi.fn(),
    get: vi.fn(),
    updateStatus: vi.fn(),
    listClusters: vi.fn(),
  },
}))

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    user: { sub: 'analyst-1', exp: Date.now() / 1000 + 3600, iat: Date.now() / 1000 },
    token: 'fake-token',
    secondsUntilExpiry: 3600,
  }),
  AuthProvider: ({ children }: any) => children,
}))

describe('TopicsDashboard page', () => {
  // ─────────────────────────────────────────────────────────────────────
  // Basic rendering
  // ─────────────────────────────────────────────────────────────────────

  it('shows empty state when no topics exist', async () => {
    const { topicsApi } = await import('../../api/topics')
    vi.mocked(topicsApi.list).mockResolvedValueOnce([])

    renderWithProviders(<TopicsDashboard />)
    await waitFor(() => {
      expect(screen.getByText('No topics yet')).toBeInTheDocument()
    })

    vi.mocked(topicsApi.list).mockResolvedValue(mockTopics)
  })

  it('shows a "New topic" button', async () => {
    renderWithProviders(<TopicsDashboard />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /new topic|create/i })).toBeInTheDocument()
    })
  })

  it('renders all topic cards', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TopicsDashboard />)

    // Default filter is 'active' — click 'All' to show all topics
    await waitFor(() => {
      expect(screen.getByText('Ukraine conflict')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /All/i }))

    await waitFor(() => {
      expect(screen.getByText('Ukraine conflict')).toBeInTheDocument()
      expect(screen.getByText('South China Sea')).toBeInTheDocument()
      expect(screen.getByText('Cybersecurity threats')).toBeInTheDocument()
      expect(screen.getByText('Border surveillance')).toBeInTheDocument()
    })
  })

  // ─────────────────────────────────────────────────────────────────────
  // Search
  // ─────────────────────────────────────────────────────────────────────

  it('has a search input', async () => {
    renderWithProviders(<TopicsDashboard />)
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument()
    })
  })

  it('filters topics by search query', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TopicsDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Ukraine conflict')).toBeInTheDocument()
    })

    const search = screen.getByPlaceholderText(/search/i)
    await user.type(search, 'china')

    await waitFor(() => {
      expect(screen.getByText('South China Sea')).toBeInTheDocument()
      expect(screen.queryByText('Ukraine conflict')).not.toBeInTheDocument()
      expect(screen.queryByText('Cybersecurity threats')).not.toBeInTheDocument()
    })
  })

  // ─────────────────────────────────────────────────────────────────────
  // Status filter chips
  // ─────────────────────────────────────────────────────────────────────

  it('has status filter chips: All, Active, Paused', async () => {
    renderWithProviders(<TopicsDashboard />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /All/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Active/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Paused/i })).toBeInTheDocument()
    })
  })

  it('shows counts on filter chips', async () => {
    renderWithProviders(<TopicsDashboard />)
    await waitFor(() => {
      // Active chip should show 2, Paused should show 2
      const activeChip = screen.getByRole('button', { name: /Active/i })
      expect(activeChip).toHaveTextContent('2')
      const pausedChip = screen.getByRole('button', { name: /Paused/i })
      expect(pausedChip).toHaveTextContent('2')
    })
  })

  it('filters by status when chip clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TopicsDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Ukraine conflict')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /Paused/i }))

    await waitFor(() => {
      expect(screen.getByText('Cybersecurity threats')).toBeInTheDocument()
      expect(screen.getByText('Border surveillance')).toBeInTheDocument()
      expect(screen.queryByText('Ukraine conflict')).not.toBeInTheDocument()
      expect(screen.queryByText('South China Sea')).not.toBeInTheDocument()
    })
  })

  // ─────────────────────────────────────────────────────────────────────
  // Sort
  // ─────────────────────────────────────────────────────────────────────

  it('has a sort dropdown with urgency as default', async () => {
    renderWithProviders(<TopicsDashboard />)
    await waitFor(() => {
      const sortSelect = screen.getByRole('combobox', { name: /sort/i })
      expect(sortSelect).toBeInTheDocument()
      expect(sortSelect).toHaveValue('urgency')
    })
  })

  it('sorts by most content', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(<TopicsDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Ukraine conflict')).toBeInTheDocument()
    })

    // Default filter is 'active' — click 'All' to include paused topics
    await user.click(screen.getByRole('button', { name: /All/i }))
    await waitFor(() => {
      expect(screen.getByText('Cybersecurity threats')).toBeInTheDocument()
    })

    const sortSelect = screen.getByRole('combobox', { name: /sort/i })
    await user.selectOptions(sortSelect, 'most_content')

    await waitFor(() => {
      const cards = container.querySelectorAll('article')
      expect(cards.length).toBe(4)
      // Ukraine (150) should be first, Border (20) last
      expect(cards[0]).toHaveTextContent('Ukraine conflict')
      expect(cards[cards.length - 1]).toHaveTextContent('Border surveillance')
    })
  })

  // ─────────────────────────────────────────────────────────────────────
  // Filtered count display
  // ─────────────────────────────────────────────────────────────────────

  it('shows total topic count in subtitle', async () => {
    renderWithProviders(<TopicsDashboard />)
    await waitFor(() => {
      expect(screen.getByText(/4 topics/i)).toBeInTheDocument()
    })
  })

  it('shows filtered count when search is active', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TopicsDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Ukraine conflict')).toBeInTheDocument()
    })

    // Search for an active topic so it's visible under the default 'active' filter
    const search = screen.getByPlaceholderText(/search/i)
    await user.type(search, 'ukraine')

    await waitFor(() => {
      expect(screen.getByText(/1 of 4 topics/i)).toBeInTheDocument()
    })
  })

  // ─────────────────────────────────────────────────────────────────────
  // Urgency badges
  // ─────────────────────────────────────────────────────────────────────

  it('shows signal badge on topics with unacked signals', async () => {
    renderWithProviders(<TopicsDashboard />)
    await waitFor(() => {
      // Ukraine has 8 signals
      expect(screen.getByLabelText('8 unacknowledged signals')).toBeInTheDocument()
      // South China Sea has 3 signals
      expect(screen.getByLabelText('3 unacknowledged signals')).toBeInTheDocument()
    })
  })

  it('hides signal badge when count is zero', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TopicsDashboard />)

    // Switch to paused to see Cybersecurity (0 signals)
    await waitFor(() => {
      expect(screen.getByText('Ukraine conflict')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /Paused/i }))

    await waitFor(() => {
      expect(screen.getByText('Cybersecurity threats')).toBeInTheDocument()
      // No signal badge for 0 signals
      expect(screen.queryByLabelText(/0 unacknowledged/)).not.toBeInTheDocument()
    })
  })

  it('shows new content badge for topics with recent content', async () => {
    renderWithProviders(<TopicsDashboard />)
    await waitFor(() => {
      expect(screen.getByText('+12 new')).toBeInTheDocument()
      expect(screen.getByText('+5 new')).toBeInTheDocument()
    })
  })

  it('shows source health dots', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TopicsDashboard />)

    // Active topics: Ukraine (healthy), South China Sea (degraded)
    await waitFor(() => {
      expect(screen.getByLabelText('Sources healthy')).toBeInTheDocument()
      expect(screen.getByLabelText('Sources degraded')).toBeInTheDocument()
    })

    // Switch to all to see down status
    await user.click(screen.getByRole('button', { name: /All/i }))
    await waitFor(() => {
      expect(screen.getByLabelText('Sources down')).toBeInTheDocument()
    })
  })

  // ─────────────────────────────────────────────────────────────────────
  // Urgency sort
  // ─────────────────────────────────────────────────────────────────────

  it('sorts by urgency: most signals first, then by recent activity', async () => {
    const { container } = renderWithProviders(<TopicsDashboard />)

    // Default sort = urgency, default filter = active
    // Active topics: Ukraine (8 signals), South China Sea (3 signals)
    await waitFor(() => {
      const cards = container.querySelectorAll('article')
      expect(cards.length).toBe(2)
      expect(cards[0]).toHaveTextContent('Ukraine conflict')
      expect(cards[1]).toHaveTextContent('South China Sea')
    })
  })

  // ─────────────────────────────────────────────────────────────────────
  // Empty/graceful state
  // ─────────────────────────────────────────────────────────────────────

  it('renders topic with no signals, no content, no sources gracefully', async () => {
    const { topicsApi } = await import('../../api/topics')
    vi.mocked(topicsApi.list).mockResolvedValueOnce([
      {
        id: 't-empty', name: 'Empty topic', status: 'active' as const,
        signal_threshold: 3, credibility_min: 30, created_at: '2026-07-01T00:00:00Z',
        content_count: 0, signal_count: 0,
        new_content_24h: 0, worst_source_health: 'healthy' as const,
        last_activity: null,
      },
    ])

    renderWithProviders(<TopicsDashboard />)
    await waitFor(() => {
      expect(screen.getByText('Empty topic')).toBeInTheDocument()
      // No signal or content badges rendered
      expect(screen.queryByLabelText(/unacknowledged/)).not.toBeInTheDocument()
      expect(screen.queryByText(/new$/)).not.toBeInTheDocument()
      // Falls back to "Created" timestamp
      expect(screen.getByText(/Created/)).toBeInTheDocument()
    })

    vi.mocked(topicsApi.list).mockResolvedValue(mockTopics)
  })

  it('shows last activity timestamp when available', async () => {
    renderWithProviders(<TopicsDashboard />)
    await waitFor(() => {
      // Both active topics have last_activity set
      const activities = screen.getAllByText(/Last activity/)
      expect(activities.length).toBeGreaterThanOrEqual(1)
    })
  })
})
