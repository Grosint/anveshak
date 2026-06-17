import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import Identifiers from '../../pages/Identifiers'
import { renderWithProviders } from '../test-utils'

// Mock the identifiers API
vi.mock('../../api/identifiers', () => ({
  identifiersApi: {
    top: vi.fn().mockResolvedValue([
      {
        identifier_type: 'PHONE_IN',
        identifier_value: '+919876543210',
        source_count: 5,
        content_item_count: 12,
        first_seen_at: '2026-06-01T10:00:00Z',
        last_seen_at: '2026-06-10T15:30:00Z',
      },
      {
        identifier_type: 'UPI',
        identifier_value: 'scammer@paytm',
        source_count: 3,
        content_item_count: 7,
        first_seen_at: '2026-06-02T08:00:00Z',
        last_seen_at: '2026-06-09T12:00:00Z',
      },
    ]),
    searchGlobal: vi.fn().mockResolvedValue([]),
    clusters: vi.fn().mockResolvedValue([]),
    search: vi.fn().mockResolvedValue([]),
    clusterDetail: vi.fn().mockResolvedValue(null),
    coOccurrence: vi.fn().mockResolvedValue({ items: [], count: 0 }),
  },
}))

// Mock contexts
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

vi.mock('../../contexts/WSContext', () => ({
  useWS: () => ({
    subscribe: (_cb: any) => () => {},
    status: 'disconnected',
  }),
  WSProvider: ({ children }: any) => children,
}))

describe('Identifiers page (embedded mode — standalone route removed)', () => {
  it('renders view mode tabs when embedded with topicId', () => {
    renderWithProviders(<Identifiers embedded topicId="topic-001" />)
    expect(screen.getByText('Top')).toBeInTheDocument()
    expect(screen.getByText('Clusters')).toBeInTheDocument()
    expect(screen.getByText('Search')).toBeInTheDocument()
  })

  it('renders type filter dropdown', () => {
    renderWithProviders(<Identifiers embedded topicId="topic-001" />)
    expect(screen.getByText('All types')).toBeInTheDocument()
  })

  it('renders top identifiers when topicId provided', async () => {
    renderWithProviders(<Identifiers embedded topicId="topic-001" />)
    await waitFor(() => {
      expect(screen.getByText('+919876543210')).toBeInTheDocument()
      expect(screen.getByText('scammer@paytm')).toBeInTheDocument()
    })
  })

  it('renders source count column', async () => {
    renderWithProviders(<Identifiers embedded topicId="topic-001" />)
    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument()
    })
  })

  it('renders type badges', async () => {
    renderWithProviders(<Identifiers embedded topicId="topic-001" />)
    await waitFor(() => {
      expect(screen.getByText('Phone')).toBeInTheDocument()
      expect(screen.getByText('UPI')).toBeInTheDocument()
    })
  })

  it('hides title when embedded', () => {
    renderWithProviders(<Identifiers embedded topicId="topic-001" />)
    // Should not render the h1
    expect(screen.queryByRole('heading', { level: 1 })).toBeNull()
  })

  it('always requires topicId (no standalone topic input)', () => {
    renderWithProviders(<Identifiers embedded topicId="topic-001" />)
    // No "Enter topic ID" input — embedded always has topicId from parent
    expect(screen.queryByPlaceholderText(/enter topic id/i)).not.toBeInTheDocument()
  })
})
