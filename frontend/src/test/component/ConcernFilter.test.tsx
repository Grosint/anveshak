/**
 * Concern category filter — issue #36, ADR 0001.
 *
 * The system never surfaces a category unprompted, and applying a filter
 * changes membership without changing ordering.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConcernFilter } from '../../components/intelligence/ConcernFilter'

const mockTaxonomy = vi.fn()
vi.mock('../../api/concern', () => ({
  concernApi: {
    taxonomy: (...args: any[]) => mockTaxonomy(...args),
    clustersByConcern: vi.fn(),
  },
}))

const TAXONOMY = {
  version: 1,
  owner: 'customer',
  categories: [
    { id: 'financial_fraud', label: 'Financial fraud', definition: 'Payment solicitation.' },
    {
      id: 'incitement_to_violence',
      label: 'Incitement to violence',
      definition: 'Calls for physical harm.',
    },
  ],
}

function renderFilter(selected: string[] = [], onChange = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  render(
    <QueryClientProvider client={client}>
      <ConcernFilter selected={selected} onChange={onChange} />
    </QueryClientProvider>,
  )
  return onChange
}

beforeEach(() => {
  mockTaxonomy.mockReset()
  mockTaxonomy.mockResolvedValue(TAXONOMY)
})

describe('Categories are never surfaced unprompted', () => {
  it('shows no category until the analyst opens the filter', () => {
    renderFilter()
    expect(screen.queryByText('Financial fraud')).not.toBeInTheDocument()
  })

  it('does not fetch the taxonomy until it is opened', () => {
    renderFilter()
    expect(mockTaxonomy).not.toHaveBeenCalled()
  })

  it('fetches and shows categories once opened', async () => {
    renderFilter()
    fireEvent.click(screen.getByText(/filter by concern category/i))
    await waitFor(() => expect(screen.getByText('Financial fraud')).toBeInTheDocument())
    expect(screen.getByText('Incitement to violence')).toBeInTheDocument()
  })
})

describe('Selection', () => {
  it('reports a category the analyst selects', async () => {
    const onChange = renderFilter()
    fireEvent.click(screen.getByText(/filter by concern category/i))
    await waitFor(() => expect(screen.getByLabelText('Financial fraud')).toBeInTheDocument())
    fireEvent.click(screen.getByLabelText('Financial fraud'))
    expect(onChange).toHaveBeenCalledWith(['financial_fraud'])
  })

  it('deselects a selected category', async () => {
    const onChange = renderFilter(['financial_fraud'])
    fireEvent.click(screen.getByText(/filter by concern category/i))
    await waitFor(() => expect(screen.getByLabelText('Financial fraud')).toBeInTheDocument())
    fireEvent.click(screen.getByLabelText('Financial fraud'))
    expect(onChange).toHaveBeenCalledWith([])
  })

  it('shows how many are selected', () => {
    renderFilter(['financial_fraud', 'incitement_to_violence'])
    expect(screen.getByText(/filter by concern category \(2\)/i)).toBeInTheDocument()
  })
})

describe('The filter offers no ordering', () => {
  it('has no sort control', async () => {
    renderFilter()
    fireEvent.click(screen.getByText(/filter by concern category/i))
    await waitFor(() => expect(screen.getByText('Financial fraud')).toBeInTheDocument())
    expect(screen.queryByText(/sort/i)).not.toBeInTheDocument()
  })

  it('states that the order does not change', async () => {
    renderFilter()
    fireEvent.click(screen.getByText(/filter by concern category/i))
    await waitFor(() => expect(screen.getByText(/order stays as it was/i)).toBeInTheDocument())
  })

  it('names whose taxonomy it is', async () => {
    renderFilter()
    fireEvent.click(screen.getByText(/filter by concern category/i))
    await waitFor(() => expect(screen.getByText(/owned by the customer/i)).toBeInTheDocument())
  })
})
