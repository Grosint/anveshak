/**
 * Watch Space in the interface — issue #25.
 *
 * A Watch Space is a Topic in every technical respect, so it lists with the
 * other Topics rather than in a separate place. The analyst needs to tell
 * the two apart at a glance, because a Watch Space collects across a whole
 * domain and its content volume reads very differently.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import TopicsDashboard from '../../pages/TopicsDashboard'
import { CreateTopicModal } from '../../components/topics/CreateTopicModal'
import { makeTopic } from '../factories'

const mockTopicsList = vi.fn()
const mockCreate = vi.fn()

vi.mock('../../api/topics', () => ({
  topicsApi: {
    list: (...args: any[]) => mockTopicsList(...args),
    create: (...args: any[]) => mockCreate(...args),
    get: vi.fn(),
    updateStatus: vi.fn(),
    listClusters: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('../../contexts/auth', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    token: 'test-jwt',
    user: { sub: 'analyst-1', exp: Math.floor(Date.now() / 1000) + 3600, iat: Math.floor(Date.now() / 1000) },
    login: vi.fn(),
    logout: vi.fn(),
    secondsUntilExpiry: 3600,
  }),
}))

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TopicsDashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mockTopicsList.mockReset()
  mockCreate.mockReset()
  mockCreate.mockResolvedValue({ id: 'new-topic', name: 'New', status: 'active' })
})

describe('Identifying a Watch Space', () => {
  it('marks a Watch Space in the topic list', async () => {
    mockTopicsList.mockResolvedValue([
      makeTopic({ id: 'ws-1', name: 'Internal Security Tension', is_watch_space: true }),
    ])

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('Internal Security Tension')).toBeInTheDocument()
    })
    expect(screen.getByText('Watch Space')).toBeInTheDocument()
  })

  it('does not mark an ordinary topic', async () => {
    mockTopicsList.mockResolvedValue([
      makeTopic({ id: 't-1', name: 'Kerala Cyber Fraud Ring' }),
    ])

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('Kerala Cyber Fraud Ring')).toBeInTheDocument()
    })
    expect(screen.queryByText('Watch Space')).not.toBeInTheDocument()
  })

  it('lists a Watch Space alongside ordinary topics, not separately', async () => {
    mockTopicsList.mockResolvedValue([
      makeTopic({ id: 'ws-1', name: 'Internal Security Tension', is_watch_space: true }),
      makeTopic({ id: 't-1', name: 'Kerala Cyber Fraud Ring' }),
    ])

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('Internal Security Tension')).toBeInTheDocument()
    })
    expect(screen.getByText('Kerala Cyber Fraud Ring')).toBeInTheDocument()
  })
})

describe('Creating a Watch Space', () => {
  function renderModal(onSubmit = vi.fn().mockResolvedValue(undefined)) {
    render(<CreateTopicModal open onClose={vi.fn()} onSubmit={onSubmit} />)
    return onSubmit
  }

  it('offers a Watch Space option', () => {
    renderModal()
    expect(screen.getByLabelText(/watch space/i)).toBeInTheDocument()
  })

  it('creates an ordinary topic by default', async () => {
    const onSubmit = renderModal()

    fireEvent.change(screen.getByLabelText(/topic name/i), {
      target: { value: 'Kerala Cyber Fraud Ring' },
    })
    fireEvent.change(screen.getByPlaceholderText(/South China Sea/i), {
      target: { value: 'upi fraud' },
    })
    fireEvent.blur(screen.getByPlaceholderText(/South China Sea/i))
    fireEvent.submit(document.getElementById('create-topic-form')!)

    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(onSubmit.mock.calls[0][0].is_watch_space).toBe(false)
  })

  it('sends the marker when the option is selected', async () => {
    const onSubmit = renderModal()

    fireEvent.change(screen.getByLabelText(/topic name/i), {
      target: { value: 'Internal Security Tension' },
    })
    fireEvent.change(screen.getByPlaceholderText(/South China Sea/i), {
      target: { value: 'communal tension' },
    })
    fireEvent.blur(screen.getByPlaceholderText(/South China Sea/i))
    fireEvent.click(screen.getByLabelText(/watch space/i))
    fireEvent.submit(document.getElementById('create-topic-form')!)

    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(onSubmit.mock.calls[0][0].is_watch_space).toBe(true)
  })

  it('warns that Watch Space keywords must not name a target', () => {
    renderModal()
    fireEvent.click(screen.getByLabelText(/watch space/i))
    expect(
      screen.getByText(/name no specific organisation, party, or individual/i),
    ).toBeInTheDocument()
  })
})
