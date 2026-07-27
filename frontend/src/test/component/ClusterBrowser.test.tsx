import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ProvenanceProvider } from '../../contexts/ProvenanceContext'

vi.mock('../../api/topics', () => ({
  topicsApi: {
    listClusters: vi.fn().mockResolvedValue([
      {
        id: 'c1', label: 'Mule recruitment', item_count: 42, independent_source_count: 4,
        executive_summary: 'Recruiting mule accounts', relevance_tier: 'high',
        sources: [{ platform: 'telegram', source_name: 'https://t.me/group1' }],
      },
      {
        id: 'c2', label: 'Crypto scam', item_count: 18, independent_source_count: 2,
        executive_summary: null, relevance_tier: 'medium', sources: [],
      },
    ]),
    searchClusters: vi.fn().mockResolvedValue([]),
    getClusterContent: vi.fn().mockResolvedValue([
      {
        id: 'ci-1', title: 'Mule post 1', clean_text: 'Content text',
        platform: 'telegram', source_name: 'Group1', captured_at: '2026-07-26T10:00:00Z',
        relevance_tier: 'high', translated_text: null,
      },
    ]),
    get: vi.fn(),
    updateStatus: vi.fn(),
    listSources: vi.fn(),
    unlinkSource: vi.fn(),
  },
  // Re-export types as empty (vitest auto-mocks don't handle type exports)
}))

import { ClusterBrowser } from '../../components/clusters/ClusterBrowser'

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

describe('ClusterBrowser', () => {
  it('renders cluster list from API', async () => {
    render(<ClusterBrowser topicId="t1" onSelectContent={vi.fn()} />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText('Mule recruitment')).toBeInTheDocument()
      expect(screen.getByText('Crypto scam')).toBeInTheDocument()
    })
  })

  it('shows cluster count summary', async () => {
    render(<ClusterBrowser topicId="t1" onSelectContent={vi.fn()} />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText(/2 clusters/)).toBeInTheDocument()
      expect(screen.getByText(/60 total items/)).toBeInTheDocument()
    })
  })

  it('expands cluster to show drilldown content on click', async () => {
    render(<ClusterBrowser topicId="t1" onSelectContent={vi.fn()} />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText('Mule recruitment')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Mule recruitment'))
    await waitFor(() => {
      expect(screen.getByText('Mule post 1')).toBeInTheDocument()
    })
  })

  it('calls onSelectContent when drilldown item clicked', async () => {
    const onSelect = vi.fn()
    render(<ClusterBrowser topicId="t1" onSelectContent={onSelect} />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText('Mule recruitment')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Mule recruitment'))
    await waitFor(() => {
      expect(screen.getByText('Mule post 1')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Mule post 1'))
    expect(onSelect).toHaveBeenCalledWith('ci-1', 'Mule post 1')
  })

  it('shows empty state when no clusters', async () => {
    const { topicsApi } = await import('../../api/topics')
    vi.mocked(topicsApi.listClusters).mockResolvedValueOnce([])
    render(<ClusterBrowser topicId="t1" onSelectContent={vi.fn()} />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText(/No clusters yet/)).toBeInTheDocument()
    })
  })
})
