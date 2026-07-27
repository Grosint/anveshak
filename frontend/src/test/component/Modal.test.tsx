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
