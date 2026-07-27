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
