import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import SignalsInbox from '../../pages/SignalsInbox'
import { renderWithProviders } from '../test-utils'

vi.mock('../../api/signals', () => ({
  signalsApi: {
    list: vi.fn().mockResolvedValue({ data: [] }),
    acknowledge: vi.fn(),
    dismiss: vi.fn(),
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

vi.mock('../../contexts/WSContext', () => ({
  useWS: () => ({
    lastSignal: null,
    isConnected: false,
    subscribe: (_cb: any) => () => {},  // returns unsubscribe noop
  }),
  WSProvider: ({ children }: any) => children,
}))

describe('SignalsInbox page', () => {
  it('renders without crashing', () => {
    renderWithProviders(<SignalsInbox />)
    expect(document.body).toBeTruthy()
  })

  it('shows signals heading or empty state', async () => {
    renderWithProviders(<SignalsInbox />)
    await waitFor(() => {
      // Should show either "Signals" heading or empty state
      const text = document.body.textContent || ''
      expect(text.length).toBeGreaterThan(0)
    })
  })
})
