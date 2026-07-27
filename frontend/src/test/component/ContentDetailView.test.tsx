import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ProvenanceProvider } from '../../contexts/ProvenanceContext'
import type { ContentProvenance } from '../../api/provenance'

// Mock provenanceApi
const mockContentProvenance = vi.fn<() => Promise<ContentProvenance>>()
vi.mock('../../api/provenance', () => ({
  provenanceApi: {
    contentProvenance: (...args: unknown[]) => mockContentProvenance(...(args as [])),
  },
}))

// Lazy import after mocks
const { default: ContentDetailView } = await import(
  '../../components/provenance/ContentDetailView'
)

function makeProvenance(overrides: Partial<ContentProvenance> = {}): ContentProvenance {
  return {
    id: 'ci-1',
    topic_id: 'topic-1',
    source_id: 's-1',
    narrative_cluster_id: null,
    clean_text: 'Test content',
    translated_text: null,
    language: 'en',
    captured_at: '2026-01-01T00:00:00Z',
    credibility_score_at_capture: 75,
    url: 'https://example.com',
    source: { id: 's-1', name: 'Test Source', platform: 'web', credibility_score: 75 },
    cluster: null,
    identifiers: [],
    vision_results: [],
    ...overrides,
  }
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
}

function renderComponent(contentId = 'ci-1') {
  const qc = createQueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ProvenanceProvider>
          <ContentDetailView contentId={contentId} />
        </ProvenanceProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ContentDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders EXIF metadata when present in vision results', async () => {
    mockContentProvenance.mockResolvedValue(
      makeProvenance({
        vision_results: [
          {
            deepfake_score: 0.15,
            deepfake_model: 'dire',
            yolo_detections: null,
            clip_labels: null,
            synthetic_probability: null,
            processed_at: '2026-01-01T00:00:00Z',
            storage_path: '/media/test.jpg',
            asset_type: 'image',
            exif_data: { Make: 'Canon', Model: 'EOS R5', Software: 'Lightroom' },
            phash: null,
          },
        ],
      }),
    )

    renderComponent()

    // Wait for EXIF table to appear
    expect(await screen.findByText('EXIF Metadata')).toBeInTheDocument()
    expect(await screen.findByText('Make')).toBeInTheDocument()
    expect(await screen.findByText('Canon')).toBeInTheDocument()
    expect(await screen.findByText('Model')).toBeInTheDocument()
    expect(await screen.findByText('EOS R5')).toBeInTheDocument()
  })

  it('hides EXIF section when exif_data is null', async () => {
    mockContentProvenance.mockResolvedValue(
      makeProvenance({
        vision_results: [
          {
            deepfake_score: 0.3,
            deepfake_model: 'dire',
            yolo_detections: null,
            clip_labels: null,
            synthetic_probability: null,
            processed_at: '2026-01-01T00:00:00Z',
            storage_path: '/media/test.jpg',
            asset_type: 'image',
            exif_data: null,
            phash: null,
          },
        ],
      }),
    )

    renderComponent()

    // Wait for vision section to render (deepfake meter appears)
    expect(await screen.findByText('Media Analysis (1)')).toBeInTheDocument()
    // EXIF section should not be present
    expect(screen.queryByText('EXIF Metadata')).not.toBeInTheDocument()
  })

  it('hides EXIF section when exif_data is empty object', async () => {
    mockContentProvenance.mockResolvedValue(
      makeProvenance({
        vision_results: [
          {
            deepfake_score: 0.1,
            deepfake_model: 'dire',
            yolo_detections: null,
            clip_labels: null,
            synthetic_probability: null,
            processed_at: '2026-01-01T00:00:00Z',
            storage_path: '/media/test.jpg',
            asset_type: 'image',
            exif_data: {},
            phash: null,
          },
        ],
      }),
    )

    renderComponent()

    expect(await screen.findByText('Media Analysis (1)')).toBeInTheDocument()
    expect(screen.queryByText('EXIF Metadata')).not.toBeInTheDocument()
  })

  it('hides vision section entirely when no vision results', async () => {
    mockContentProvenance.mockResolvedValue(makeProvenance({ vision_results: [] }))

    renderComponent()

    expect(await screen.findByText('Content')).toBeInTheDocument()
    expect(screen.queryByText('Media Analysis')).not.toBeInTheDocument()
  })
})
