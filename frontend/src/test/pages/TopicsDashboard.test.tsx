import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import TopicsDashboard from '../../pages/TopicsDashboard'
import { renderWithProviders } from '../test-utils'

// Mock the topics API — returns unwrapped arrays (not { data: [] })
vi.mock('../../api/topics', () => ({
  topicsApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn(),
    get: vi.fn(),
    updateStatus: vi.fn(),
    listClusters: vi.fn(),
  },
}))

// Mock AuthContext
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
  it('shows empty state when no topics exist', async () => {
    renderWithProviders(<TopicsDashboard />)
    await waitFor(() => {
      expect(screen.getByText('No topics yet')).toBeInTheDocument()
    })
  })

  it('shows a "New topic" button', async () => {
    renderWithProviders(<TopicsDashboard />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /new topic|create/i })).toBeInTheDocument()
    })
  })
})
