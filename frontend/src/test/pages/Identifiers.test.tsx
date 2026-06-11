import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import Identifiers from '../../pages/Identifiers'
import { renderWithProviders } from '../test-utils'

// Mock the identifiers API
vi.mock('../../api/identifiers', () => ({
  identifiersApi: {
    top: vi.fn().mockResolvedValue([
      {
        entity_type: 'PHONE_IN',
        entity_text: '+919876543210',
        source_count: 5,
        content_item_count: 12,
        first_seen: '2026-06-01T10:00:00Z',
        last_seen: '2026-06-10T15:30:00Z',
      },
      {
        entity_type: 'UPI',
        entity_text: 'scammer@paytm',
        source_count: 3,
        content_item_count: 7,
        first_seen: '2026-06-02T08:00:00Z',
        last_seen: '2026-06-09T12:00:00Z',
      },
    ]),
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

describe('Identifiers page', () => {
  it('renders page title', () => {
    renderWithProviders(<Identifiers />)
    expect(screen.getByText('Identifiers')).toBeInTheDocument()
  })

  it('renders view mode tabs', () => {
    renderWithProviders(<Identifiers />)
    expect(screen.getByText('Top')).toBeInTheDocument()
    expect(screen.getByText('Clusters')).toBeInTheDocument()
    expect(screen.getByText('Search')).toBeInTheDocument()
  })

  it('renders type filter dropdown', () => {
    renderWithProviders(<Identifiers />)
    expect(screen.getByText('All types')).toBeInTheDocument()
  })

  it('shows prompt when no topic selected', () => {
    renderWithProviders(<Identifiers />)
    expect(screen.getByText('Select a topic to view identifiers.')).toBeInTheDocument()
  })

  it('renders top identifiers when topicId provided', async () => {
    renderWithProviders(<Identifiers topicId="topic-001" />)
    await waitFor(() => {
      expect(screen.getByText('+919876543210')).toBeInTheDocument()
      expect(screen.getByText('scammer@paytm')).toBeInTheDocument()
    })
  })

  it('renders source count column', async () => {
    renderWithProviders(<Identifiers topicId="topic-001" />)
    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument()
    })
  })

  it('renders type badges', async () => {
    renderWithProviders(<Identifiers topicId="topic-001" />)
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

  it('renders export button when topic selected', () => {
    renderWithProviders(<Identifiers topicId="topic-001" />)
    expect(screen.getByText('Export CSV')).toBeInTheDocument()
  })
})
