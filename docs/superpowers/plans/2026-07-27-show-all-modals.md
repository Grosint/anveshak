# ShowAllModal + Report/Source Management Modals — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full-screen modal overlays triggered by IntelligenceView action buttons, reusing existing page components.

**Architecture:** Extend the existing `Modal` component with a `fullScreen` prop. Create 4 thin modal wrappers that compose existing components (`Identifiers`, `ReportsTab`, `SourcesTab`) inside the full-screen shell. Extract cluster browsing from `TopicWorkspace` into a reusable `ClusterBrowser`. Wire modal state in `TopicWorkspace` to replace tab-switching callbacks.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Vitest + React Testing Library, @tanstack/react-query

## Global Constraints

- Vitest tests in `frontend/src/test/`, config in `vite.config.ts` `test:` block
- Test wrapper must include `QueryClientProvider`, `MemoryRouter`, `ProvenanceProvider`
- Follow existing test patterns in `frontend/src/test/component/IntelligenceView.test.tsx`
- `embedded` prop pattern per `frontend.md` rules — skip page header when true
- Run tests: `cd frontend && npx vitest run <path>` for single file, `npx vitest run` for all
- Typecheck: `cd frontend && npx tsc --noEmit`
- All CSS uses Tailwind utility classes with project CSS variables (`anveshak-card`, `anveshak-border`, `text-primary`, etc.)

---

### Task 1: Extend Modal with fullScreen prop

**Files:**
- Modify: `frontend/src/components/ui/Modal.tsx`
- Test: `frontend/src/test/component/Modal.test.tsx`

**Interfaces:**
- Consumes: nothing new
- Produces: `Modal` component accepts new optional `fullScreen?: boolean` prop. When `true`, renders as `fixed inset-0` full-screen panel with sticky header and scrollable body. Escape key closes. Existing behavior unchanged when `false`/omitted.

- [ ] **Step 1: Write failing tests for fullScreen behavior**

Create `frontend/src/test/component/Modal.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Modal } from '../../components/ui/Modal'

describe('Modal', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(
      <Modal open={false} onClose={vi.fn()} title="Test">Content</Modal>
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders children when open is true', () => {
    render(
      <Modal open={true} onClose={vi.fn()} title="Test">
        <p>Hello modal</p>
      </Modal>
    )
    expect(screen.getByText('Hello modal')).toBeInTheDocument()
  })

  it('renders title in header', () => {
    render(
      <Modal open={true} onClose={vi.fn()} title="My Title">Content</Modal>
    )
    expect(screen.getByText('My Title')).toBeInTheDocument()
  })

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn()
    render(
      <Modal open={true} onClose={onClose} title="Test">Content</Modal>
    )
    fireEvent.click(screen.getByLabelText('Close modal'))
    expect(onClose).toHaveBeenCalled()
  })

  it('calls onClose when backdrop clicked (non-fullscreen)', () => {
    const onClose = vi.fn()
    render(
      <Modal open={true} onClose={onClose} title="Test">Content</Modal>
    )
    // Backdrop is the aria-hidden div
    const backdrop = document.querySelector('[aria-hidden="true"]')!
    fireEvent.click(backdrop)
    expect(onClose).toHaveBeenCalled()
  })

  it('calls onClose on Escape key', () => {
    const onClose = vi.fn()
    render(
      <Modal open={true} onClose={onClose} title="Test">Content</Modal>
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })

  it('applies fullScreen layout when fullScreen=true', () => {
    render(
      <Modal open={true} onClose={vi.fn()} title="Full" fullScreen>
        <p>Full content</p>
      </Modal>
    )
    const panel = screen.getByText('Full content').closest('[data-testid="modal-panel"]')
    expect(panel).toBeInTheDocument()
    // Full-screen panel should have inset-0
    expect(panel!.className).toContain('inset-0')
  })

  it('does not apply fullScreen layout by default', () => {
    render(
      <Modal open={true} onClose={vi.fn()} title="Normal">
        <p>Normal content</p>
      </Modal>
    )
    const panel = screen.getByText('Normal content').closest('[data-testid="modal-panel"]')
    expect(panel).toBeInTheDocument()
    expect(panel!.className).not.toContain('inset-0')
  })

  it('renders footer when provided', () => {
    render(
      <Modal open={true} onClose={vi.fn()} title="Test" footer={<button>Save</button>}>
        Content
      </Modal>
    )
    expect(screen.getByText('Save')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/test/component/Modal.test.tsx`
Expected: Multiple failures — `fullScreen` prop not recognized, `data-testid` not present, Escape handler not wired.

- [ ] **Step 3: Implement fullScreen prop on Modal**

Modify `frontend/src/components/ui/Modal.tsx` to this complete implementation:

```tsx
import { ReactNode, useEffect, useCallback } from 'react'
import { Button } from './Button'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  maxWidth?: string
  fullScreen?: boolean
}

export function Modal({ open, onClose, title, children, footer, maxWidth = 'max-w-lg', fullScreen = false }: ModalProps) {
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose()
  }, [onClose])

  useEffect(() => {
    if (!open) return
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, handleKeyDown])

  if (!open) return null

  if (fullScreen) {
    return (
      <div
        className="fixed inset-0 z-[60] flex flex-col bg-[#0b1222]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        data-testid="modal-panel"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-anveshak-border shrink-0">
          <h2 id="modal-title" className="text-base font-semibold text-text-primary">
            {title}
          </h2>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close modal">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </Button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-anveshak-border shrink-0">
            {footer}
          </div>
        )}
      </div>
    )
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className={`relative z-10 w-full ${maxWidth} bg-anveshak-card border border-anveshak-border rounded-lg shadow-card-hover animate-fade-in`}
        data-testid="modal-panel"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-anveshak-border">
          <h2 id="modal-title" className="text-base font-semibold text-text-primary">
            {title}
          </h2>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close modal">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </Button>
        </div>

        {/* Body */}
        <div className="px-5 py-4">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-anveshak-border">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
```

Key changes from original:
- Added `fullScreen?: boolean` prop to interface and destructuring (default `false`)
- Added Escape key handler via `useEffect` + `useCallback`
- Removed unused `dialogRef` (was never wired to a `<dialog>` element)
- Full-screen branch: `fixed inset-0 z-[60]`, flex column layout, scrollable body, `bg-[#0b1222]` (matches EntityGraph pattern)
- Added `data-testid="modal-panel"` to both branches for test targeting

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/test/component/Modal.test.tsx`
Expected: All 8 tests PASS

- [ ] **Step 5: Run existing tests to verify no regression**

Run: `cd frontend && npx vitest run src/test/component/IntelligenceView.test.tsx`
Expected: All existing tests PASS (Modal is not imported by these tests, but verifies test infra works)

- [ ] **Step 6: Commit**

```bash
cd frontend
git add src/components/ui/Modal.tsx src/test/component/Modal.test.tsx
git commit -m "feat(frontend): extend Modal with fullScreen prop and Escape handler"
```

---

### Task 2: Extract ClusterBrowser from TopicWorkspace

**Files:**
- Create: `frontend/src/components/clusters/ClusterBrowser.tsx`
- Test: `frontend/src/test/component/ClusterBrowser.test.tsx`
- Modify: `frontend/src/pages/TopicWorkspace.tsx` (replace inline cluster rendering with `<ClusterBrowser>`)

**Interfaces:**
- Consumes: `topicsApi.listClusters(topicId)`, `topicsApi.searchClusters(topicId, query)`, `topicsApi.getClusterContent(topicId, clusterId, opts)` from `frontend/src/api/topics.ts`. Types `Cluster`, `ClusterContentItem` from same module.
- Produces: `<ClusterBrowser topicId={string} onSelectContent={(contentId: string, title?: string) => void} />` component. Self-contained — owns its own query state, search bar, cluster list, drilldown.

- [ ] **Step 1: Write failing tests for ClusterBrowser**

Create `frontend/src/test/component/ClusterBrowser.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

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
      <MemoryRouter>{children}</MemoryRouter>
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/test/component/ClusterBrowser.test.tsx`
Expected: FAIL — module `../../components/clusters/ClusterBrowser` not found

- [ ] **Step 3: Create ClusterBrowser component**

Create `frontend/src/components/clusters/ClusterBrowser.tsx`:

```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { topicsApi, Cluster, ClusterContentItem } from '../../api/topics'
import { Badge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'
import { EmptyState } from '../ui/EmptyState'

const TIER_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  high:    { bg: 'bg-emerald-500/20', text: 'text-emerald-400', label: 'High' },
  medium:  { bg: 'bg-amber-500/20',   text: 'text-amber-400',   label: 'Medium' },
  low:     { bg: 'bg-red-500/20',     text: 'text-red-400',     label: 'Low' },
  keyword: { bg: 'bg-blue-500/20',    text: 'text-blue-400',    label: 'Keyword' },
}

function RelevanceBadge({ tier }: { tier?: string | null }) {
  if (!tier) return null
  const style = TIER_STYLES[tier] ?? TIER_STYLES.low
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  )
}

interface ClusterBrowserProps {
  topicId: string
  onSelectContent: (contentId: string, title?: string) => void
}

export function ClusterBrowser({ topicId, onSelectContent }: ClusterBrowserProps) {
  const [searchQ, setSearchQ] = useState('')
  const [searchActive, setSearchActive] = useState(false)
  const [expandedClusterId, setExpandedClusterId] = useState<string | null>(null)
  const [drilldownSort, setDrilldownSort] = useState<'time' | 'relevance'>('time')

  // Browse clusters
  const { data: clusters = [], isLoading } = useQuery({
    queryKey: ['clusters', topicId],
    queryFn: () => topicsApi.listClusters(topicId),
    enabled: !!topicId && !searchActive,
  })

  // Search clusters
  const { data: narrativeResults = [], isFetching: isSearching } = useQuery({
    queryKey: ['cluster-search', topicId, searchQ],
    queryFn: () => topicsApi.searchClusters(topicId, searchQ),
    enabled: searchActive && !!searchQ && !!topicId,
    staleTime: 60_000,
  })

  // Drilldown content
  const { data: clusterContent = [], isFetching: isDrilldownLoading } = useQuery({
    queryKey: ['cluster-content', topicId, expandedClusterId, drilldownSort, searchActive ? searchQ : ''],
    queryFn: () => topicsApi.getClusterContent(topicId, expandedClusterId!, {
      q: searchActive ? searchQ : undefined,
      sort: searchActive && searchQ ? drilldownSort : 'time',
      limit: 50,
    }),
    enabled: !!topicId && !!expandedClusterId,
  })

  const displayClusters: Cluster[] = searchActive ? narrativeResults : clusters

  const handleClusterClick = (id: string) => {
    if (expandedClusterId === id) {
      setExpandedClusterId(null)
    } else {
      setExpandedClusterId(id)
      setDrilldownSort(searchActive && searchQ ? 'relevance' : 'time')
    }
  }

  return (
    <div className="p-4">
      {/* Search bar */}
      <div className="flex gap-2 items-center mb-4">
        <input
          type="search"
          value={searchQ}
          onChange={(e) => setSearchQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && searchQ.trim()) setSearchActive(true)
            if (e.key === 'Escape') { setSearchActive(false); setSearchQ(''); setExpandedClusterId(null) }
          }}
          placeholder="Search narratives..."
          className="flex-1 bg-anveshak-card border border-anveshak-border rounded px-3 py-1.5 text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent"
        />
        {searchActive ? (
          <button
            onClick={() => { setSearchActive(false); setSearchQ(''); setExpandedClusterId(null) }}
            className="text-xs text-text-muted hover:text-text-primary px-2 py-1"
          >
            Clear
          </button>
        ) : (
          <button
            onClick={() => { if (searchQ.trim()) setSearchActive(true) }}
            disabled={!searchQ.trim()}
            className="text-xs text-anveshak-accent disabled:text-text-muted px-2 py-1"
          >
            Search
          </button>
        )}
      </div>

      {isLoading || isSearching ? (
        <div className="flex justify-center py-20">
          <Spinner label={isSearching ? 'Searching narratives...' : 'Loading clusters...'} />
        </div>
      ) : displayClusters.length === 0 ? (
        <EmptyState
          icon="📊"
          title={searchActive ? 'No matching narratives' : 'No clusters yet'}
          description={searchActive ? 'Try different keywords.' : 'Clusters emerge when enough content is analyzed.'}
        />
      ) : (
        <div className="max-w-3xl space-y-3">
          {/* Summary */}
          <div className="flex items-center gap-3 text-[10px] text-text-muted px-1">
            <span>
              {searchActive
                ? `${displayClusters.length} matching narrative${displayClusters.length !== 1 ? 's' : ''}`
                : `${displayClusters.length} cluster${displayClusters.length !== 1 ? 's' : ''}`}
            </span>
            <span className="text-anveshak-border">|</span>
            <span>{displayClusters.reduce((s, c) => s + c.item_count, 0)} total items</span>
          </div>

          {displayClusters.map((cluster) => {
            const isExpanded = expandedClusterId === cluster.id
            return (
              <div key={cluster.id}>
                <article
                  className={`bg-anveshak-card border border-anveshak-border rounded-lg p-4 hover:border-anveshak-accent/40 transition-all cursor-pointer ${
                    isExpanded ? 'ring-1 ring-anveshak-accent' : ''
                  }`}
                  onClick={() => handleClusterClick(cluster.id)}
                >
                  <div className="flex items-start justify-between mb-1">
                    <div className="flex items-center gap-2 min-w-0">
                      <h3 className="text-sm font-semibold text-text-primary truncate">{cluster.label ?? 'Unclassified'}</h3>
                      <RelevanceBadge tier={cluster.relevance_tier} />
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Badge variant="accent">{cluster.item_count}</Badge>
                      <span className="text-[10px] text-text-muted">{cluster.independent_source_count} sources</span>
                      <svg
                        viewBox="0 0 20 20" fill="currentColor"
                        className={`w-3 h-3 text-text-muted transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                      >
                        <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                      </svg>
                    </div>
                  </div>
                  {cluster.executive_summary && (
                    <p className="text-xs text-text-secondary leading-relaxed line-clamp-3">{cluster.executive_summary}</p>
                  )}
                  {cluster.sources?.length > 0 && (
                    <div className="flex gap-1.5 flex-wrap mt-2">
                      {cluster.sources.map((src, i) => (
                        <span key={i} className="text-[9px] bg-anveshak-muted rounded px-1.5 py-0.5 text-text-muted">
                          {src.platform.toUpperCase()} {src.source_name.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}
                        </span>
                      ))}
                    </div>
                  )}
                </article>

                {/* Drill-down */}
                {isExpanded && (
                  <div className="ml-4 mt-1 mb-2 border-l-2 border-anveshak-border/40 pl-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-[10px] text-text-muted">Sort:</span>
                      <button
                        className={`text-[10px] px-2 py-0.5 rounded ${drilldownSort === 'time' ? 'bg-anveshak-accent/20 text-anveshak-accent' : 'text-text-muted hover:text-text-primary'}`}
                        onClick={(e) => { e.stopPropagation(); setDrilldownSort('time') }}
                      >
                        Chronological
                      </button>
                      <button
                        className={`text-[10px] px-2 py-0.5 rounded ${drilldownSort === 'relevance' ? 'bg-anveshak-accent/20 text-anveshak-accent' : 'text-text-muted hover:text-text-primary'}`}
                        onClick={(e) => { e.stopPropagation(); setDrilldownSort('relevance') }}
                        disabled={!searchQ}
                      >
                        Relevance
                      </button>
                    </div>

                    {isDrilldownLoading ? (
                      <div className="py-3 flex justify-center">
                        <Spinner size="sm" label="Loading items..." />
                      </div>
                    ) : clusterContent.length === 0 ? (
                      <p className="text-[11px] text-text-muted py-2">No content items in this cluster.</p>
                    ) : (
                      <div className="space-y-2">
                        {clusterContent.map((item: ClusterContentItem) => (
                          <div
                            key={item.id}
                            className="bg-anveshak-card/50 border border-anveshak-border rounded-lg p-3 cursor-pointer hover:border-anveshak-accent/40 transition-colors"
                            onClick={(e) => { e.stopPropagation(); onSelectContent(item.id, item.title ?? undefined) }}
                          >
                            <div className="flex items-start justify-between gap-2 mb-1">
                              <div className="flex items-center gap-2 min-w-0">
                                {item.platform && (
                                  <span className="text-[9px] font-bold text-text-muted shrink-0">
                                    {item.platform.toUpperCase()}
                                  </span>
                                )}
                                <span className="text-[10px] text-text-muted truncate">
                                  {item.source_name?.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}
                                </span>
                                <RelevanceBadge tier={item.relevance_tier} />
                              </div>
                              <span className="text-[9px] text-text-muted shrink-0">
                                {new Date(item.captured_at).toLocaleDateString()}
                              </span>
                            </div>
                            {item.title && (
                              <p className="text-[11px] font-medium text-text-primary mb-1 line-clamp-1">{item.title}</p>
                            )}
                            <p className="text-[11px] text-text-secondary/80 leading-relaxed line-clamp-2">
                              {item.translated_text || item.clean_text}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run ClusterBrowser tests**

Run: `cd frontend && npx vitest run src/test/component/ClusterBrowser.test.tsx`
Expected: All 5 tests PASS

- [ ] **Step 5: Replace inline cluster rendering in TopicWorkspace with ClusterBrowser**

In `frontend/src/pages/TopicWorkspace.tsx`:

1. Add import at top (near other component imports):
```tsx
import { ClusterBrowser } from '../components/clusters/ClusterBrowser'
```

2. Remove these state variables (lines 70-71) since ClusterBrowser manages its own:
```tsx
// DELETE these two lines:
const [expandedClusterId, setExpandedClusterId] = useState<string | null>(null)
const [drilldownSort, setDrilldownSort] = useState<'time' | 'relevance'>('time')
```

3. Remove these queries that are now inside ClusterBrowser — the `clusters` query (lines 90-94), `narrativeResults` query (lines 97-102), `clusterContent` query (lines 105-113):
```tsx
// DELETE: const { data: clusters = [] } = useQuery({ ... clusters ... })
// DELETE: const { data: narrativeResults = [], ... } = useQuery({ ... cluster-search ... })
// DELETE: const { data: clusterContent = [], ... } = useQuery({ ... cluster-content ... })
```

4. Remove `isNarrativeSearching` from the `isSearching` const (line 123):
```tsx
// BEFORE:
const isSearching = isContentSearching || isNarrativeSearching
// AFTER:
const isSearching = isContentSearching
```

5. Remove the narrative search mode from the segmented control in the search bar (lines 216-236). Remove the `narratives` button. Remove the `searchMode` state variable and the `setSearchMode` usage. Simplify the search bar to only show when `activeTab === 'feed'`.

6. Replace the entire `{activeTab === 'clusters' && (() => { ... })()}` block (lines 326-475) with:
```tsx
{activeTab === 'clusters' && (
  <ClusterBrowser topicId={topicId} onSelectContent={handleSelectContent} />
)}
```

- [ ] **Step 6: Run existing tests to verify no regression**

Run: `cd frontend && npx vitest run src/test/component/IntelligenceView.test.tsx`
Expected: All PASS

- [ ] **Step 7: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 8: Commit**

```bash
cd frontend
git add src/components/clusters/ClusterBrowser.tsx src/test/component/ClusterBrowser.test.tsx src/pages/TopicWorkspace.tsx
git commit -m "refactor(frontend): extract ClusterBrowser from TopicWorkspace"
```

---

### Task 3: Create modal wrappers and wire into TopicWorkspace

**Files:**
- Create: `frontend/src/components/modals/IdentifiersModal.tsx`
- Create: `frontend/src/components/modals/ClustersModal.tsx`
- Create: `frontend/src/components/modals/ReportGenerationModal.tsx`
- Create: `frontend/src/components/modals/SourceManagementModal.tsx`
- Modify: `frontend/src/pages/Identifiers.tsx` (add `onSelectIdentifier` callback prop)
- Modify: `frontend/src/pages/TopicWorkspace.tsx` (add modal state + render modals)
- Test: `frontend/src/test/component/Modals.test.tsx`

**Interfaces:**
- Consumes: `Modal` (from Task 1), `ClusterBrowser` (from Task 2), `Identifiers` page, `ReportsTab`, `SourcesTab`
- Produces: Four modal components, each accepting `{ open: boolean; onClose: () => void; topicId: string }`. `IdentifiersModal` and `ClustersModal` also accept provenance callback.

- [ ] **Step 1: Add onSelectIdentifier prop to Identifiers page**

In `frontend/src/pages/Identifiers.tsx`, update the interface and component signature:

```tsx
interface IdentifiersProps {
  embedded?: boolean
  topicId?: string
  onSelectIdentifier?: (type: string, value: string) => void
}

export default function Identifiers({ embedded = false, topicId: propTopicId, onSelectIdentifier }: IdentifiersProps) {
```

Then in `TopIdentifiersTable`, pass `onSelectIdentifier` through and make rows clickable. Update the `TopIdentifiersTable` call (line 164):

```tsx
{view === 'top' && !isLoading && activeTopicId && (
  <TopIdentifiersTable items={topIdentifiers} onSelect={onSelectIdentifier} />
)}
```

Update `TopIdentifiersTable` function signature and add onClick to rows:

```tsx
function TopIdentifiersTable({ items, onSelect }: { items: TopIdentifier[]; onSelect?: (type: string, value: string) => void }) {
```

Add to each `<tr>`:
```tsx
<tr
  key={`${item.identifier_type}-${item.identifier_value}-${i}`}
  onClick={() => onSelect?.(item.identifier_type, item.identifier_value)}
  className="border-b border-anveshak-border/50 hover:bg-anveshak-muted/50 transition-colors cursor-pointer"
>
```

- [ ] **Step 2: Create IdentifiersModal**

Create `frontend/src/components/modals/IdentifiersModal.tsx`:

```tsx
import { lazy, Suspense } from 'react'
import { Modal } from '../ui/Modal'
import { Spinner } from '../ui/Spinner'

const Identifiers = lazy(() => import('../../pages/Identifiers'))

interface IdentifiersModalProps {
  open: boolean
  onClose: () => void
  topicId: string
  onSelectIdentifier?: (type: string, value: string) => void
}

export function IdentifiersModal({ open, onClose, topicId, onSelectIdentifier }: IdentifiersModalProps) {
  const handleSelect = (type: string, value: string) => {
    onSelectIdentifier?.(type, value)
    onClose()
  }

  return (
    <Modal fullScreen open={open} onClose={onClose} title="All Identifiers">
      <Suspense fallback={<div className="p-6"><Spinner label="Loading identifiers..." /></div>}>
        <Identifiers embedded topicId={topicId} onSelectIdentifier={handleSelect} />
      </Suspense>
    </Modal>
  )
}
```

- [ ] **Step 3: Create ClustersModal**

Create `frontend/src/components/modals/ClustersModal.tsx`:

```tsx
import { Modal } from '../ui/Modal'
import { ClusterBrowser } from '../clusters/ClusterBrowser'

interface ClustersModalProps {
  open: boolean
  onClose: () => void
  topicId: string
  onSelectContent?: (contentId: string, title?: string) => void
}

export function ClustersModal({ open, onClose, topicId, onSelectContent }: ClustersModalProps) {
  const handleSelect = (contentId: string, title?: string) => {
    onSelectContent?.(contentId, title)
    onClose()
  }

  return (
    <Modal fullScreen open={open} onClose={onClose} title="All Clusters">
      <ClusterBrowser topicId={topicId} onSelectContent={handleSelect} />
    </Modal>
  )
}
```

- [ ] **Step 4: Create ReportGenerationModal**

Create `frontend/src/components/modals/ReportGenerationModal.tsx`:

```tsx
import { lazy, Suspense } from 'react'
import { Modal } from '../ui/Modal'
import { Spinner } from '../ui/Spinner'

const ReportsTab = lazy(() => import('../workspace/ReportsTab'))

interface ReportGenerationModalProps {
  open: boolean
  onClose: () => void
  topicId: string
}

export function ReportGenerationModal({ open, onClose, topicId }: ReportGenerationModalProps) {
  return (
    <Modal fullScreen open={open} onClose={onClose} title="Generate Report">
      <Suspense fallback={<div className="p-6"><Spinner label="Loading reports..." /></div>}>
        <ReportsTab topicId={topicId} />
      </Suspense>
    </Modal>
  )
}
```

- [ ] **Step 5: Create SourceManagementModal**

Create `frontend/src/components/modals/SourceManagementModal.tsx`:

```tsx
import { lazy, Suspense } from 'react'
import { Modal } from '../ui/Modal'
import { Spinner } from '../ui/Spinner'

const SourcesTab = lazy(() => import('../workspace/SourcesTab'))

interface SourceManagementModalProps {
  open: boolean
  onClose: () => void
  topicId: string
}

export function SourceManagementModal({ open, onClose, topicId }: SourceManagementModalProps) {
  return (
    <Modal fullScreen open={open} onClose={onClose} title="Manage Sources">
      <Suspense fallback={<div className="p-6"><Spinner label="Loading sources..." /></div>}>
        <SourcesTab topicId={topicId} />
      </Suspense>
    </Modal>
  )
}
```

- [ ] **Step 6: Write tests for modal wrappers**

Create `frontend/src/test/component/Modals.test.tsx`:

```tsx
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
```

- [ ] **Step 7: Run modal tests**

Run: `cd frontend && npx vitest run src/test/component/Modals.test.tsx`
Expected: All 10 tests PASS

- [ ] **Step 8: Wire modals into TopicWorkspace**

In `frontend/src/pages/TopicWorkspace.tsx`:

1. Add imports:
```tsx
import { IdentifiersModal } from '../components/modals/IdentifiersModal'
import { ClustersModal } from '../components/modals/ClustersModal'
import { ReportGenerationModal } from '../components/modals/ReportGenerationModal'
import { SourceManagementModal } from '../components/modals/SourceManagementModal'
```

2. Add modal state (after existing state variables, around line 74):
```tsx
const [showIdentifiersModal, setShowIdentifiersModal] = useState(false)
const [showClustersModal, setShowClustersModal] = useState(false)
const [showReportModal, setShowReportModal] = useState(false)
const [showSourcesModal, setShowSourcesModal] = useState(false)
```

3. Add provenance handler for identifier selection (after `handleSelectContent`):
```tsx
const handleSelectIdentifier = (type: string, value: string) => {
  provenance.push({
    entityType: 'identifier',
    entityId: value,
    topicId: topicId!,
    label: value,
  })
}
```

4. Update IntelligenceView callbacks (around line 282-291):
```tsx
<IntelligenceView
  topicId={topicId}
  topicStatus={topic?.status}
  onNavigateMap={() => handleTabSwitch('map')}
  onNavigateContent={() => handleTabSwitch('feed')}
  onShowAllClusters={() => setShowClustersModal(true)}
  onShowAllIdentifiers={() => setShowIdentifiersModal(true)}
  onGenerateReport={() => setShowReportModal(true)}
  onManageSources={() => setShowSourcesModal(true)}
/>
```

5. Render modals before closing `</div>` of the component (before the entity graph and signal graph modals, around line 527):
```tsx
{/* Full-screen content modals */}
<IdentifiersModal
  open={showIdentifiersModal}
  onClose={() => setShowIdentifiersModal(false)}
  topicId={topicId}
  onSelectIdentifier={handleSelectIdentifier}
/>
<ClustersModal
  open={showClustersModal}
  onClose={() => setShowClustersModal(false)}
  topicId={topicId}
  onSelectContent={handleSelectContent}
/>
<ReportGenerationModal
  open={showReportModal}
  onClose={() => setShowReportModal(false)}
  topicId={topicId}
/>
<SourceManagementModal
  open={showSourcesModal}
  onClose={() => setShowSourcesModal(false)}
  topicId={topicId}
/>
```

- [ ] **Step 9: Run all tests**

Run: `cd frontend && npx vitest run`
Expected: All tests PASS

- [ ] **Step 10: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 11: Commit**

```bash
cd frontend
git add src/components/modals/ src/pages/Identifiers.tsx src/pages/TopicWorkspace.tsx src/test/component/Modals.test.tsx
git commit -m "feat(frontend): add full-screen modals for identifiers, clusters, reports, sources (#10)"
```
