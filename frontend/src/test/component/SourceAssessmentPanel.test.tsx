import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import rehypeSanitize from 'rehype-sanitize'
import type { SourceAssessment, SourceStats } from '../../api/assessments'

// Capture the props react-markdown is rendered with. The brief is LLM prose
// written over scraped, untrusted text, so the sanitiser must be wired in.
const markdownProps: Record<string, unknown>[] = []
vi.mock('react-markdown', () => ({
  default: (props: Record<string, unknown>) => {
    markdownProps.push(props)
    return <div data-testid="markdown">{props.children as string}</div>
  },
}))

vi.mock('recharts', () => {
  const Stub = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>
  return {
    ResponsiveContainer: Stub, BarChart: Stub, Bar: Stub, XAxis: Stub, YAxis: Stub,
    Tooltip: Stub, AreaChart: Stub, Area: Stub, PieChart: Stub, Pie: Stub, Cell: Stub,
  }
})

const create = vi.fn()
vi.mock('../../api/assessments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/assessments')>()
  return {
    ...actual,
    assessmentsApi: {
      create: (...args: unknown[]) => create(...args),
      get: vi.fn(),
      generateBrief: vi.fn(),
    },
  }
})

const EMPTY_STATS: SourceStats = {
  total_posts: 3,
  first_post: '2026-08-01T00:00:00Z',
  last_post: '2026-08-30T00:00:00Z',
  avg_posts_per_day: 0.1,
  engagement: { likes: 1, comments: 0, shares: 0, views: 10 },
  language_breakdown: [],
  volume_timeline: [],
  top_entities: [],
  identifier_overlap: [],
  cluster_participation: [],
  sentiment_distribution: { negative: 1, neutral: 1, positive: 1 },
  credibility_trajectory: [],
}

const ASSESSMENT: SourceAssessment = {
  id: 'a-1',
  topic_id: 't-1',
  source_id: 's-1',
  time_window_start: '2026-08-01T00:00:00Z',
  time_window_end: '2026-08-31T00:00:00Z',
  content_item_count: 3,
  stats: EMPTY_STATS,
  source_snapshot: null,
  platform_metadata: null,
  brief_md: 'Brief body from the model.',
  confidence_score: 0.8,
  generated_at: '2026-08-31T00:00:00Z',
  generation_status: 'complete',
  created_at: '2026-08-31T00:00:00Z',
}

async function renderPanel() {
  const { default: SourceAssessmentPanel } = await import(
    '../../components/workspace/SourceAssessmentPanel'
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  render(
    <QueryClientProvider client={client}>
      <SourceAssessmentPanel topicId="t-1" sourceId="s-1" sourceName="Example Feed" onClose={() => {}} />
    </QueryClientProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: /Assess Source/i }))
  await waitFor(() => expect(screen.getByTestId('markdown')).toBeTruthy())
}

describe('SourceAssessmentPanel brief rendering', () => {
  beforeEach(() => {
    markdownProps.length = 0
    create.mockReset()
    create.mockResolvedValue(ASSESSMENT)
  })

  it('renders the brief markdown', async () => {
    await renderPanel()
    expect(screen.getByTestId('markdown').textContent).toBe('Brief body from the model.')
  })

  // Wiring assertion, not a stripping assertion: react-markdown is mocked, so
  // this proves the plugin is passed. With react-markdown v9 and no rehype-raw
  // in the tree, rehypeSanitize is defense in depth, not today's XSS fix.
  it('wires rehypeSanitize into the brief renderer', async () => {
    await renderPanel()
    const rehypePlugins = markdownProps[0]?.rehypePlugins as unknown[] | undefined
    expect(rehypePlugins).toBeDefined()
    expect(rehypePlugins).toContain(rehypeSanitize)
  })
})
