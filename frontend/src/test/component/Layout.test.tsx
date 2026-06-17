import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import Layout from '../../components/ui/Layout'
import { renderWithProviders } from '../test-utils'

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    user: { sub: 'admin_kaur', role: 'analyst', exp: Date.now() / 1000 + 3600, iat: Date.now() / 1000 },
    token: 'fake-token',
    secondsUntilExpiry: 3600,
  }),
  AuthProvider: ({ children }: any) => children,
}))

vi.mock('../../contexts/WSContext', () => ({
  useWS: () => ({ subscribe: () => () => {}, status: 'connected' }),
  WSProvider: ({ children }: any) => children,
}))

vi.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ toggle: vi.fn(), isDark: true }),
  ThemeProvider: ({ children }: any) => children,
}))

vi.mock('../../api/sources', () => ({
  sourcesApi: {
    list: vi.fn().mockResolvedValue([]),
  },
}))

// Both desktop sidebar and mobile bottom nav render links — jsdom sees both.
// Use getAllByRole and check length >= 1 for nav items.

describe('Layout sidebar navigation', () => {
  // ─────────────────────────────────────────────────────────────────────
  // Primary nav items (5) — each rendered twice (desktop + mobile)
  // ─────────────────────────────────────────────────────────────────────

  it('has Topics nav link', () => {
    renderWithProviders(<Layout />)
    expect(screen.getAllByRole('link', { name: /topics/i }).length).toBeGreaterThanOrEqual(1)
  })

  it('has Signals nav link', () => {
    renderWithProviders(<Layout />)
    expect(screen.getAllByRole('link', { name: /signals/i }).length).toBeGreaterThanOrEqual(1)
  })

  it('has Vision nav link', () => {
    renderWithProviders(<Layout />)
    expect(screen.getAllByRole('link', { name: /vision/i }).length).toBeGreaterThanOrEqual(1)
  })

  it('has Reports nav link', () => {
    renderWithProviders(<Layout />)
    expect(screen.getAllByRole('link', { name: /reports/i }).length).toBeGreaterThanOrEqual(1)
  })

  it('has Analytics nav link', () => {
    renderWithProviders(<Layout />)
    expect(screen.getAllByRole('link', { name: /analytics/i }).length).toBeGreaterThanOrEqual(1)
  })

  // ─────────────────────────────────────────────────────────────────────
  // Settings nav item (after separator)
  // ─────────────────────────────────────────────────────────────────────

  it('has Settings nav link', () => {
    renderWithProviders(<Layout />)
    expect(screen.getAllByRole('link', { name: /settings/i }).length).toBeGreaterThanOrEqual(1)
  })

  // ─────────────────────────────────────────────────────────────────────
  // Removed nav items — should NOT exist
  // ─────────────────────────────────────────────────────────────────────

  it('does NOT have Sources as a standalone nav link', () => {
    renderWithProviders(<Layout />)
    const links = screen.getAllByRole('link')
    const sourcesLinks = links.filter((l) => l.textContent?.trim() === 'Sources')
    expect(sourcesLinks).toHaveLength(0)
  })

  it('does NOT have Users as a standalone nav link', () => {
    renderWithProviders(<Layout />)
    const links = screen.getAllByRole('link')
    const usersLinks = links.filter((l) => l.textContent?.trim() === 'Users')
    expect(usersLinks).toHaveLength(0)
  })

  it('does NOT have Schedules as a standalone nav link', () => {
    renderWithProviders(<Layout />)
    const links = screen.getAllByRole('link')
    const schedLinks = links.filter((l) => l.textContent?.trim() === 'Schedules')
    expect(schedLinks).toHaveLength(0)
  })

  it('does NOT have Identifiers as a standalone nav link', () => {
    renderWithProviders(<Layout />)
    const links = screen.getAllByRole('link')
    const idLinks = links.filter((l) => l.textContent?.trim() === 'Identifiers')
    expect(idLinks).toHaveLength(0)
  })

  it('has a global identifier search button', () => {
    renderWithProviders(<Layout />)
    expect(screen.getByRole('button', { name: /search identifiers/i })).toBeInTheDocument()
  })

  // ─────────────────────────────────────────────────────────────────────
  // User footer
  // ─────────────────────────────────────────────────────────────────────

  it('shows user initials circle', () => {
    renderWithProviders(<Layout />)
    // "admin_kaur" → "AK"
    expect(screen.getByText('AK')).toBeInTheDocument()
  })

  it('shows username in footer', () => {
    renderWithProviders(<Layout />)
    expect(screen.getByText('admin_kaur')).toBeInTheDocument()
  })

  it('has a sign out button', () => {
    renderWithProviders(<Layout />)
    expect(screen.getByRole('button', { name: /sign out/i })).toBeInTheDocument()
  })

  it('shows user role in sidebar instead of "Signed in"', () => {
    renderWithProviders(<Layout />)
    expect(screen.getByText('Analyst')).toBeInTheDocument()
    expect(screen.queryByText('Signed in')).not.toBeInTheDocument()
  })
})
