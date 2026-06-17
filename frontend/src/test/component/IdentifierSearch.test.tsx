import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import IdentifierSearch from '../../components/search/IdentifierSearch'
import { renderWithProviders } from '../test-utils'

// Mock identifiers API
vi.mock('../../api/identifiers', () => ({
  identifiersApi: {
    searchGlobal: vi.fn().mockResolvedValue([
      {
        identifier_type: 'PHONE_IN',
        identifier_value: '+919876543210',
        topic_id: 'topic-001',
        topic_name: 'Cyber Fraud Ring X',
        source_count: 5,
        content_item_count: 12,
        last_seen_at: '2026-06-10T15:30:00Z',
      },
      {
        identifier_type: 'UPI',
        identifier_value: 'scammer@paytm',
        topic_id: 'topic-002',
        topic_name: 'UPI Fraud Network',
        source_count: 3,
        content_item_count: 7,
        last_seen_at: '2026-06-09T12:00:00Z',
      },
    ]),
    top: vi.fn().mockResolvedValue([]),
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
    user: { sub: 'analyst-1', exp: Date.now() / 1000 + 3600, iat: Date.now() / 1000, role: 'analyst' },
    token: 'fake-token',
    secondsUntilExpiry: 3600,
  }),
  AuthProvider: ({ children }: any) => children,
}))

vi.mock('../../contexts/WSContext', () => ({
  useWS: () => ({ subscribe: () => () => {}, status: 'disconnected' }),
  WSProvider: ({ children }: any) => children,
}))

// Mock navigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

describe('IdentifierSearch modal', () => {
  const onClose = vi.fn()

  it('renders search input', () => {
    renderWithProviders(<IdentifierSearch open onClose={onClose} />)
    expect(screen.getByPlaceholderText(/search identifier/i)).toBeInTheDocument()
  })

  it('renders type filter dropdown', () => {
    renderWithProviders(<IdentifierSearch open onClose={onClose} />)
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('does not render when open=false', () => {
    renderWithProviders(<IdentifierSearch open={false} onClose={onClose} />)
    expect(screen.queryByPlaceholderText(/search identifier/i)).not.toBeInTheDocument()
  })

  it('shows results after typing', async () => {
    renderWithProviders(<IdentifierSearch open onClose={onClose} />)
    const input = screen.getByPlaceholderText(/search identifier/i)
    await userEvent.type(input, '9876543210')

    await waitFor(() => {
      expect(screen.getByText('+919876543210')).toBeInTheDocument()
      expect(screen.getByText('Cyber Fraud Ring X')).toBeInTheDocument()
    })
  })

  it('shows topic name in results', async () => {
    renderWithProviders(<IdentifierSearch open onClose={onClose} />)
    const input = screen.getByPlaceholderText(/search identifier/i)
    await userEvent.type(input, '9876543210')

    await waitFor(() => {
      expect(screen.getByText('UPI Fraud Network')).toBeInTheDocument()
    })
  })

  it('shows source count in results', async () => {
    renderWithProviders(<IdentifierSearch open onClose={onClose} />)
    const input = screen.getByPlaceholderText(/search identifier/i)
    await userEvent.type(input, '9876543210')

    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument()
    })
  })

  it('closes on Escape key', async () => {
    renderWithProviders(<IdentifierSearch open onClose={onClose} />)
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })

  it('has a close button', () => {
    renderWithProviders(<IdentifierSearch open onClose={onClose} />)
    expect(screen.getByRole('button', { name: /close/i })).toBeInTheDocument()
  })

  it('renders title', () => {
    renderWithProviders(<IdentifierSearch open onClose={onClose} />)
    expect(screen.getByText(/search identifiers/i)).toBeInTheDocument()
  })
})
