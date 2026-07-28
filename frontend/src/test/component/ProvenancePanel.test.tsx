import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ProvenanceProvider, useProvenance, type ProvenanceStackEntry } from '../../contexts/ProvenanceContext'
import { ProvenancePanel } from '../../components/provenance/ProvenancePanel'
import { ProvenanceBreadcrumb } from '../../components/provenance/ProvenanceBreadcrumb'

// ── Mock lazy-loaded detail components ─────────────────────────────────
vi.mock('../../components/provenance/IdentifierDetail', () => ({
  default: ({ identifierValue }: { identifierValue: string }) => (
    <div data-testid="identifier-detail">{identifierValue}</div>
  ),
}))
vi.mock('../../components/provenance/ContentDetailView', () => ({
  default: ({ contentId }: { contentId: string }) => (
    <div data-testid="content-detail">{contentId}</div>
  ),
}))
vi.mock('../../components/provenance/SourceDetail', () => ({
  default: ({ sourceId }: { sourceId: string }) => (
    <div data-testid="source-detail">{sourceId}</div>
  ),
}))
vi.mock('../../components/provenance/ClusterDetail', () => ({
  default: ({ clusterId }: { clusterId: string }) => (
    <div data-testid="cluster-detail">{clusterId}</div>
  ),
}))
vi.mock('../../components/provenance/SignalDetail', () => ({
  default: ({ signalId }: { signalId: string }) => (
    <div data-testid="signal-detail">{signalId}</div>
  ),
}))

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
}

function renderWithProviders(ui: React.ReactElement) {
  const qc = createQueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ProvenanceProvider>{ui}</ProvenanceProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

// Helper component to trigger provenance actions from tests
function PanelHarness({ autoOpen }: { autoOpen?: ProvenanceStackEntry }) {
  const { push, pop, close, stack, isOpen, current } = useProvenance()
  return (
    <div>
      <button data-testid="push-identifier" onClick={() => push({ entityType: 'identifier', entityId: 'UPI-123', topicId: 't1', label: 'UPI-123' })}>Push Identifier</button>
      <button data-testid="push-content" onClick={() => push({ entityType: 'content', entityId: 'c-abc', topicId: 't1', label: 'Article A' })}>Push Content</button>
      <button data-testid="push-source" onClick={() => push({ entityType: 'source', entityId: 's-1', topicId: 't1', label: 'Source X' })}>Push Source</button>
      <button data-testid="push-cluster" onClick={() => push({ entityType: 'cluster', entityId: 'cl-1', topicId: 't1', label: 'Cluster Y' })}>Push Cluster</button>
      <button data-testid="push-signal" onClick={() => push({ entityType: 'signal', entityId: 'sig-1', topicId: 't1', label: 'Signal Z' })}>Push Signal</button>
      <button data-testid="pop" onClick={pop}>Pop</button>
      <button data-testid="close" onClick={close}>Close</button>
      <span data-testid="stack-depth">{stack.length}</span>
      <span data-testid="is-open">{isOpen ? 'open' : 'closed'}</span>
      <span data-testid="current-type">{current?.entityType ?? 'none'}</span>
      <ProvenancePanel />
    </div>
  )
}

describe('ProvenanceContext — stack operations', () => {
  it('starts closed with empty stack', () => {
    renderWithProviders(<PanelHarness />)
    expect(screen.getByTestId('stack-depth')).toHaveTextContent('0')
    expect(screen.getByTestId('is-open')).toHaveTextContent('closed')
    expect(screen.getByTestId('current-type')).toHaveTextContent('none')
  })

  it('push opens panel and sets current', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-identifier')) })
    expect(screen.getByTestId('stack-depth')).toHaveTextContent('1')
    expect(screen.getByTestId('is-open')).toHaveTextContent('open')
    expect(screen.getByTestId('current-type')).toHaveTextContent('identifier')
  })

  it('multiple pushes build stack, current is last', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-identifier')) })
    await act(async () => { fireEvent.click(screen.getByTestId('push-content')) })
    await act(async () => { fireEvent.click(screen.getByTestId('push-source')) })
    expect(screen.getByTestId('stack-depth')).toHaveTextContent('3')
    expect(screen.getByTestId('current-type')).toHaveTextContent('source')
  })

  it('pop removes top entry', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-identifier')) })
    await act(async () => { fireEvent.click(screen.getByTestId('push-content')) })
    await act(async () => { fireEvent.click(screen.getByTestId('pop')) })
    expect(screen.getByTestId('stack-depth')).toHaveTextContent('1')
    expect(screen.getByTestId('current-type')).toHaveTextContent('identifier')
  })

  it('pop on single entry closes panel', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-identifier')) })
    await act(async () => { fireEvent.click(screen.getByTestId('pop')) })
    expect(screen.getByTestId('stack-depth')).toHaveTextContent('0')
    expect(screen.getByTestId('is-open')).toHaveTextContent('closed')
  })

  it('close clears entire stack', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-identifier')) })
    await act(async () => { fireEvent.click(screen.getByTestId('push-content')) })
    await act(async () => { fireEvent.click(screen.getByTestId('push-source')) })
    await act(async () => { fireEvent.click(screen.getByTestId('close')) })
    expect(screen.getByTestId('stack-depth')).toHaveTextContent('0')
    expect(screen.getByTestId('is-open')).toHaveTextContent('closed')
  })
})

describe('ProvenancePanel — entity type rendering', () => {
  it('renders IdentifierDetail for identifier entity', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-identifier')) })
    expect(screen.getByTestId('identifier-detail')).toHaveTextContent('UPI-123')
  })

  it('renders ContentDetailView for content entity', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-content')) })
    expect(screen.getByTestId('content-detail')).toHaveTextContent('c-abc')
  })

  it('renders SourceDetail for source entity', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-source')) })
    expect(screen.getByTestId('source-detail')).toHaveTextContent('s-1')
  })

  it('renders ClusterDetail for cluster entity', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-cluster')) })
    expect(screen.getByTestId('cluster-detail')).toHaveTextContent('cl-1')
  })

  it('renders SignalDetail for signal entity', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-signal')) })
    expect(screen.getByTestId('signal-detail')).toHaveTextContent('sig-1')
  })
})

describe('ProvenancePanel — navigation controls', () => {
  it('shows back button when stack depth > 1', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-identifier')) })
    // Depth 1 — no back button
    expect(screen.queryByLabelText('Back')).not.toBeInTheDocument()

    await act(async () => { fireEvent.click(screen.getByTestId('push-content')) })
    // Depth 2 — back button visible
    expect(screen.getByLabelText('Back')).toBeInTheDocument()
  })

  it('back button pops stack', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-identifier')) })
    await act(async () => { fireEvent.click(screen.getByTestId('push-content')) })
    await act(async () => { fireEvent.click(screen.getByLabelText('Back')) })
    expect(screen.getByTestId('stack-depth')).toHaveTextContent('1')
    expect(screen.getByTestId('current-type')).toHaveTextContent('identifier')
  })

  it('close button clears stack', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-identifier')) })
    await act(async () => { fireEvent.click(screen.getByLabelText('Close panel')) })
    expect(screen.getByTestId('is-open')).toHaveTextContent('closed')
  })

  it('panel is not rendered when stack is empty', () => {
    renderWithProviders(<PanelHarness />)
    expect(screen.queryByLabelText('Provenance panel')).not.toBeInTheDocument()
  })

  it('backdrop click closes panel (overlay mode)', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-identifier')) })
    expect(screen.getByTestId('is-open')).toHaveTextContent('open')

    // Click the backdrop (aria-hidden div)
    const backdrop = screen.getByLabelText('Provenance panel').previousElementSibling
    if (backdrop) {
      await act(async () => { fireEvent.click(backdrop) })
      expect(screen.getByTestId('is-open')).toHaveTextContent('closed')
    }
  })

  it('panel renders as fixed overlay (not static flex sibling)', async () => {
    renderWithProviders(<PanelHarness />)
    await act(async () => { fireEvent.click(screen.getByTestId('push-identifier')) })
    const panel = screen.getByLabelText('Provenance panel')
    expect(panel.className).toContain('fixed')
    expect(panel.className).not.toContain('md:static')
  })
})

describe('ProvenanceBreadcrumb', () => {
  const stack: ProvenanceStackEntry[] = [
    { entityType: 'identifier', entityId: 'UPI-123', label: 'UPI-123' },
    { entityType: 'content', entityId: 'c-1', label: 'Article A' },
    { entityType: 'source', entityId: 's-1', label: 'Source X' },
  ]

  it('renders breadcrumb entries for each stack item', () => {
    const onJumpTo = vi.fn()
    render(<ProvenanceBreadcrumb stack={stack} onJumpTo={onJumpTo} />)
    expect(screen.getByText('UPI-123')).toBeInTheDocument()
    expect(screen.getByText('Article A')).toBeInTheDocument()
    expect(screen.getByText('Source X')).toBeInTheDocument()
  })

  it('last entry is not clickable (disabled)', () => {
    const onJumpTo = vi.fn()
    render(<ProvenanceBreadcrumb stack={stack} onJumpTo={onJumpTo} />)
    // "Source X" is the last entry — its button should be disabled
    const buttons = screen.getAllByRole('button')
    const lastBtn = buttons[buttons.length - 1]
    expect(lastBtn).toBeDisabled()
  })

  it('clicking non-last entry calls onJumpTo with index', () => {
    const onJumpTo = vi.fn()
    render(<ProvenanceBreadcrumb stack={stack} onJumpTo={onJumpTo} />)
    // Click first entry (index 0)
    fireEvent.click(screen.getByText('UPI-123'))
    expect(onJumpTo).toHaveBeenCalledWith(0)
  })

  it('renders nothing for empty stack', () => {
    const { container } = render(<ProvenanceBreadcrumb stack={[]} onJumpTo={vi.fn()} />)
    expect(container.innerHTML).toBe('')
  })
})
