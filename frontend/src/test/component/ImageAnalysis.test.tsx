import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

// Mock APIs
const mockAnalyse = vi.fn()
const mockListTopics = vi.fn()

vi.mock('../../api/vision', () => ({
  visionApi: {
    analyse: (...args: unknown[]) => mockAnalyse(...args),
    pollJob: vi.fn(),
    listRecentJobs: vi.fn().mockResolvedValue([]),
    reverseSearch: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('../../api/topics', () => ({
  topicsApi: {
    list: () => mockListTopics(),
  },
  // Re-export Topic type (unused at runtime but needed for import)
}))

const { default: ImageAnalysis } = await import('../../pages/ImageAnalysis')

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
}

function renderPage() {
  const qc = createQueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ImageAnalysis />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ImageAnalysis — topic selector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAnalyse.mockResolvedValue({ job_id: 'j-1', media_asset_id: 'ma-1', asset_type: 'image', status: 'queued' })
  })

  it('renders topic selector when topics exist', async () => {
    mockListTopics.mockResolvedValue([
      { id: 't-1', name: 'Cyber Fraud', status: 'active', signal_threshold: 3, credibility_min: 50, created_at: '2026-01-01' },
      { id: 't-2', name: 'Drug Trade', status: 'active', signal_threshold: 3, credibility_min: 50, created_at: '2026-01-01' },
    ])

    renderPage()

    expect(await screen.findByLabelText('Link to topic (optional)')).toBeInTheDocument()
    expect(screen.getByText('Standalone analysis')).toBeInTheDocument()
    expect(screen.getByText('Cyber Fraud')).toBeInTheDocument()
    expect(screen.getByText('Drug Trade')).toBeInTheDocument()
  })

  it('hides topic selector when no topics', async () => {
    mockListTopics.mockResolvedValue([])

    renderPage()

    // Wait for page to render
    expect(await screen.findByText('Image Analysis')).toBeInTheDocument()
    expect(screen.queryByLabelText('Link to topic (optional)')).not.toBeInTheDocument()
  })

  it('filters out archived topics', async () => {
    mockListTopics.mockResolvedValue([
      { id: 't-1', name: 'Active Topic', status: 'active', signal_threshold: 3, credibility_min: 50, created_at: '2026-01-01' },
      { id: 't-2', name: 'Archived Topic', status: 'archived', signal_threshold: 3, credibility_min: 50, created_at: '2026-01-01' },
    ])

    renderPage()

    expect(await screen.findByText('Active Topic')).toBeInTheDocument()
    // Archived topic should not appear as option
    expect(screen.queryByText('Archived Topic')).not.toBeInTheDocument()
  })

  it('passes topic_id to analyse when selected', async () => {
    mockListTopics.mockResolvedValue([
      { id: 't-1', name: 'Cyber Fraud', status: 'active', signal_threshold: 3, credibility_min: 50, created_at: '2026-01-01' },
    ])

    renderPage()

    const select = await screen.findByLabelText('Link to topic (optional)')
    fireEvent.change(select, { target: { value: 't-1' } })

    // Simulate file upload via drop zone
    const file = new File(['fake-image'], 'test.jpg', { type: 'image/jpeg' })
    const dropZone = screen.getByText(/upload an image/i).closest('div')!
    const input = dropZone.querySelector('input[type="file"]')
    if (input) {
      fireEvent.change(input, { target: { files: [file] } })

      // Wait for analyse to be called
      await vi.waitFor(() => expect(mockAnalyse).toHaveBeenCalled())
      expect(mockAnalyse).toHaveBeenCalledWith(file, undefined, 't-1')
    }
  })

  it('passes undefined topic_id when standalone selected', async () => {
    mockListTopics.mockResolvedValue([
      { id: 't-1', name: 'Cyber Fraud', status: 'active', signal_threshold: 3, credibility_min: 50, created_at: '2026-01-01' },
    ])

    renderPage()

    // Leave default "Standalone analysis" selected
    const file = new File(['fake-image'], 'test.jpg', { type: 'image/jpeg' })
    const dropZone = screen.getByText(/upload an image/i).closest('div')!
    const input = dropZone.querySelector('input[type="file"]')
    if (input) {
      fireEvent.change(input, { target: { files: [file] } })

      await vi.waitFor(() => expect(mockAnalyse).toHaveBeenCalled())
      expect(mockAnalyse).toHaveBeenCalledWith(file, undefined, undefined)
    }
  })
})
