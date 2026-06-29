/**
 * Tests for EntityGraph story-driven views.
 *
 * Cytoscape needs canvas — not available in jsdom.
 * Test: view tabs render, source code has story architecture,
 * helper functions work correctly.
 */
import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../test-utils'
// Mock cytoscape (no canvas in jsdom)
vi.mock('cytoscape', () => ({
  default: vi.fn(() => ({
    on: vi.fn(),
    destroy: vi.fn(),
    fit: vi.fn(),
    elements: vi.fn(() => ({ addClass: vi.fn(), removeClass: vi.fn() })),
  })),
}))

vi.mock('../../api/intelligence', () => ({
  intelligenceApi: {
    entityGraph: vi.fn().mockResolvedValue({
      topic_id: 'topic-1',
      nodes: [
        { entity: 'John Doe', type: 'PERSON' },
        { entity: 'Acme Corp', type: 'ORG' },
      ],
      edges: [{ entity_a: 'John Doe', entity_b: 'Acme Corp', count: 3 }],
      node_count: 2,
      edge_count: 1,
    }),
  },
}))

vi.mock('../../api/identifiers', () => ({
  identifiersApi: {
    clusters: vi.fn().mockResolvedValue([
      { id: 'c1', identifier_type: 'PHONE_IN', identifier_value: '9876543210', source_count: 2 },
      { id: 'c2', identifier_type: 'TELEGRAM_HANDLE', identifier_value: '@scambot', source_count: 1 },
    ]),
    clusterDetail: vi.fn().mockImplementation((id: string) => {
      if (id === 'c1') return Promise.resolve({
        id: 'c1', identifier_type: 'PHONE_IN', identifier_value: '9876543210', source_count: 2,
        items: [{ content_item_id: 'ci-1', source_name: 'Siasat Daily', snippet: 'fraud' }],
      })
      return Promise.resolve({
        id: 'c2', identifier_type: 'TELEGRAM_HANDLE', identifier_value: '@scambot', source_count: 1,
        items: [{ content_item_id: 'ci-2', source_name: 'Telegram', snippet: 'scam' }],
      })
    }),
  },
}))

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true, login: vi.fn(), logout: vi.fn(),
    user: { sub: 'a', role: 'analyst', exp: Date.now() / 1000 + 3600, iat: Date.now() / 1000 },
    token: 'fake', secondsUntilExpiry: 3600,
  }),
}))

vi.mock('../../contexts/WSContext', () => ({
  useWS: () => ({ subscribe: () => () => {}, status: 'connected' }),
}))

describe('EntityGraph story views', () => {
  it('renders story view tabs', async () => {
    const EntityGraph = (await import('../../components/workspace/EntityGraph')).default
    renderWithProviders(<EntityGraph topicId="topic-1" onClose={vi.fn()} />)

    // Wait for data load
    const moneyTab = await screen.findByText('Money Trail', {}, { timeout: 3000 })
    expect(moneyTab).toBeTruthy()
    expect(screen.getByText('Social Network')).toBeTruthy()
    expect(screen.getByText('Digital Footprint')).toBeTruthy()
    expect(screen.getByText('Key Players')).toBeTruthy()
    expect(screen.getByText('Full Picture')).toBeTruthy()
  })

  it('shows subtitle for active view', async () => {
    const EntityGraph = (await import('../../components/workspace/EntityGraph')).default
    renderWithProviders(<EntityGraph topicId="topic-1" onClose={vi.fn()} />)

    await screen.findByText('Money Trail', {}, { timeout: 3000 })
    // Active tab should show its subtitle
    expect(screen.getByText(/funds move/i)).toBeTruthy()
  })

  it('has node/edge count in header', async () => {
    const EntityGraph = (await import('../../components/workspace/EntityGraph')).default
    renderWithProviders(<EntityGraph topicId="topic-1" onClose={vi.fn()} />)

    await screen.findByText('Money Trail', {}, { timeout: 3000 })
    // Should show "N nodes · M edges"
    expect(screen.getByText(/nodes.*edges/)).toBeTruthy()
  })
})

describe('EntityGraph source code architecture', () => {
  it('defines VIEWS array with 5 story views', async () => {
    const source = await import('../../components/workspace/EntityGraph?raw')
    const code = (source as any).default as string
    expect(code).toContain('Money Trail')
    expect(code).toContain('Social Network')
    expect(code).toContain('Digital Footprint')
    expect(code).toContain('Key Players')
    expect(code).toContain('Full Picture')
  })

  it('has truncateLabel helper function', async () => {
    const source = await import('../../components/workspace/EntityGraph?raw')
    const code = (source as any).default as string
    expect(code).toContain('truncateLabel')
  })

  it('uses edgeWidth data property for edge scaling', async () => {
    const source = await import('../../components/workspace/EntityGraph?raw')
    const code = (source as any).default as string
    expect(code).toContain('edgeWidth')
  })

  it('has PERSON and ORG specific node styles', async () => {
    const source = await import('../../components/workspace/EntityGraph?raw')
    const code = (source as any).default as string
    expect(code).toContain('PERSON')
    expect(code).toContain('ORG')
    // Should have distinct colors for person/org
    expect(code).toContain('round-rectangle')
  })

  it('filters nodes by active view idTypes', async () => {
    const source = await import('../../components/workspace/EntityGraph?raw')
    const code = (source as any).default as string
    // Should check view.idTypes to filter
    expect(code).toContain('idTypes')
    expect(code).toContain('showEntities')
    expect(code).toContain('showSources')
  })

  it('computes degree-based node sizing', async () => {
    const source = await import('../../components/workspace/EntityGraph?raw')
    const code = (source as any).default as string
    // Should scale node size by degree
    expect(code).toContain('degree')
  })

  it('uses increased nodeRepulsion for less cramming', async () => {
    const source = await import('../../components/workspace/EntityGraph?raw')
    const code = (source as any).default as string
    // Should use higher repulsion than 12000
    expect(code).toContain('18000')
  })
})
