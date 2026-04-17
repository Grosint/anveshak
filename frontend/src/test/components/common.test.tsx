import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { EmptyState } from '../../components/ui/EmptyState'

describe('Badge component', () => {
  it('renders text content', () => {
    render(<Badge>Active</Badge>)
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('accepts variant prop', () => {
    render(<Badge variant="success">OK</Badge>)
    expect(screen.getByText('OK')).toBeInTheDocument()
  })
})

describe('Button component', () => {
  it('renders text content', () => {
    render(<Button>Click Me</Button>)
    expect(screen.getByText('Click Me')).toBeInTheDocument()
  })

  it('renders as a button element', () => {
    render(<Button>Test</Button>)
    expect(screen.getByRole('button')).toBeInTheDocument()
  })
})

describe('Spinner component', () => {
  it('renders without crashing', () => {
    const { container } = render(<Spinner />)
    expect(container.firstChild).toBeTruthy()
  })
})

describe('EmptyState component', () => {
  it('renders title and description', () => {
    render(<EmptyState title="No data" description="No data available" />)
    expect(screen.getByText('No data')).toBeInTheDocument()
    expect(screen.getByText('No data available')).toBeInTheDocument()
  })
})
