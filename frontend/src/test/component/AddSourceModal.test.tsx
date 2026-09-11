/**
 * Registering a Source - issue #51, ADR 0004.
 *
 * The structural rubric sets the credibility a Source starts at. The modal
 * used to send a number on every registration, which meant the rubric never
 * applied to anything added through the workbench: the API reads a stated
 * score as an explicit override, and 50 from an untouched slider is
 * indistinguishable from 50 an analyst chose.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AddSourceModal } from '../../components/sources/AddSourceModal'

vi.mock('../../api/topics', () => ({
  topicsApi: {
    list: vi.fn().mockResolvedValue([]),
  },
}))

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText(/source name/i), { target: { value: 'Declared Outlet' } })
  fireEvent.change(screen.getByLabelText(/url \/ handle/i), {
    target: { value: 'https://declared.example.in/feed' },
  })
}

describe('AddSourceModal credibility', () => {
  it('omits the score so the rubric decides', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<AddSourceModal open onClose={vi.fn()} onSubmit={onSubmit} />, { wrapper })

    fillRequiredFields()
    fireEvent.click(screen.getByRole('button', { name: /add source/i }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(onSubmit.mock.calls[0][0]).not.toHaveProperty('credibility_score')
  })

  it('says what sets the score when it is not being set by hand', () => {
    render(<AddSourceModal open onClose={vi.fn()} onSubmit={vi.fn()} />, { wrapper })
    expect(screen.getByText(/structural rubric/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/credibility score:/i)).not.toBeInTheDocument()
  })

  it('sends the score when an analyst sets it by hand', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<AddSourceModal open onClose={vi.fn()} onSubmit={onSubmit} />, { wrapper })

    fillRequiredFields()
    fireEvent.click(screen.getByLabelText(/set the initial credibility score by hand/i))
    fireEvent.change(screen.getByLabelText(/credibility score:/i), { target: { value: '73' } })
    fireEvent.click(screen.getByRole('button', { name: /add source/i }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ credibility_score: 73 })
  })
})
