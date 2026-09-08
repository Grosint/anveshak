/**
 * Manufactured Narrative card body — issue #32.
 *
 * The card shows the repeated claim across accounts and the arithmetic that
 * fired it, including which threshold was crossed and by how much. It
 * reports that the spread lacks independent sourcing. It never asserts the
 * narrative is false. See ADR 0001.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { SignalCard } from '../../components/signals/SignalCard'
import { makeSignal } from '../factories'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<any>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

const EVIDENCE = {
  cluster_id: 'cl-1',
  item_count: 42,
  account_count: 14,
  independent_source_count: 1,
  thresholds: { min_item_count: 15, min_account_count: 5, max_independent_sources: 2 },
  margins: { item_count: 27, account_count: 9, independent_sources_below_ceiling: 1 },
  repeated_claim: 'The same sentence, posted by fourteen accounts',
  content_item_ids: ['ci-1', 'ci-2', 'ci-3'],
}

function renderCard(evidence: any = EVIDENCE) {
  render(
    <MemoryRouter>
      <SignalCard
        signal={makeSignal({
          signal_type: 'manufactured_narrative',
          cluster_label: 'Fuel price claim',
          independent_source_count: 1,
          cluster_item_count: 42,
          evidence,
        })}
        onAcknowledge={vi.fn()}
        onDismiss={vi.fn()}
      />
    </MemoryRouter>,
  )
}

describe('Manufactured Narrative card', () => {
  it('shows the repeated claim', () => {
    renderCard()
    expect(
      screen.getByText(/The same sentence, posted by fourteen accounts/),
    ).toBeInTheDocument()
  })

  it('shows the arithmetic', () => {
    renderCard()
    expect(screen.getByText('42 items')).toBeInTheDocument()
    expect(screen.getByText('14 accounts')).toBeInTheDocument()
    expect(screen.getByText('1 independent sources')).toBeInTheDocument()
  })

  it('shows which threshold was crossed and by how much', () => {
    renderCard()
    expect(screen.getByText(/15/)).toBeInTheDocument()
    expect(screen.getByText(/\+27/)).toBeInTheDocument()
  })

  it('states that the spread lacks independent sourcing', () => {
    renderCard()
    expect(screen.getByText(/lacks independent sourcing/i)).toBeInTheDocument()
  })

  it('never asserts the narrative is false', () => {
    renderCard()
    const body = document.body.textContent ?? ''
    expect(body).not.toMatch(/false|fake|disinformation|misinformation|propaganda|hoax/i)
  })

  it('renders without evidence', () => {
    renderCard(null)
    expect(screen.getByText('Fuel price claim')).toBeInTheDocument()
  })

  it('renders an ordinary signal without the manufactured body', () => {
    render(
      <MemoryRouter>
        <SignalCard
          signal={makeSignal({ signal_type: 'multi_source_convergence', cluster_label: 'Ordinary' })}
          onAcknowledge={vi.fn()}
          onDismiss={vi.fn()}
        />
      </MemoryRouter>,
    )
    expect(screen.queryByText(/lacks independent sourcing/i)).not.toBeInTheDocument()
  })
})
