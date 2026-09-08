/**
 * Mobilization card body — issue #33.
 *
 * The matched phrase is always displayed so an analyst can verify the
 * extraction. Nothing on the card predicts that an event will occur.
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
  matched_phrase: 'Everyone gather at Town Square tomorrow at 4pm',
  pattern_id: 'en_gather_at',
  lexicon_version: 1,
  extracted_date: '2026-03-05',
  extracted_place: 'Town Square',
  item_count: 4,
  content_item_ids: ['ci-1', 'ci-2'],
}

function renderCard(evidence: any = EVIDENCE) {
  render(
    <MemoryRouter>
      <SignalCard
        signal={makeSignal({
          signal_type: 'mobilization_call',
          cluster_label: 'Assembly call',
          evidence,
        })}
        onAcknowledge={vi.fn()}
        onDismiss={vi.fn()}
      />
    </MemoryRouter>,
  )
}

describe('Mobilization card', () => {
  it('always shows the exact matched phrase', () => {
    renderCard()
    expect(
      screen.getByText('Everyone gather at Town Square tomorrow at 4pm'),
    ).toBeInTheDocument()
  })

  it('shows the extracted date and place', () => {
    renderCard()
    expect(screen.getByText('2026-03-05')).toBeInTheDocument()
    expect(screen.getByText('Town Square')).toBeInTheDocument()
  })

  it('says so when no date was in the text rather than guessing one', () => {
    renderCard({ ...EVIDENCE, extracted_date: null, extracted_place: null })
    expect(screen.getAllByText('none in the text').length).toBe(2)
  })

  it('still shows the phrase when nothing was extracted', () => {
    renderCard({ matched_phrase: 'Join us at the maidan' })
    expect(screen.getByText('Join us at the maidan')).toBeInTheDocument()
  })

  it('names the pattern and lexicon version so the analyst can check them', () => {
    renderCard()
    expect(screen.getByText(/en_gather_at/)).toBeInTheDocument()
    expect(screen.getByText(/lexicon v1/)).toBeInTheDocument()
  })

  it('never predicts that an event will occur', () => {
    renderCard()
    const body = document.body.textContent ?? ''
    expect(body).not.toMatch(/will occur|expected to|likely|probability|imminent|forecast/i)
  })

  it('renders without evidence', () => {
    renderCard(null)
    expect(screen.getByText('Assembly call')).toBeInTheDocument()
  })
})
