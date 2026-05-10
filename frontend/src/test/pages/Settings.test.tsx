import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import Settings from '../../pages/Settings'
import { renderWithProviders } from '../test-utils'

// Mock the page components that Settings embeds
vi.mock('../../pages/SourceManager', () => ({
  default: (props: any) => (
    <div data-testid="source-manager" data-embedded={props.embedded}>
      SourceManager {props.embedded ? 'embedded' : 'standalone'}
    </div>
  ),
}))

vi.mock('../../pages/UserManagement', () => ({
  default: (props: any) => (
    <div data-testid="user-management" data-embedded={props.embedded}>
      UserManagement {props.embedded ? 'embedded' : 'standalone'}
    </div>
  ),
}))

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    user: { sub: 'admin-1', exp: Date.now() / 1000 + 3600, iat: Date.now() / 1000 },
    token: 'fake-token',
    secondsUntilExpiry: 3600,
  }),
  AuthProvider: ({ children }: any) => children,
}))

function renderSettings(initialPath = '/settings/sources') {
  return renderWithProviders(
    <Routes>
      <Route path="/settings/:tab" element={<Settings />} />
      <Route path="/settings" element={<Settings />} />
    </Routes>,
    { routerProps: { initialEntries: [initialPath] } },
  )
}

describe('Settings page', () => {
  // ─────────────────────────────────────────────────────────────────────
  // Basic rendering
  // ─────────────────────────────────────────────────────────────────────

  it('renders Settings heading', async () => {
    renderSettings()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('has Sources and Users tabs', async () => {
    renderSettings()
    expect(screen.getByRole('tab', { name: /sources/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /users/i })).toBeInTheDocument()
  })

  // ─────────────────────────────────────────────────────────────────────
  // Tab content
  // ─────────────────────────────────────────────────────────────────────

  it('shows SourceManager in embedded mode by default', async () => {
    renderSettings()
    const sm = screen.getByTestId('source-manager')
    expect(sm).toBeInTheDocument()
    expect(sm).toHaveTextContent('embedded')
  })

  it('shows UserManagement when Users tab is active', async () => {
    renderSettings('/settings/users')
    const um = screen.getByTestId('user-management')
    expect(um).toBeInTheDocument()
    expect(um).toHaveTextContent('embedded')
  })

  // ─────────────────────────────────────────────────────────────────────
  // Tab switching
  // ─────────────────────────────────────────────────────────────────────

  it('switches to Users tab on click', async () => {
    const user = userEvent.setup()
    renderSettings()

    expect(screen.getByTestId('source-manager')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /users/i }))

    await waitFor(() => {
      expect(screen.getByTestId('user-management')).toBeInTheDocument()
      expect(screen.queryByTestId('source-manager')).not.toBeInTheDocument()
    })
  })

  // ─────────────────────────────────────────────────────────────────────
  // Active tab styling
  // ─────────────────────────────────────────────────────────────────────

  it('marks Sources tab as selected when on sources route', async () => {
    renderSettings()
    const sourcesTab = screen.getByRole('tab', { name: /sources/i })
    expect(sourcesTab).toHaveAttribute('aria-selected', 'true')
  })
})
