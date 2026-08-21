import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SignalBadge, NewContentBadge, SourceHealthDot } from '../../components/ui/UrgencyBadge'

describe('SignalBadge', () => {
  it('renders nothing when count is zero', () => {
    const { container } = render(<SignalBadge count={0} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders count when positive', () => {
    render(<SignalBadge count={5} />)
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByLabelText('5 unacknowledged signals')).toBeInTheDocument()
  })

  it('uses singular label for count of 1', () => {
    render(<SignalBadge count={1} />)
    expect(screen.getByLabelText('1 unacknowledged signal')).toBeInTheDocument()
  })
})

describe('NewContentBadge', () => {
  it('renders nothing when count is zero', () => {
    const { container } = render(<NewContentBadge count={0} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders +N new when positive', () => {
    render(<NewContentBadge count={12} />)
    expect(screen.getByText('+12 new')).toBeInTheDocument()
    expect(screen.getByLabelText('12 new items in last 24h')).toBeInTheDocument()
  })

  it('uses singular label for count of 1', () => {
    render(<NewContentBadge count={1} />)
    expect(screen.getByLabelText('1 new item in last 24h')).toBeInTheDocument()
  })
})

describe('SourceHealthDot', () => {
  it('renders green dot for healthy', () => {
    render(<SourceHealthDot status="healthy" />)
    const dot = screen.getByLabelText('Sources healthy')
    expect(dot).toBeInTheDocument()
    expect(dot.className).toContain('bg-cred-high')
  })

  it('renders amber dot for degraded', () => {
    render(<SourceHealthDot status="degraded" />)
    const dot = screen.getByLabelText('Sources degraded')
    expect(dot).toBeInTheDocument()
    expect(dot.className).toContain('bg-signal-med')
  })

  it('renders red dot for down', () => {
    render(<SourceHealthDot status="down" />)
    const dot = screen.getByLabelText('Sources down')
    expect(dot).toBeInTheDocument()
    expect(dot.className).toContain('bg-signal-high')
  })
})
