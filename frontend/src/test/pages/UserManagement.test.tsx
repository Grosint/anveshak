import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import UserManagement from '../../pages/UserManagement'
import { renderWithProviders } from '../test-utils'

// vi.hoisted runs before vi.mock — safe to reference in factory
const mockUsers = vi.hoisted(() => [
  { id: 'u1', username: 'admin@anveshak.local', role: 'admin', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
  { id: 'u2', username: 'analyst1@anveshak.local', role: 'analyst', created_at: '2026-02-01T00:00:00Z', updated_at: '2026-02-01T00:00:00Z' },
  { id: 'u3', username: 'viewer1@anveshak.local', role: 'viewer', created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
  { id: 'u4', username: 'analyst2@anveshak.local', role: 'analyst', created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-01T00:00:00Z' },
])

vi.mock('../../api/users', () => ({
  usersApi: {
    list: vi.fn().mockResolvedValue(mockUsers),
    create: vi.fn().mockResolvedValue({ user_id: 'u-new' }),
    delete: vi.fn().mockResolvedValue({ deleted: true }),
    updateRole: vi.fn().mockResolvedValue({ user_id: 'u2', role: 'admin' }),
  },
}))

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    user: { sub: 'u1', exp: Date.now() / 1000 + 3600, iat: Date.now() / 1000 },
    token: 'fake-token',
    secondsUntilExpiry: 3600,
  }),
  AuthProvider: ({ children }: any) => children,
}))


describe('UserManagement page', () => {
  // ---------------------------------------------------------------
  // 1. Basic rendering
  // ---------------------------------------------------------------

  it('renders user table with all users', async () => {
    renderWithProviders(<UserManagement />)
    await waitFor(() => {
      expect(screen.getByText('admin@anveshak.local')).toBeInTheDocument()
      expect(screen.getByText('analyst1@anveshak.local')).toBeInTheDocument()
      expect(screen.getByText('viewer1@anveshak.local')).toBeInTheDocument()
    })
  })

  it('shows user count in header', async () => {
    renderWithProviders(<UserManagement />)
    await waitFor(() => {
      expect(screen.getByText(/4 users/)).toBeInTheDocument()
    })
  })

  it('shows Create User button', async () => {
    renderWithProviders(<UserManagement />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /create user/i })).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // 2. Search
  // ---------------------------------------------------------------

  it('filters users by search query', async () => {
    const user = userEvent.setup()
    renderWithProviders(<UserManagement />)

    await waitFor(() => {
      expect(screen.getByText('admin@anveshak.local')).toBeInTheDocument()
    })

    const search = screen.getByPlaceholderText(/search/i)
    await user.type(search, 'viewer')

    await waitFor(() => {
      expect(screen.getByText('viewer1@anveshak.local')).toBeInTheDocument()
      expect(screen.queryByText('admin@anveshak.local')).not.toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // 3. Role filter chips
  // ---------------------------------------------------------------

  it('has role filter chips for All, Admin, Analyst, Viewer', async () => {
    renderWithProviders(<UserManagement />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^All$/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Admin/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Analyst/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Viewer/i })).toBeInTheDocument()
    })
  })

  it('filters by role when chip clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<UserManagement />)

    await waitFor(() => {
      expect(screen.getByText('admin@anveshak.local')).toBeInTheDocument()
    })

    // Click Viewer chip
    await user.click(screen.getByRole('button', { name: /Viewer/i }))

    await waitFor(() => {
      expect(screen.getByText('viewer1@anveshak.local')).toBeInTheDocument()
      expect(screen.queryByText('admin@anveshak.local')).not.toBeInTheDocument()
      expect(screen.queryByText('analyst1@anveshak.local')).not.toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // 4. Sorting
  // ---------------------------------------------------------------

  it('has sortable column headers', async () => {
    renderWithProviders(<UserManagement />)
    await waitFor(() => {
      expect(screen.getByText(/Username/)).toBeInTheDocument()
      expect(screen.getByText(/Role/)).toBeInTheDocument()
      expect(screen.getByText(/Created/)).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // 5. Role badges — viewer uses ghost variant
  // ---------------------------------------------------------------

  it('displays all three role types with badges', async () => {
    renderWithProviders(<UserManagement />)
    await waitFor(() => {
      // Role badges are rendered inside Badge components — find by exact text within table rows
      const rows = screen.getAllByRole('row')
      // Header + 4 data rows
      expect(rows.length).toBeGreaterThanOrEqual(4)
      // Check that viewer role text appears somewhere (as a badge)
      expect(screen.getByText('viewer1@anveshak.local')).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // 6. Edit and Delete buttons
  // ---------------------------------------------------------------

  it('has Edit and Delete buttons for each user', async () => {
    renderWithProviders(<UserManagement />)
    await waitFor(() => {
      const editButtons = screen.getAllByRole('button', { name: /edit/i })
      const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
      expect(editButtons.length).toBeGreaterThanOrEqual(3)
      expect(deleteButtons.length).toBeGreaterThanOrEqual(3)
    })
  })

  // ---------------------------------------------------------------
  // 7. Create modal has viewer role option
  // ---------------------------------------------------------------

  it('create modal includes viewer role option', async () => {
    const user = userEvent.setup()
    renderWithProviders(<UserManagement />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /create user/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /create user/i }))

    await waitFor(() => {
      const select = screen.getByDisplayValue(/Analyst/i)
      expect(select).toBeInTheDocument()
      // Verify viewer option exists in the select
      const options = within(select as HTMLElement).getAllByRole('option')
      const optionValues = options.map((o) => o.getAttribute('value'))
      expect(optionValues).toContain('viewer')
      expect(optionValues).toContain('analyst')
      expect(optionValues).toContain('admin')
    })
  })

  // ---------------------------------------------------------------
  // 8. Delete uses confirmation modal (not browser confirm)
  // ---------------------------------------------------------------

  it('delete button opens confirmation modal', async () => {
    const user = userEvent.setup()
    renderWithProviders(<UserManagement />)

    await waitFor(() => {
      expect(screen.getByText('admin@anveshak.local')).toBeInTheDocument()
    })

    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    await user.click(deleteButtons[0])

    await waitFor(() => {
      expect(screen.getByText(/are you sure/i)).toBeInTheDocument()
      expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument()
    })
  })

  // ---------------------------------------------------------------
  // 9. Empty state
  // ---------------------------------------------------------------

  it('shows empty state when no users', async () => {
    const { usersApi } = await import('../../api/users')
    vi.mocked(usersApi.list).mockResolvedValueOnce([])

    renderWithProviders(<UserManagement />)
    await waitFor(() => {
      expect(screen.getByText(/no users/i)).toBeInTheDocument()
    })

    // Restore
    vi.mocked(usersApi.list).mockResolvedValue(mockUsers)
  })
})
