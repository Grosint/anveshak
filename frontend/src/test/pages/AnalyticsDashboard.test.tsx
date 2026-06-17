import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import AnalyticsDashboard from '../../pages/AnalyticsDashboard'
import { renderWithProviders } from '../test-utils'

const mockHealth = vi.hoisted(() => ({
  content_items_total: 500,
  content_items_last_24h: 25,
  content_items_embedded: 480,
  narrative_clusters_total: 12,
  signals_last_30d: 8,
  reports_last_30d: 3,
  sources_active: 10,
  sources_down: 2,
  content_items_zh: 0,
  content_items_translated: 0,
  extracted_entities_zh: 0,
}))

const mockSources = vi.hoisted(() => [
  { id: 's1', name: 'Source 1', platform: 'web', health_status: 'healthy', credibility_score: 80, url_or_handle: 'https://example.com', topic_links_count: 1, consecutive_failures: 0 },
  { id: 's2', name: 'Source 2', platform: 'web', health_status: 'healthy', credibility_score: 70, url_or_handle: 'https://test.com', topic_links_count: 1, consecutive_failures: 0 },
  { id: 's3', name: 'Source 3', platform: 'rss', health_status: 'degraded', credibility_score: 50, url_or_handle: 'https://rss.com', topic_links_count: 2, consecutive_failures: 1 },
  { id: 's4', name: 'Source 4', platform: 'telegram', health_status: 'down', credibility_score: 30, url_or_handle: 't.me/test', topic_links_count: 0, consecutive_failures: 5 },
  { id: 's5', name: 'Source 5', platform: 'reddit', health_status: 'healthy', credibility_score: 60, url_or_handle: 'r/osint', topic_links_count: 1, consecutive_failures: 0 },
])

vi.mock('../../api/system', () => ({
  systemApi: {
    pipelineHealth: vi.fn().mockResolvedValue(mockHealth),
  },
}))

vi.mock('../../api/topics', () => ({
  topicsApi: {
    list: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('../../api/sources', () => ({
  sourcesApi: {
    list: vi.fn().mockResolvedValue(mockSources),
  },
}))

vi.mock('../../api/identifiers', () => ({
  identifiersApi: {
    convergence: vi.fn().mockResolvedValue([
      {
        identifier_type: 'PHONE_IN',
        identifier_value: '+919876543210',
        topic_count: 3,
        total_source_count: 8,
        topic_names: ['Cyber Fraud Ring X', 'UPI Scam Network', 'Phone Fraud Cases'],
      },
      {
        identifier_type: 'UPI',
        identifier_value: 'scammer@ybl',
        topic_count: 2,
        total_source_count: 5,
        topic_names: ['Cyber Fraud Ring X', 'UPI Scam Network'],
      },
    ]),
    searchGlobal: vi.fn().mockResolvedValue([]),
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

describe('AnalyticsDashboard page', () => {
  // ─────────────────────────────────────────────────────────────────────
  // Stat cards (existing)
  // ─────────────────────────────────────────────────────────────────────

  it('renders pipeline stat cards', async () => {
    renderWithProviders(<AnalyticsDashboard />)
    await waitFor(() => {
      expect(screen.getByText('500')).toBeInTheDocument()  // Content Items
      expect(screen.getByText('12')).toBeInTheDocument()   // Clusters
    })
  })

  // ─────────────────────────────────────────────────────────────────────
  // Source Health chart section
  // ─────────────────────────────────────────────────────────────────────

  it('renders Source Health Distribution section', async () => {
    renderWithProviders(<AnalyticsDashboard />)
    await waitFor(() => {
      expect(screen.getByText(/source health distribution/i)).toBeInTheDocument()
    })
  })

  // ─────────────────────────────────────────────────────────────────────
  // Platform Distribution chart section
  // ─────────────────────────────────────────────────────────────────────

  it('renders Platform Distribution section', async () => {
    renderWithProviders(<AnalyticsDashboard />)
    await waitFor(() => {
      expect(screen.getByText(/sources by platform/i)).toBeInTheDocument()
    })
  })

  // ─────────────────────────────────────────────────────────────────────
  // Topic list should be removed
  // ─────────────────────────────────────────────────────────────────────

  it('does NOT render Topics section', async () => {
    renderWithProviders(<AnalyticsDashboard />)
    await waitFor(() => {
      expect(screen.getByText('500')).toBeInTheDocument()  // wait for load
    })
    expect(screen.queryByText(/Topics \(/)).not.toBeInTheDocument()
  })

  // ─────────────────────────────────────────────────────────────────────
  // Convergence card
  // ─────────────────────────────────────────────────────────────────────

  it('renders Cross-Topic Convergence section', async () => {
    renderWithProviders(<AnalyticsDashboard />)
    await waitFor(() => {
      expect(screen.getByText(/cross-topic convergence/i)).toBeInTheDocument()
    })
  })

  it('shows converging identifier values', async () => {
    renderWithProviders(<AnalyticsDashboard />)
    await waitFor(() => {
      expect(screen.getByText('+919876543210')).toBeInTheDocument()
      expect(screen.getByText('scammer@ybl')).toBeInTheDocument()
    })
  })

  it('shows topic count for converging identifiers', async () => {
    renderWithProviders(<AnalyticsDashboard />)
    await waitFor(() => {
      // "3 topics" for the phone number
      expect(screen.getByText(/3 topics/i)).toBeInTheDocument()
    })
  })

  it('shows topic names for converging identifiers', async () => {
    renderWithProviders(<AnalyticsDashboard />)
    await waitFor(() => {
      // "Cyber Fraud Ring X" appears in both rows' topic_names
      expect(screen.getAllByText(/Cyber Fraud Ring X/).length).toBeGreaterThanOrEqual(1)
    })
  })
})
