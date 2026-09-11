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
    listForTopic: vi.fn().mockResolvedValue({ items: [], total: 0, offset: 0, limit: 50 }),
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

describe('Seam 8b: report window selection', () => {
  async function selectTopic() {
    renderReportBuilder()
    await waitFor(() => expect(screen.getByText('Test Topic')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText(/topic/i), { target: { value: 't-1' } })
  }

  beforeEach(() => {
    mockReportCreate.mockResolvedValue({ report_id: 'rpt-1', status: 'queued', arq_job_id: 'arq-1' })
    mockReportGet.mockResolvedValue(makeReport({ id: 'rpt-1', generation_status: 'queued' }))
  })

  it('lookback preset sends time_window_hours and no explicit window', async () => {
    await selectTopic()
    fireEvent.click(screen.getByRole('button', { name: /lookback/i }))
    fireEvent.click(screen.getByRole('button', { name: /generate report/i }))

    await waitFor(() => expect(mockReportCreate).toHaveBeenCalled())
    const payload = mockReportCreate.mock.calls[0][0]
    expect(payload.time_window_hours).toBe(72)
    expect(payload.time_window_start).toBeUndefined()
    expect(payload.time_window_end).toBeUndefined()
  })

  it('date range mode sends explicit start and end instead of hours', async () => {
    await selectTopic()

    fireEvent.change(screen.getByLabelText(/^from$/i), { target: { value: '2026-01-01' } })
    fireEvent.change(screen.getByLabelText(/^to$/i), { target: { value: '2026-04-30' } })
    fireEvent.click(screen.getByRole('button', { name: /generate report/i }))

    await waitFor(() => expect(mockReportCreate).toHaveBeenCalled())
    const payload = mockReportCreate.mock.calls[0][0]
    expect(payload.time_window_hours).toBeUndefined()
    // UTC-anchored, so the window means the same thing in every timezone
    expect(payload.time_window_start).toBe('2026-01-01T00:00:00.000Z')
    expect(payload.time_window_end).toBe('2026-04-30T23:59:59.000Z')
  })

  it('date range mode blocks generation when a date is cleared', async () => {
    await selectTopic()

    // Opens prefilled, so a routine report needs no date entry
    expect(screen.getByRole('button', { name: /generate report/i })).not.toBeDisabled()

    fireEvent.change(screen.getByLabelText(/^from$/i), { target: { value: '' } })
    expect(screen.getByRole('button', { name: /generate report/i })).toBeDisabled()

    fireEvent.change(screen.getByLabelText(/^from$/i), { target: { value: '2026-01-01' } })
    fireEvent.change(screen.getByLabelText(/^to$/i), { target: { value: '' } })
    expect(screen.getByRole('button', { name: /generate report/i })).toBeDisabled()

    fireEvent.change(screen.getByLabelText(/^to$/i), { target: { value: '2026-04-30' } })
    expect(screen.getByRole('button', { name: /generate report/i })).not.toBeDisabled()
  })

  it('rejects an end date before the start date', async () => {
    await selectTopic()

    fireEvent.change(screen.getByLabelText(/^from$/i), { target: { value: '2026-04-30' } })
    fireEvent.change(screen.getByLabelText(/^to$/i), { target: { value: '2026-01-01' } })

    expect(screen.getByText(/end date must be on or after the start date/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /generate report/i })).toBeDisabled()
  })

  it('states the covered window on a completed report', async () => {
    mockReportGet.mockResolvedValue(
      makeReport({
        id: 'rpt-1',
        generation_status: 'complete',
        generated_at: '2026-05-01T10:00:00Z',
        time_window_start: '2026-01-01T00:00:00Z',
        time_window_end: '2026-04-30T12:00:00Z',
        content_md: '# Brief',
      }),
    )
    await selectTopic()
    fireEvent.click(screen.getByRole('button', { name: /generate report/i }))

    await waitFor(() => {
      expect(screen.getByText(/01 Jan 2026.*30 Apr 2026/)).toBeInTheDocument()
    })
  })
})
