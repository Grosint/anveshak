import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ProvenanceProvider } from '../../contexts/ProvenanceContext'
import { IdentifiersModal } from '../../components/modals/IdentifiersModal'
import { ClustersModal } from '../../components/modals/ClustersModal'
import { ReportGenerationModal } from '../../components/modals/ReportGenerationModal'
import { SourceManagementModal } from '../../components/modals/SourceManagementModal'

// Mock APIs
vi.mock('../../api/identifiers', () => ({
  identifiersApi: {
    top: vi.fn().mockResolvedValue([]),
    clusters: vi.fn().mockResolvedValue([]),
    search: vi.fn().mockResolvedValue([]),
    clusterDetail: vi.fn().mockResolvedValue(null),
  },
}))

vi.mock('../../api/topics', () => ({
  topicsApi: {
    listClusters: vi.fn().mockResolvedValue([]),
    searchClusters: vi.fn().mockResolvedValue([]),
    getClusterContent: vi.fn().mockResolvedValue([]),
    listSources: vi.fn().mockResolvedValue([]),
    unlinkSource: vi.fn(),
    get: vi.fn(),
    updateStatus: vi.fn(),
  },
}))

vi.mock('../../api/reports', () => ({
  reportsApi: {
    listForTopic: vi.fn().mockResolvedValue({ items: [] }),
    create: vi.fn(),
    get: vi.fn(),
    downloadPdf: vi.fn(),
  },
}))

vi.mock('../../components/discovery/SourceDiscoveryTab', () => ({
  SourceDiscoveryTab: () => <div>Discovery</div>,
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

describe('IdentifiersModal', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <IdentifiersModal open={false} onClose={vi.fn()} topicId="t1" />,
      { wrapper },
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders full-screen modal with title when open', () => {
    render(
      <IdentifiersModal open={true} onClose={vi.fn()} topicId="t1" />,
      { wrapper },
    )
    expect(screen.getByText('All Identifiers')).toBeInTheDocument()
  })

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn()
    render(
      <IdentifiersModal open={true} onClose={onClose} topicId="t1" />,
      { wrapper },
    )
    fireEvent.click(screen.getByLabelText('Close modal'))
    expect(onClose).toHaveBeenCalled()
  })

  it('calls onClose on Escape', () => {
    const onClose = vi.fn()
    render(
      <IdentifiersModal open={true} onClose={onClose} topicId="t1" />,
      { wrapper },
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
})

describe('ClustersModal', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <ClustersModal open={false} onClose={vi.fn()} topicId="t1" />,
      { wrapper },
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders full-screen modal with title when open', () => {
    render(
      <ClustersModal open={true} onClose={vi.fn()} topicId="t1" />,
      { wrapper },
    )
    expect(screen.getByText('All Clusters')).toBeInTheDocument()
  })
})

describe('ReportGenerationModal', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <ReportGenerationModal open={false} onClose={vi.fn()} topicId="t1" />,
      { wrapper },
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders full-screen modal with title when open', () => {
    render(
      <ReportGenerationModal open={true} onClose={vi.fn()} topicId="t1" />,
      { wrapper },
    )
    expect(screen.getByText('Generate Report')).toBeInTheDocument()
  })
})

describe('SourceManagementModal', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <SourceManagementModal open={false} onClose={vi.fn()} topicId="t1" />,
      { wrapper },
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders full-screen modal with title when open', async () => {
    render(
      <SourceManagementModal open={true} onClose={vi.fn()} topicId="t1" />,
      { wrapper },
    )
    expect(screen.getByText('Manage Sources')).toBeInTheDocument()
  })
})
