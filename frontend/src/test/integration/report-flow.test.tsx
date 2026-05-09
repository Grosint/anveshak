/**
 * Integration tests for report generation seam:
 *
 * Seam 8: Generate → poll → render markdown
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import ReportBuilder from '../../pages/ReportBuilder'
import { makeReport } from '../factories'

const mockReportCreate = vi.fn()
const mockReportGet = vi.fn()

vi.mock('../../api/reports', () => ({
  reportsApi: {
    create: (...args: any[]) => mockReportCreate(...args),
    get: (...args: any[]) => mockReportGet(...args),
    listForTopic: vi.fn().mockResolvedValue([]),
    getGeojson: vi.fn().mockResolvedValue({ type: 'FeatureCollection', features: [] }),
    downloadPdf: vi.fn(),
  },
}))

vi.mock('../../api/topics', () => ({
  topicsApi: {
    list: vi.fn().mockResolvedValue([
      { id: 't-1', name: 'Test Topic', status: 'active', signal_threshold: 3, credibility_min: 30, created_at: '2026-05-01T00:00:00Z' },
    ]),
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

function renderReportBuilder() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ReportBuilder />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mockReportCreate.mockReset()
  mockReportGet.mockReset()
})

describe('Seam 8: Generate → poll → display', () => {
  it('generate button is disabled until topic is selected', async () => {
    renderReportBuilder()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /generate report/i })).toBeDisabled()
    })
  })

  it('selecting topic enables generate button', async () => {
    renderReportBuilder()

    // Wait for topics to load into select
    await waitFor(() => {
      expect(screen.getByText('Test Topic')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText(/topic/i), { target: { value: 't-1' } })

    expect(screen.getByRole('button', { name: /generate report/i })).not.toBeDisabled()
  })

  it('generate calls create API with correct payload', async () => {
    mockReportCreate.mockResolvedValue({
      report_id: 'rpt-1',
      status: 'queued',
      arq_job_id: 'arq-1',
    })
    mockReportGet.mockResolvedValue(makeReport({ id: 'rpt-1', generation_status: 'queued' }))

    renderReportBuilder()

    await waitFor(() => expect(screen.getByText('Test Topic')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText(/topic/i), { target: { value: 't-1' } })
    fireEvent.click(screen.getByRole('button', { name: /generate report/i }))

    await waitFor(() => {
      expect(mockReportCreate).toHaveBeenCalledWith(expect.objectContaining({
        topic_id: 't-1',
        report_type: 'intelligence_brief',
      }))
    })
  })
})
