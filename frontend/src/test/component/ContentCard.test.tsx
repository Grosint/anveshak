/**
 * ContentCard timestamp — issue #49.
 *
 * The feed filters on publication time, so a card that still reads "6 months
 * ago" from capture time tells the analyst the filter did nothing. The card
 * leads with the timestamp the filter acted on and says which one it is.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ContentCard } from '../../components/content/ContentCard'
import { makeContentItem } from '../factories'

vi.mock('../../api/vision', () => ({
  visionApi: { analyseVideo: vi.fn() },
}))

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-09-11T12:00:00Z'))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('ContentCard timestamp', () => {
  it('leads with publication time when the platform gave one', () => {
    const item = makeContentItem({
      captured_at: '2026-09-10T09:00:00Z',
      published_at: '2026-03-04T09:00:00Z',
    })

    render(<ContentCard item={item} onClick={vi.fn()} />)

    expect(screen.getByText(/Published 6 months ago/)).toBeInTheDocument()
  })

  it('says Collected when publication time is unknown', () => {
    const item = makeContentItem({ captured_at: '2026-09-10T09:00:00Z', published_at: null })

    render(<ContentCard item={item} onClick={vi.fn()} />)

    expect(screen.getByText(/Collected 1 day ago/)).toBeInTheDocument()
  })

  it('keeps capture time reachable on the publication-time card', () => {
    const item = makeContentItem({
      captured_at: '2026-09-10T09:00:00Z',
      published_at: '2026-03-04T09:00:00Z',
    })

    render(<ContentCard item={item} onClick={vi.fn()} />)

    expect(screen.getByText(/Published/)).toHaveAttribute('title', expect.stringContaining('Collected'))
  })
})
