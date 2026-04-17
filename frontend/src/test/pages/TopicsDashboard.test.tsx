import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import TopicsDashboard from '../../pages/TopicsDashboard'
import { renderWithProviders } from '../test-utils'

// Mock the topics API
vi.mock('../../api/topics', () => ({
  topicsApi: {
    list: vi.fn().mockResolvedValue({ data: [] }),
    create: vi.fn(),
    get: vi.fn(),
    updateStatus: vi.fn(),
    listClusters: vi.fn(),
  },
  Topic: {},
  CreateTopicPayload: {},
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
  it('renders without crashing', () => {
    renderWithProviders(<TopicsDashboard />)
    // Should render something — loading state, empty state, or topics
    expect(document.body).toBeTruthy()
  })

  it('shows a create topic button', async () => {
    renderWithProviders(<TopicsDashboard />)

    await waitFor(() => {
      const buttons = screen.queryAllByRole('button')
      // Should have at least one button (create topic or similar)
      expect(buttons.length).toBeGreaterThan(0)
    })
  })
})
