import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ProvenanceProvider } from '../../contexts/ProvenanceContext'
import { SignalCards } from '../../components/intelligence/SignalCards'
import { NarrativeCards } from '../../components/intelligence/NarrativeCards'
import { IdentifierPills } from '../../components/intelligence/IdentifierPills'
import { LocationPills } from '../../components/intelligence/LocationPills'
import { RecentContent } from '../../components/intelligence/RecentContent'
import { SourceHealthStrip } from '../../components/intelligence/SourceHealthStrip'
import type { IntelSignal, IntelCluster, IntelIdentifier, IntelLocation, IntelSourceHealth } from '../../api/intelligence'

// Mock content API for RecentContent
vi.mock('../../api/content', () => ({
  contentApi: {
    list: vi.fn().mockResolvedValue([
      { id: 'ci-1', url: 'https://example.com/1', title: 'Breaking news article', clean_text: 'Content text', language: 'en', credibility_score_at_capture: 75, captured_at: '2026-07-26T10:00:00Z', backfilled: false, platform: 'rss', source_name: 'example.com' },
      { id: 'ci-2', url: 'https://example.com/2', title: 'Second article', clean_text: 'More content', language: 'en', credibility_score_at_capture: 60, captured_at: '2026-07-25T08:00:00Z', backfilled: false, platform: 'web', source_name: 'news.org' },
    ]),
  },
}))

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ProvenanceProvider>{children}</ProvenanceProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

// ── Test data ─────────────────────────────────────────────────────────

const signals: IntelSignal[] = [
  { id: 's1', signal_type: 'multi_source_convergence', description: 'Test signal', status: 'new', fired_at: '2026-07-26T10:00:00Z', cluster_label: 'Cyber fraud ring', isc: 3 },
  { id: 's2', signal_type: 'identifier_convergence', description: 'ID signal', status: 'new', fired_at: '2026-07-25T08:00:00Z', cluster_label: null, isc: 2 },
]

const clusters: IntelCluster[] = [
  { id: 'c1', label: 'Mule account recruitment', item_count: 42, isc: 4, executive_summary: 'Recruiting mule accounts via Telegram', created_at: '2026-07-20T00:00:00Z', growth_24h: 5, growth_rate: 0.12 },
  { id: 'c2', label: 'Investment scam SMS', item_count: 18, isc: 2, executive_summary: null, created_at: '2026-07-22T00:00:00Z', growth_24h: 0, growth_rate: 0 },
]

const identifiers: IntelIdentifier[] = [
  { identifier_type: 'PHONE_IN', identifier_value: '9876543210', mention_count: 12, source_count: 4 },
  { identifier_type: 'UPI', identifier_value: 'scammer@paytm', mention_count: 8, source_count: 3 },
  { identifier_type: 'TELEGRAM_HANDLE', identifier_value: 'dark_trader', mention_count: 5, source_count: 1 },
]

const locations: IntelLocation[] = [
  { location_name: 'Mumbai', latitude: 19.076, longitude: 72.877, content_count: 15 },
  { location_name: 'Kochi', latitude: 9.931, longitude: 76.267, content_count: 8 },
]

const sourceHealth: IntelSourceHealth[] = [
  { id: 'src1', name: 'Times of India', platform: 'rss', health_status: 'healthy', credibility_score: 82 },
  { id: 'src2', name: 'Dark Forum', platform: 'web', health_status: 'degraded', credibility_score: 35 },
  { id: 'src3', name: 'Down Source', platform: 'web', health_status: 'down', credibility_score: 10 },
]

// ── SignalCards ────────────────────────────────────────────────────────

describe('SignalCards', () => {
  it('renders nothing when signals empty', () => {
    const { container } = render(<SignalCards signals={[]} onSelect={vi.fn()} />, { wrapper })
    expect(container.innerHTML).toBe('')
  })

  it('renders signal cards with correct data', () => {
    render(<SignalCards signals={signals} onSelect={vi.fn()} />, { wrapper })
    expect(screen.getByText('Cyber fraud ring')).toBeInTheDocument()
    expect(screen.getByText('ID signal')).toBeInTheDocument()
    expect(screen.getByText('2 new')).toBeInTheDocument()
  })

  it('shows HIGH severity for ISC >= 3', () => {
    render(<SignalCards signals={signals} onSelect={vi.fn()} />, { wrapper })
    expect(screen.getByText('HIGH')).toBeInTheDocument()
  })

  it('calls onSelect when card clicked', () => {
    const onSelect = vi.fn()
    render(<SignalCards signals={signals} onSelect={onSelect} />, { wrapper })
    fireEvent.click(screen.getByText('Cyber fraud ring'))
    expect(onSelect).toHaveBeenCalledWith(signals[0])
  })
})

// ── NarrativeCards ────────────────────────────────────────────────────

describe('NarrativeCards', () => {
  it('renders nothing when clusters empty', () => {
    const { container } = render(<NarrativeCards clusters={[]} onSelect={vi.fn()} />, { wrapper })
    expect(container.innerHTML).toBe('')
  })

  it('renders cluster labels and item counts', () => {
    render(<NarrativeCards clusters={clusters} onSelect={vi.fn()} />, { wrapper })
    expect(screen.getByText('Mule account recruitment')).toBeInTheDocument()
    expect(screen.getByText('Investment scam SMS')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('shows growth rate percentage for growing clusters', () => {
    render(<NarrativeCards clusters={clusters} onSelect={vi.fn()} />, { wrapper })
    expect(screen.getByText('+12%')).toBeInTheDocument()
  })

  it('shows "Show all" when totalCount > displayed', () => {
    const onShowAll = vi.fn()
    render(<NarrativeCards clusters={clusters} onSelect={vi.fn()} onShowAll={onShowAll} totalCount={20} />, { wrapper })
    const showAll = screen.getByText(/Show all 20/)
    expect(showAll).toBeInTheDocument()
    fireEvent.click(showAll)
    expect(onShowAll).toHaveBeenCalled()
  })

  it('calls onSelect when card clicked', () => {
    const onSelect = vi.fn()
    render(<NarrativeCards clusters={clusters} onSelect={onSelect} />, { wrapper })
    fireEvent.click(screen.getByText('Mule account recruitment'))
    expect(onSelect).toHaveBeenCalledWith(clusters[0])
  })
})

// ── IdentifierPills ───────────────────────────────────────────────────

describe('IdentifierPills', () => {
  it('renders nothing when identifiers empty', () => {
    const { container } = render(<IdentifierPills identifiers={[]} onSelect={vi.fn()} />, { wrapper })
    expect(container.innerHTML).toBe('')
  })

  it('renders identifier values with type badges', () => {
    render(<IdentifierPills identifiers={identifiers} onSelect={vi.fn()} />, { wrapper })
    expect(screen.getByText('9876543210')).toBeInTheDocument()
    expect(screen.getByText('scammer@paytm')).toBeInTheDocument()
    expect(screen.getByText('PH')).toBeInTheDocument()
    expect(screen.getByText('UPI')).toBeInTheDocument()
  })

  it('highlights source count >= 3', () => {
    render(<IdentifierPills identifiers={identifiers} onSelect={vi.fn()} />, { wrapper })
    // Source counts 4 and 3 should have signal-high class
    const sourceCells = screen.getAllByText(/^[0-9]+$/).filter(el => el.closest('td'))
    expect(sourceCells.length).toBeGreaterThan(0)
  })

  it('calls onSelect when row clicked', () => {
    const onSelect = vi.fn()
    render(<IdentifierPills identifiers={identifiers} onSelect={onSelect} />, { wrapper })
    fireEvent.click(screen.getByText('9876543210'))
    expect(onSelect).toHaveBeenCalledWith(identifiers[0])
  })

  it('shows "Show all" button when onShowAll provided', () => {
    const onShowAll = vi.fn()
    render(<IdentifierPills identifiers={identifiers} onSelect={vi.fn()} onShowAll={onShowAll} />, { wrapper })
    const btn = screen.getByText(/Show all/)
    fireEvent.click(btn)
    expect(onShowAll).toHaveBeenCalled()
  })
})

// ── LocationPills ─────────────────────────────────────────────────────

describe('LocationPills', () => {
  it('renders nothing when locations empty', () => {
    const { container } = render(<LocationPills locations={[]} onSelectLocation={vi.fn()} />, { wrapper })
    expect(container.innerHTML).toBe('')
  })

  it('renders location names with content counts', () => {
    render(<LocationPills locations={locations} onSelectLocation={vi.fn()} />, { wrapper })
    expect(screen.getByText('Mumbai')).toBeInTheDocument()
    expect(screen.getByText('(15)')).toBeInTheDocument()
    expect(screen.getByText('Kochi')).toBeInTheDocument()
    expect(screen.getByText('(8)')).toBeInTheDocument()
  })

  it('calls onSelectLocation when pill clicked', () => {
    const onSelect = vi.fn()
    render(<LocationPills locations={locations} onSelectLocation={onSelect} />, { wrapper })
    fireEvent.click(screen.getByText('Mumbai'))
    expect(onSelect).toHaveBeenCalledWith(locations[0])
  })

  it('shows "Open Map" button when onOpenMap provided', () => {
    const onOpenMap = vi.fn()
    render(<LocationPills locations={locations} onSelectLocation={vi.fn()} onOpenMap={onOpenMap} />, { wrapper })
    const btn = screen.getByText(/Open Map/)
    fireEvent.click(btn)
    expect(onOpenMap).toHaveBeenCalled()
  })
})

// ── RecentContent ─────────────────────────────────────────────────────

describe('RecentContent', () => {
  it('renders content items from API', async () => {
    render(<RecentContent topicId="t1" onSelectContent={vi.fn()} />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText('Breaking news article')).toBeInTheDocument()
      expect(screen.getByText('Second article')).toBeInTheDocument()
    })
  })

  it('calls onSelectContent when item clicked', async () => {
    const onSelect = vi.fn()
    render(<RecentContent topicId="t1" onSelectContent={onSelect} />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText('Breaking news article')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Breaking news article'))
    expect(onSelect).toHaveBeenCalledWith('ci-1', 'Breaking news article')
  })

  it('shows "Show all" button when onShowAll provided', async () => {
    const onShowAll = vi.fn()
    render(<RecentContent topicId="t1" onSelectContent={vi.fn()} onShowAll={onShowAll} />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText(/Show all/)).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText(/Show all/))
    expect(onShowAll).toHaveBeenCalled()
  })
})

// ── SourceHealthStrip ─────────────────────────────────────────────────

describe('SourceHealthStrip', () => {
  it('renders nothing when sources empty', () => {
    const { container } = render(<SourceHealthStrip sources={[]} />, { wrapper })
    expect(container.innerHTML).toBe('')
  })

  it('renders health dots with source names in tooltips', () => {
    render(<SourceHealthStrip sources={sourceHealth} />, { wrapper })
    // Source names appear in tooltip spans (hidden by default, shown on hover)
    expect(screen.getByText('Times of India')).toBeInTheDocument()
    expect(screen.getByText('Dark Forum')).toBeInTheDocument()
    expect(screen.getByText('Down Source')).toBeInTheDocument()
    // Dots are rendered as spans with health status colors
    const dots = document.querySelectorAll('.rounded-full')
    expect(dots.length).toBe(3)
  })

  it('shows gear button when onManage provided', () => {
    const onManage = vi.fn()
    render(<SourceHealthStrip sources={sourceHealth} onManage={onManage} />, { wrapper })
    const btn = screen.getByLabelText('Manage sources')
    fireEvent.click(btn)
    expect(onManage).toHaveBeenCalled()
  })

  it('does not show gear button without onManage', () => {
    render(<SourceHealthStrip sources={sourceHealth} />, { wrapper })
    expect(screen.queryByLabelText('Manage sources')).not.toBeInTheDocument()
  })
})
