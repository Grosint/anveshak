/**
 * Tests for LocationMap component — location list panel, unresolved indicator,
 * enriched GeoJSON properties.
 *
 * MapLibre GL requires WebGL — not available in jsdom.
 * We test the wrapper (LocationMap) and verify GeoMap source code for
 * dark tiles and clustering config.
 */
import { describe, it, expect, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import { renderWithProviders } from '../test-utils'

// Mock GeoMap since MapLibre needs WebGL
vi.mock('../../components/map/GeoMap', () => ({
  default: ({ geojson, onFeatureClick }: any) => (
    <div data-testid="geo-map" data-features={geojson?.features?.length ?? 0}>
      mock-map
    </div>
  ),
}))

vi.mock('../../api/intelligence', () => ({
  intelligenceApi: {
    locationMap: vi.fn().mockResolvedValue({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [72.87, 19.07] },
          properties: {
            name: 'Mumbai',
            entity_type: 'GPE',
            mention_count: 23,
            source_count: 5,
            latest_mention: '2026-06-29T08:00:00Z',
          },
        },
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [77.20, 28.61] },
          properties: {
            name: 'Delhi',
            entity_type: 'GPE',
            mention_count: 18,
            source_count: 3,
            latest_mention: '2026-06-28T12:00:00Z',
          },
        },
      ],
      metadata: {
        total_extracted: 5,
        geocoded: 2,
        unresolved: ['Kotwali PS', 'Doranda', 'Cyber Thana'],
      },
    }),
  },
}))

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    user: { sub: 'analyst-1', role: 'analyst', exp: Date.now() / 1000 + 3600, iat: Date.now() / 1000 },
    token: 'fake-token',
    secondsUntilExpiry: 3600,
  }),
}))

vi.mock('../../contexts/WSContext', () => ({
  useWS: () => ({ subscribe: () => () => {}, status: 'connected' }),
}))

describe('LocationMap wrapper', () => {
  it('renders location list panel with location names', async () => {
    const LocationMap = (await import('../../components/workspace/LocationMap')).default
    renderWithProviders(<LocationMap topicId="topic-1" />)

    // Wait for data to load and list to render
    const mumbai = await screen.findByText('Mumbai', {}, { timeout: 3000 })
    expect(mumbai).toBeTruthy()

    expect(screen.getByText('Delhi')).toBeTruthy()
  })

  it('shows mention count for each location in the list', async () => {
    const LocationMap = (await import('../../components/workspace/LocationMap')).default
    renderWithProviders(<LocationMap topicId="topic-1" />)

    await screen.findByText('Mumbai', {}, { timeout: 3000 })
    // Mention counts should be visible
    expect(screen.getByText('23')).toBeTruthy()
    expect(screen.getByText('18')).toBeTruthy()
  })

  it('shows unresolved locations section', async () => {
    const LocationMap = (await import('../../components/workspace/LocationMap')).default
    renderWithProviders(<LocationMap topicId="topic-1" />)

    await screen.findByText('Mumbai', {}, { timeout: 3000 })
    // Unresolved section should show names that couldn't be geocoded
    const unresolvedHeaders = screen.getAllByText(/unresolved/i)
    expect(unresolvedHeaders.length).toBeGreaterThan(0)
    expect(screen.getByText('Kotwali PS')).toBeTruthy()
  })

  it('shows geocoded vs total count', async () => {
    const LocationMap = (await import('../../components/workspace/LocationMap')).default
    renderWithProviders(<LocationMap topicId="topic-1" />)

    await screen.findByText('Mumbai', {}, { timeout: 3000 })
    // Should show "2 of 5" or "2/5" geocoded indicator
    expect(screen.getByText(/2.*5|2 of 5/)).toBeTruthy()
  })
})

describe('GeoMap dark tiles and clustering', () => {
  it('uses dark tile style URL, not demo tiles', async () => {
    const source = await import('../../components/map/GeoMap?raw')
    const code = (source as any).default as string
    expect(code).not.toContain('demotiles.maplibre.org')
    expect(code).toContain('dark-matter')
  })

  it('enables clustering on GeoJSON source', async () => {
    const source = await import('../../components/map/GeoMap?raw')
    const code = (source as any).default as string
    expect(code).toContain('cluster: true')
  })

  it('has hover tooltip handler (mouseenter)', async () => {
    const source = await import('../../components/map/GeoMap?raw')
    const code = (source as any).default as string
    expect(code).toContain('mouseenter')
  })

  it('renders a legend element', async () => {
    const source = await import('../../components/map/GeoMap?raw')
    const code = (source as any).default as string
    expect(code).toContain('legend')
  })
})
