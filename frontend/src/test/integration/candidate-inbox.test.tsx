/**
 * Candidate Topic inbox — issues #26 and #27.
 *
 * Triage is a different task from monitoring, so this is its own top-level
 * page. The inbox shows why each candidate surfaced, ordered by how it is
 * spreading rather than by how concerning anything judges it to be.
 * See ADR 0001.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import CandidateInbox from '../../pages/CandidateInbox'

const mockList = vi.fn()
const mockAccept = vi.fn()
const mockDismiss = vi.fn()

vi.mock('../../api/candidates', () => ({
  candidatesApi: {
    list: (...args: any[]) => mockList(...args),
    accept: (...args: any[]) => mockAccept(...args),
    dismiss: (...args: any[]) => mockDismiss(...args),
  },
}))

const navigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<any>('react-router-dom')
  return { ...actual, useNavigate: () => navigate }
})

function makeCandidate(overrides = {}) {
  return {
    id: 'cand-1',
    cluster_id: 'cl-1',
    watch_space_id: 'ws-1',
    watch_space_name: 'Internal Security Tension',
    cluster_label: 'Fuel price protest across three districts',
    status: 'pending',
    independent_source_count: 4,
    item_count: 26,
    contributing_account_count: 11,
    novelty_score: 0.42,
    run_count: 3,
    evidence: { measurements: { thresholds: { min_independent_sources: 3 } } },
    created_at: '2026-03-01T00:00:00Z',
    promoted_topic_id: null,
    ...overrides,
  }
}

function renderInbox() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <CandidateInbox />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mockList.mockReset()
  mockAccept.mockReset()
  mockDismiss.mockReset()
  navigate.mockReset()
  mockAccept.mockResolvedValue({ candidate_id: 'cand-1', topic_id: 'new-topic', content_items_linked: 26 })
  mockDismiss.mockResolvedValue({ candidate_id: 'cand-1', status: 'dismissed' })
})

describe('The inbox shows why a candidate surfaced', () => {
  it('lists pending candidates', async () => {
    mockList.mockResolvedValue([makeCandidate()])
    renderInbox()
    await waitFor(() =>
      expect(screen.getByText('Fuel price protest across three districts')).toBeInTheDocument(),
    )
  })

  it('shows the measurements that produced it', async () => {
    mockList.mockResolvedValue([makeCandidate()])
    renderInbox()
    await waitFor(() => expect(screen.getByText('4')).toBeInTheDocument())
    expect(screen.getByText('26')).toBeInTheDocument()
    expect(screen.getByText('11')).toBeInTheDocument()
    expect(screen.getByText(/independent sources/i)).toBeInTheDocument()
  })

  it('shows the gate each measurement had to clear', async () => {
    // An analyst checks the arithmetic rather than trusting the outcome.
    mockList.mockResolvedValue([makeCandidate()])
    renderInbox()
    await waitFor(() => expect(screen.getByText(/gate 3/i)).toBeInTheDocument())
  })

  it('names the Watch Space that found it', async () => {
    mockList.mockResolvedValue([makeCandidate()])
    renderInbox()
    await waitFor(() =>
      expect(screen.getByText(/Internal Security Tension/)).toBeInTheDocument(),
    )
  })

  it('shows an empty state when nothing is waiting', async () => {
    mockList.mockResolvedValue([])
    renderInbox()
    await waitFor(() => expect(screen.getByText(/nothing waiting/i)).toBeInTheDocument())
  })

  it('orders by spread, never by concern', async () => {
    mockList.mockResolvedValue([
      makeCandidate({ id: 'a', cluster_label: 'Widely carried', independent_source_count: 6 }),
      makeCandidate({ id: 'b', cluster_label: 'Narrowly carried', independent_source_count: 2 }),
    ])
    renderInbox()
    await waitFor(() => expect(screen.getByText('Widely carried')).toBeInTheDocument())

    const body = document.body.textContent ?? ''
    expect(body.indexOf('Widely carried')).toBeLessThan(body.indexOf('Narrowly carried'))
    expect(body).not.toMatch(/concern/i)
  })
})

describe('Accepting and dismissing', () => {
  it('accepts a candidate', async () => {
    mockList.mockResolvedValue([makeCandidate()])
    renderInbox()
    await waitFor(() => expect(screen.getByLabelText(/accept/i)).toBeInTheDocument())
    fireEvent.click(screen.getByLabelText(/accept/i))
    await waitFor(() => expect(mockAccept).toHaveBeenCalledWith('cand-1', expect.anything()))
  })

  it('opens the new topic after accepting', async () => {
    mockList.mockResolvedValue([makeCandidate()])
    renderInbox()
    await waitFor(() => expect(screen.getByLabelText(/accept/i)).toBeInTheDocument())
    fireEvent.click(screen.getByLabelText(/accept/i))
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/topics/new-topic'))
  })

  it('dismisses a candidate', async () => {
    mockList.mockResolvedValue([makeCandidate()])
    renderInbox()
    await waitFor(() => expect(screen.getByLabelText(/dismiss/i)).toBeInTheDocument())
    fireEvent.click(screen.getByLabelText(/dismiss/i))
    await waitFor(() => expect(mockDismiss).toHaveBeenCalledWith('cand-1'))
  })

  it('says that nothing is monitored until a decision is made', async () => {
    mockList.mockResolvedValue([makeCandidate()])
    renderInbox()
    await waitFor(() =>
      expect(screen.getByText(/not monitored until you accept/i)).toBeInTheDocument(),
    )
  })
})
