import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ReportBuilder from '../../pages/ReportBuilder'
import { renderWithProviders } from '../test-utils'

const mockTopics = vi.hoisted(() => [
  {
    id: 't1', name: 'Ukraine conflict', status: 'active' as const,
    signal_threshold: 3, credibility_min: 30, created_at: '2026-01-15T00:00:00Z',
    content_count: 150, signal_count: 8,
    scheduled_report_cron: '0 9 * * *', scheduled_report_type: 'intelligence_brief',
  },
  {
    id: 't2', name: 'South China Sea', status: 'active' as const,
    signal_threshold: 2, credibility_min: 40, created_at: '2026-03-01T00:00:00Z',
    content_count: 90, signal_count: 3,
    scheduled_report_cron: null, scheduled_report_type: null,
  },
])

vi.mock('../../api/topics', () => ({
  topicsApi: {
    list: vi.fn().mockResolvedValue(mockTopics),
    create: vi.fn(),
    get: vi.fn(),
    updateStatus: vi.fn(),
    updateSchedule: vi.fn().mockResolvedValue({}),
  },
}))

vi.mock('../../api/reports', () => ({
  reportsApi: {
    create: vi.fn(),
    get: vi.fn(),
    listForTopic: vi.fn().mockResolvedValue({ items: [], total: 0, offset: 0, limit: 50 }),
    getGeojson: vi.fn(),
    downloadPdf: vi.fn(),
  },
}))

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

describe('ReportBuilder page', () => {
  // ─────────────────────────────────────────────────────────────────────
  // 2-column layout
  // ─────────────────────────────────────────────────────────────────────

  it('renders generation form on the left', async () => {
    renderWithProviders(<ReportBuilder />)
    await waitFor(() => {
      // The heading says "Generate report", the button says "Generate report"
      expect(screen.getByRole('heading', { name: /generate report/i })).toBeInTheDocument()
      expect(screen.getByLabelText(/topic/i)).toBeInTheDocument()
    })
  })

  // ─────────────────────────────────────────────────────────────────────
  // Tabs including Schedules
  // ─────────────────────────────────────────────────────────────────────

  it('has Report, GIS Map, History, and Schedules tabs', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReportBuilder />)

    // Wait for topics to load in the select
    await waitFor(() => {
      expect(screen.getByText('Ukraine conflict')).toBeInTheDocument()
    })

    const topicSelect = screen.getByLabelText(/topic/i)
    await user.selectOptions(topicSelect, 't1')

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /^Report$/i })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /gis/i })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /history/i })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /schedules/i })).toBeInTheDocument()
    })
  })

  it('shows schedule manager content when Schedules tab is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReportBuilder />)

    // Wait for topics to load
    await waitFor(() => {
      expect(screen.getByText('Ukraine conflict')).toBeInTheDocument()
    })

    const topicSelect = screen.getByLabelText(/topic/i)
    await user.selectOptions(topicSelect, 't1')

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /schedules/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('tab', { name: /schedules/i }))

    await waitFor(() => {
      // ScheduleManager should show scheduled topics
      expect(screen.getByText(/active schedules/i)).toBeInTheDocument()
    })
  })

  // ─────────────────────────────────────────────────────────────────────
  // Basic form elements
  // ─────────────────────────────────────────────────────────────────────

  it('has report type selector buttons', async () => {
    renderWithProviders(<ReportBuilder />)
    await waitFor(() => {
      expect(screen.getByText('Intelligence Brief')).toBeInTheDocument()
      expect(screen.getByText('Research Summary')).toBeInTheDocument()
      expect(screen.getByText('Weekly Digest')).toBeInTheDocument()
    })
  })

  it('has time window and credibility inputs', async () => {
    renderWithProviders(<ReportBuilder />)
    await waitFor(() => {
      expect(screen.getByLabelText(/time window/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/min.*credibility/i)).toBeInTheDocument()
    })
  })
})
