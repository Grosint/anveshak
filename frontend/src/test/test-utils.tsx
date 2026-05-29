/**
 * Shared test utilities — wraps components with required providers.
 *
 * Provides: AuthContext (configurable), WSContext (configurable),
 * React Router (MemoryRouter), React Query.
 */
import React, { ReactElement, createContext, useContext } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { MemoryRouter, MemoryRouterProps } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// ── Auth context mock ───────────────────────────────────────────────────

interface MockAuthState {
  isAuthenticated: boolean
  user: { sub: string; exp: number; iat: number; role?: string } | null
  token: string | null
  secondsUntilExpiry: number | null
  login: (token: string) => void
  logout: () => void
}

const defaultAuthState: MockAuthState = {
  isAuthenticated: true,
  user: { sub: 'analyst-1', exp: Math.floor(Date.now() / 1000) + 3600, iat: Math.floor(Date.now() / 1000), role: 'analyst' },
  token: 'fake-token',
  secondsUntilExpiry: 3600,
  login: () => {},
  logout: () => {},
}

// ── WS context mock ────────────────────────────────────────────────────

interface MockWSState {
  subscribe: (handler: any) => () => void
  status: 'connected' | 'disconnected' | 'connecting'
}

const defaultWSState: MockWSState = {
  subscribe: () => () => {},
  status: 'disconnected',
}

// ── Query client ────────────────────────────────────────────────────────

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

// ── Render with providers ───────────────────────────────────────────────

interface WrapperProps {
  children: React.ReactNode
}

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  routerProps?: MemoryRouterProps
  authState?: Partial<MockAuthState>
  wsState?: Partial<MockWSState>
}

/**
 * Create a mock JWT token payload for testing.
 */
export function mockJWTToken(sub: string = 'analyst-1'): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const payload = btoa(
    JSON.stringify({
      sub,
      exp: Math.floor(Date.now() / 1000) + 3600,
      iat: Math.floor(Date.now() / 1000),
    }),
  )
  return `${header}.${payload}.fake-signature`
}

/**
 * Render with all providers needed by page components.
 */
export function renderWithProviders(
  ui: ReactElement,
  options: CustomRenderOptions = {},
) {
  const { routerProps, authState, wsState, ...renderOptions } = options
  const queryClient = createTestQueryClient()

  function Wrapper({ children }: WrapperProps) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter {...routerProps}>{children}</MemoryRouter>
      </QueryClientProvider>
    )
  }

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient,
  }
}
