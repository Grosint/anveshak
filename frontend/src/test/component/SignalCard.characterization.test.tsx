/**
 * Characterization tests for SignalCard — pinned before the #31 restyle.
 *
 * These pin the behaviour that must survive the restyle. Severity styling
 * and titles change deliberately in #31 and are covered by
 * signal-presentation.test.tsx instead; everything here must not move.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { SignalCard } from '../../components/signals/SignalCard'
import { makeSignal } from '../factories'

const navigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<any>('react-router-dom')
  return { ...actual, useNavigate: () => navigate }
})

function renderCard(overrides = {}, handlers = {}) {
  const signal = makeSignal({
    cluster_label: 'Fuel price protest across three districts',
    independent_source_count: 3,
    cluster_item_count: 12,
    sources: [
      { source_name: 'The Hindu', platform: 'rss', credibility_score: 80 },
      { source_name: 'r/india', platform: 'reddit', credibility_score: 40 },
    ],
    ...overrides,
  })
  const onAcknowledge = vi.fn()
  const onDismiss = vi.fn()
  render(
    <MemoryRouter>
      <SignalCard
        signal={signal}
        onAcknowledge={onAcknowledge}
        onDismiss={onDismiss}
        {...handlers}
      />
    </MemoryRouter>,
  )
  return { signal, onAcknowledge, onDismiss }
}

describe('SignalCard behaviour that must not regress', () => {
  it('shows the narrative label', () => {
    renderCard()
    expect(screen.getByText('Fuel price protest across three districts')).toBeInTheDocument()
  })

  it('lists every contributing source', () => {
    renderCard()
    expect(screen.getByText(/The Hindu/)).toBeInTheDocument()
    expect(screen.getByText(/r\/india/)).toBeInTheDocument()
  })

  it('shows the item count', () => {
    renderCard()
    expect(screen.getByText('12')).toBeInTheDocument()
  })

  it('acknowledges a new signal', () => {
    const { signal, onAcknowledge } = renderCard({ status: 'new' })
    fireEvent.click(screen.getByLabelText('Acknowledge signal'))
    expect(onAcknowledge).toHaveBeenCalledWith(signal.id)
  })

  it('dismisses a signal', () => {
    const { signal, onDismiss } = renderCard({ status: 'new' })
    fireEvent.click(screen.getByLabelText('Dismiss signal'))
    expect(onDismiss).toHaveBeenCalledWith(signal.id)
  })

  it('offers no actions on a dismissed signal', () => {
    renderCard({ status: 'dismissed' })
    expect(screen.queryByLabelText('Acknowledge signal')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Dismiss signal')).not.toBeInTheDocument()
  })

  it('offers no acknowledge on an already acknowledged signal', () => {
    renderCard({ status: 'acknowledged' })
    expect(screen.queryByLabelText('Acknowledge signal')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Dismiss signal')).toBeInTheDocument()
  })

  it('navigates to the topic on click', () => {
    navigate.mockClear()
    const { signal } = renderCard()
    fireEvent.click(screen.getByRole('button', { name: /click to view topic feed/i }))
    expect(navigate).toHaveBeenCalledWith(`/topics/${signal.topic_id}`)
  })

  it('marks an unread signal', () => {
    renderCard({ status: 'new' })
    expect(screen.getByLabelText('Unread')).toBeInTheDocument()
  })

  it('renders without sources or counts', () => {
    renderCard({ sources: [], independent_source_count: null, cluster_item_count: null })
    expect(screen.getByText('Fuel price protest across three districts')).toBeInTheDocument()
  })
})
