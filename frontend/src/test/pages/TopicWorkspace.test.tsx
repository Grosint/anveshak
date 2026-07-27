/**
 * Tests for the 3-view TopicWorkspace shell.
 *
 * Verifies: tab rendering, URL-driven view selection, provenance clear on
 * view switch, lazy map loading, and direct URL navigation.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import TopicWorkspace from '../../pages/TopicWorkspace'

// ── Mocks ───────────────────────────────────────────────────────────────

const mockClose = vi.fn()
const mockPush = vi.fn()

vi.mock('../../contexts/ProvenanceContext', () => ({
  useProvenance: () => ({
    isOpen: false,
    stack: [],
    current: null,
    push: mockPush,
    pop: vi.fn(),
    close: mockClose,
    jumpTo: vi.fn(),
  }),
}))

vi.mock('../../api/topics', () => ({
  topicsApi: {
    get: vi.fn().mockResolvedValue({
      id: 'topic-1',
      name: 'Test Topic',
      status: 'active',
      signal_threshold: 3,
      credibility_min: 30,
      created_at: '2026-05-01T00:00:00Z',
    }),
    listSources: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('../../api/content', () => ({
  contentApi: {
    list: vi.fn().mockResolvedValue([]),
    search: vi.fn().mockResolvedValue([]),
    get: vi.fn(),
    getVision: vi.fn(),
  },
  ContentFilters: {},
}))

vi.mock('../../api/intelligence', () => ({
  intelligenceApi: {
    topicIntelligence: vi.fn().mockResolvedValue({
      signals: [],
      clusters: [],
      identifiers: [],
      locations: [],
      recent_content: [],
      source_health: [],
    }),
    locationMap: vi.fn().mockResolvedValue({ type: 'FeatureCollection', features: [] }),
    listPins: vi.fn().mockResolvedValue([]),
    entityGraph: vi.fn().mockResolvedValue({ nodes: [], edges: [] }),
    topicStats: vi.fn().mockResolvedValue({}),
  },
}))

vi.mock('../../components/provenance/ProvenancePanel', () => ({
  ProvenancePanel: () => <div data-testid="provenance-panel">Provenance</div>,
}))

vi.mock('../../components/workspace/LocationMap', () => ({
  default: () => <div data-testid="location-map">Map View</div>,
}))

// ── Helpers ─────────────────────────────────────────────────────────────

function renderWorkspace(initialPath = '/topics/topic-1') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/topics/:topicId" element={<TopicWorkspace />} />
          <Route path="/topics/:topicId/content" element={<TopicWorkspace />} />
          <Route path="/topics/:topicId/map" element={<TopicWorkspace />} />
          <Route path="/topics/:topicId/feed" element={<TopicWorkspace />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ── Tests ───────────────────────────────────────────────────────────────

describe('TopicWorkspace 3-view shell', () => {
  it('renders 3 view tabs', async () => {
    renderWorkspace()

    await waitFor(() => {
      expect(screen.getByText('Intelligence')).toBeInTheDocument()
      expect(screen.getByText('Content')).toBeInTheDocument()
      expect(screen.getByText('Map')).toBeInTheDocument()
    })

    // Old tabs should NOT be present
    expect(screen.queryByText('Clusters')).not.toBeInTheDocument()
    expect(screen.queryByText('Identifiers')).not.toBeInTheDocument()
    expect(screen.queryByText('Reports')).not.toBeInTheDocument()
    expect(screen.queryByText('Sources')).not.toBeInTheDocument()
  })

  it('defaults to Intelligence view at /topics/:topicId', async () => {
    renderWorkspace('/topics/topic-1')

    await waitFor(() => {
      const tab = screen.getByText('Intelligence')
      expect(tab).toHaveAttribute('aria-current', 'page')
    })
  })

  it('shows Content view at /topics/:topicId/content', async () => {
    renderWorkspace('/topics/topic-1/content')

    await waitFor(() => {
      const tab = screen.getByText('Content')
      expect(tab).toHaveAttribute('aria-current', 'page')
    })
  })

  it('shows Map view at /topics/:topicId/map', async () => {
    renderWorkspace('/topics/topic-1/map')

    await waitFor(() => {
      const tab = screen.getByText('Map')
      expect(tab).toHaveAttribute('aria-current', 'page')
    })

    // Map lazy-loaded
    await waitFor(() => {
      expect(screen.getByTestId('location-map')).toBeInTheDocument()
    })
  })

  it('redirects old /feed URL to /content', async () => {
    // The /feed route is a redirect in App.tsx, but in isolated test
    // TopicWorkspace handles it via resolveWorkspaceView fallback
    renderWorkspace('/topics/topic-1/feed')

    await waitFor(() => {
      const tab = screen.getByText('Content')
      expect(tab).toHaveAttribute('aria-current', 'page')
    })
  })

  it('clears provenance panel on view switch', async () => {
    const user = userEvent.setup()
    renderWorkspace()

    await waitFor(() => {
      expect(screen.getByText('Content')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Content'))
    expect(mockClose).toHaveBeenCalled()
  })

  it('map is not loaded until Map tab clicked', async () => {
    renderWorkspace('/topics/topic-1')

    // Map should not be in DOM on Intelligence view
    expect(screen.queryByTestId('location-map')).not.toBeInTheDocument()
  })
})
