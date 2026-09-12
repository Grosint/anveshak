/**
 * Shared test utilities — wraps components with required providers.
 *
 * Provides: React Router (MemoryRouter) and React Query.
 */
import React, { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { MemoryRouter, MemoryRouterProps } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

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
  const { routerProps, ...renderOptions } = options
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
