import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Login from '../../pages/Login'
import { renderWithProviders } from '../test-utils'

// Mock axios to prevent real HTTP calls
vi.mock('axios', () => ({
  default: {
    post: vi.fn(),
    create: vi.fn(() => ({
      interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
    })),
  },
}))

// Mock AuthContext
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: false,
    login: vi.fn(),
    logout: vi.fn(),
    user: null,
    token: null,
    secondsUntilExpiry: null,
  }),
  AuthProvider: ({ children }: any) => children,
}))

describe('Login page', () => {
  it('renders username and password fields', () => {
    renderWithProviders(<Login />)

    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('renders a submit button', () => {
    renderWithProviders(<Login />)

    const button = screen.getByRole('button', { name: /sign in|log in|enter/i })
    expect(button).toBeInTheDocument()
  })

  it('renders the brand mark', () => {
    renderWithProviders(<Login />)

    // The brand name "Anveshak" should appear somewhere on the login page
    const matches = screen.getAllByText(/anveshak/i)
    expect(matches.length).toBeGreaterThan(0)
  })

  it('username field accepts input', async () => {
    renderWithProviders(<Login />)
    const user = userEvent.setup()

    const input = screen.getByLabelText(/username/i)
    await user.type(input, 'analyst1')
    expect(input).toHaveValue('analyst1')
  })
})
