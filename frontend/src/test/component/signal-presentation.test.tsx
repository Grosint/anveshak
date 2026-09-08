/**
 * Severity restyle and descriptive signal titles — issue #31, ADR 0001.
 *
 * A red CRITICAL badge on a narrative about a political group reads as a
 * verdict, and this system does not issue verdicts. Severity is computed
 * from propagation facts, so the definition survives; the presentation does
 * not. It becomes a neutral magnitude shown next to the arithmetic that
 * produced it, titles state what was measured, and evidence leads.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { SignalCard } from '../../components/signals/SignalCard'
import { signalTitle, severityMeasurement, SEVERITY_VARIANT } from '../../lib/domain'
import { makeSignal } from '../factories'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<any>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

function renderCard(overrides = {}) {
  const signal = makeSignal({
    cluster_label: 'Fuel price protest across three districts',
    independent_source_count: 3,
    cluster_item_count: 12,
    sources: [{ source_name: 'The Hindu', platform: 'rss', credibility_score: 80 }],
    ...overrides,
  })
  render(
    <MemoryRouter>
      <SignalCard signal={signal} onAcknowledge={vi.fn()} onDismiss={vi.fn()} />
    </MemoryRouter>,
  )
  return signal
}

describe('Titles state what was measured', () => {
  it('multi-source convergence reports the source count', () => {
    const signal = makeSignal({ signal_type: 'multi_source_convergence', independent_source_count: 4 })
    expect(signalTitle(signal)).toMatch(/4 independent sources/i)
  })

  it('cross-topic convergence reports the match', () => {
    const signal = makeSignal({ signal_type: 'cross_topic_convergence' })
    expect(signalTitle(signal)).toMatch(/matched/i)
  })

  it('a hostility shift reports the measured change', () => {
    const signal = makeSignal({
      signal_type: 'hostility_shift',
      evidence: { drop: 0.21, window_hours: 24 },
    })
    expect(signalTitle(signal)).toMatch(/hostility/i)
  })

  it('a manufactured narrative reports spread, never falsehood', () => {
    const signal = makeSignal({
      signal_type: 'manufactured_narrative',
      evidence: { item_count: 40, account_count: 12, independent_source_count: 1 },
    })
    const title = signalTitle(signal)
    expect(title).toMatch(/independent source/i)
    expect(title).not.toMatch(/false|fake|disinformation|propaganda|misleading/i)
  })

  it('a mobilization call reports what was said, never what will happen', () => {
    const signal = makeSignal({ signal_type: 'mobilization_call', evidence: { item_count: 4 } })
    const title = signalTitle(signal)
    expect(title).not.toMatch(/will|predict|expect|likely|imminent|risk of/i)
  })

  it('no title asserts a conclusion about content', () => {
    const types = [
      'multi_source_convergence',
      'cross_topic_convergence',
      'hostility_shift',
      'sentiment_shift',
      'manufactured_narrative',
      'mobilization_call',
      'identifier_convergence',
      'scam_template_match',
      'new_cluster',
    ]
    for (const signal_type of types) {
      const title = signalTitle(makeSignal({ signal_type, independent_source_count: 3 }))
      expect(title, signal_type).not.toMatch(
        /threat|danger|critical|alarming|extremist|dangerous|false|propaganda/i,
      )
    }
  })

  it('falls back to the signal type rather than inventing wording', () => {
    expect(signalTitle(makeSignal({ signal_type: 'something_new' }))).toMatch(/something new/i)
  })
})

describe('Severity reads as a magnitude, not an alarm', () => {
  it('no severity level renders in the danger colour', () => {
    for (const level of ['HIGH', 'MEDIUM', 'LOW']) {
      expect(SEVERITY_VARIANT[level]).not.toBe('danger')
    }
  })

  it('carries the arithmetic that produced it', () => {
    const signal = makeSignal({ signal_type: 'multi_source_convergence', independent_source_count: 4 })
    const measurement = severityMeasurement(signal)
    expect(measurement.value).toBe(4)
    expect(measurement.threshold).toBeGreaterThan(0)
    expect(measurement.statement).toMatch(/4/)
  })

  it('states the threshold that was crossed', () => {
    const signal = makeSignal({ independent_source_count: 3 })
    expect(severityMeasurement(signal).statement).toMatch(/threshold/i)
  })

  it('shows the measurement on the card', () => {
    renderCard({ independent_source_count: 3 })
    expect(screen.getByText(/3 of 3 independent sources/i)).toBeInTheDocument()
  })

  it('renders the magnitude with a neutral label', () => {
    renderCard({ independent_source_count: 3 })
    expect(screen.getByLabelText(/magnitude/i)).toBeInTheDocument()
  })
})

describe('Evidence leads', () => {
  it('the narrative and its sources appear before any score', () => {
    renderCard({ independent_source_count: 3 })
    const body = document.body.textContent ?? ''
    const evidenceAt = body.indexOf('Fuel price protest across three districts')
    const magnitudeAt = body.search(/\bHIGH\b|\bMEDIUM\b|\bLOW\b/)
    expect(evidenceAt).toBeGreaterThanOrEqual(0)
    expect(magnitudeAt === -1 || evidenceAt < magnitudeAt).toBe(true)
  })

  it('the source list is present whenever sources exist', () => {
    renderCard()
    expect(screen.getByText(/The Hindu/)).toBeInTheDocument()
  })
})
