import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import SignalsInbox from '../../pages/SignalsInbox'
import { renderWithProviders } from '../test-utils'

// Mock the signals API — returns unwrapped arrays (not { data: [] })
vi.mock('../../api/signals', () => ({
  signalsApi: {
    list: vi.fn().mockResolvedValue([]),
    acknowledge: vi.fn(),
    dismiss: vi.fn(),
  },
}))

// Mock AuthContext
vi.mock('../../contexts/AuthContext', () => ({
  AuthProvider: ({ children }: any) => children,
}))

vi.mock('../../contexts/auth', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    user: { sub: 'analyst-1', exp: Date.now() / 1000 + 3600, iat: Date.now() / 1000 },
    token: 'fake-token',
    secondsUntilExpiry: 3600,
  }),
}))

// Mock WSContext — matches real interface shape (subscribe/status, not isConnected/lastSignal)
vi.mock('../../contexts/WSContext', () => ({
  WSProvider: ({ children }: any) => children,
}))

vi.mock('../../contexts/ws', () => ({
  useWS: () => ({
    subscribe: (_cb: any) => () => {},
    status: 'disconnected',
  }),
}))

describe('SignalsInbox page', () => {
  it('renders signal status tabs', async () => {
    renderWithProviders(<SignalsInbox />)
    await waitFor(() => {
      expect(screen.getByText('New')).toBeInTheDocument()
      expect(screen.getByText('Acknowledged')).toBeInTheDocument()
    })
  })

  it('shows time filter presets', async () => {
    renderWithProviders(<SignalsInbox />)
    await waitFor(() => {
      expect(screen.getByText('7 days')).toBeInTheDocument()
      expect(screen.getByText('30 days')).toBeInTheDocument()
    })
  })
})
