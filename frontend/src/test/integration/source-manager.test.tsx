/**
 * Integration tests for source manager seams:
 *
 * Seam 7: useQueries → warning counts mapped by array index (R10)
 * Seam 9: Source delete 409 → regex parse of content count (R9)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import SourceManager from '../../pages/SourceManager'
import { makeSource } from '../factories'

// ── Mocks ───────────────────────────────────────────────────────────────

const mockSourcesList = vi.fn()
const mockWarningsCount = vi.fn()
const mockDelete = vi.fn()

vi.mock('../../api/sources', () => ({
  sourcesApi: {
    list: (...args: any[]) => mockSourcesList(...args),
    create: vi.fn().mockResolvedValue({ id: 'new', name: 'New' }),
    updateCredibility: vi.fn(),
    getAuditLog: vi.fn().mockResolvedValue([]),
    toggleActive: vi.fn(),
    getReportWarningsCount: (...args: any[]) => mockWarningsCount(...args),
    checkHealth: vi.fn(),
    update: vi.fn(),
    delete: (...args: any[]) => mockDelete(...args),
  },
}))

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    token: 'test-jwt',
    user: { sub: 'analyst-1', exp: Math.floor(Date.now() / 1000) + 3600, iat: Math.floor(Date.now() / 1000) },
    login: vi.fn(),
    logout: vi.fn(),
    secondsUntilExpiry: 3600,
  }),
}))

function renderSourceManager() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SourceManager />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mockSourcesList.mockReset()
  mockWarningsCount.mockReset()
  mockDelete.mockReset()
})

// ── Seam 7: Warning counts by source.id (R10) ──────────────────────────

describe('Seam 7: Warning counts map to correct sources (R10)', () => {
  it('warning counts map by source id, not array index', async () => {
    const srcA = makeSource({ id: 'src-a', name: 'Source Alpha', health_status: 'healthy', credibility_score: 80 })
    const srcB = makeSource({ id: 'src-b', name: 'Source Beta', health_status: 'healthy', credibility_score: 60 })

    mockSourcesList.mockResolvedValue({ items: [srcA, srcB], total: 2, offset: 0, limit: 50 })

    // Source A has 3 warnings, Source B has 0
    mockWarningsCount.mockImplementation((sourceId: string) => {
      if (sourceId === 'src-a') return Promise.resolve({ source_id: 'src-a', warning_count: 3 })
      return Promise.resolve({ source_id: 'src-b', warning_count: 0 })
    })

    renderSourceManager()

    // Wait for sources to load
    await waitFor(() => {
      expect(screen.getByText('Source Alpha')).toBeInTheDocument()
      expect(screen.getByText('Source Beta')).toBeInTheDocument()
    })

    // Source Alpha should show the warning badge (⚠ 3)
    await waitFor(() => {
      expect(screen.getByText('⚠ 3')).toBeInTheDocument()
    })
  })
})

// ── Seam 9: Delete 409 → regex content count (R9) ─────────────────────

describe('Seam 9: Delete 409 error parsing (R9)', () => {
  it('extracts content count from 409 error message', async () => {
    const source = makeSource({ id: 'src-del', name: 'Deletable Source' })
    mockSourcesList.mockResolvedValue({ items: [source], total: 1, offset: 0, limit: 50 })
    mockWarningsCount.mockResolvedValue({ source_id: 'src-del', warning_count: 0 })

    // First delete attempt returns 409 with content count
    mockDelete.mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'Source has 42 content items linked' } },
    })

    renderSourceManager()

    // Wait for source to appear, then click to select it
    await waitFor(() => {
      expect(screen.getByText('Deletable Source')).toBeInTheDocument()
    })

    // Select the source to show detail panel
    fireEvent.click(screen.getByText('Deletable Source'))

    // Wait for detail panel, then click delete
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /delete source/i })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /delete source/i }))

    // Click confirm
    await waitFor(() => {
      expect(screen.getByText(/confirm delete|delete anyway/i)).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText(/confirm delete|delete anyway/i))

    // After 409, the content count should be extracted and displayed
    await waitFor(() => {
      expect(screen.getByText(/42 content item/)).toBeInTheDocument()
    })
  })
})
