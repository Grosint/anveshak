import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { trackersApi } from '../../api/trackers'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'

interface ConcludeModalProps {
  open: boolean
  trackerId: string
  onClose: () => void
  onConcluded: () => void
}

export function ConcludeModal({ open, trackerId, onClose, onConcluded }: ConcludeModalProps) {
  const [summary, setSummary] = useState('')
  const [error, setError] = useState<string | null>(null)

  const concludeMutation = useMutation({
    mutationFn: () =>
      trackersApi.updateStatus(trackerId, {
        status: 'concluded',
        closing_summary: summary.trim(),
      }),
    onSuccess: () => {
      setSummary('')
      setError(null)
      onConcluded()
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to conclude tracker.')
    },
  })

  function handleClose() {
    setSummary('')
    setError(null)
    onClose()
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!summary.trim()) {
      setError('Closing summary is required before concluding.')
      return
    }
    concludeMutation.mutate()
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Conclude Tracker"
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={handleClose} disabled={concludeMutation.isPending}>
            Cancel
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={handleSubmit}
            loading={concludeMutation.isPending}
          >
            Conclude
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-text-muted">
          Concluding this tracker marks the investigation as closed. This action cannot be undone
          through normal workflow. Provide a closing summary before proceeding.
        </p>

        {error && (
          <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded px-3 py-2">
            {error}
          </p>
        )}

        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">
            Closing Summary <span className="text-red-400">*</span>
          </label>
          <textarea
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder="Summarise findings, outcome, and disposition of this investigation…"
            rows={5}
            className="w-full bg-anveshak-card border border-anveshak-border rounded px-3 py-2 text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent resize-none"
            autoFocus
          />
        </div>
      </form>
    </Modal>
  )
}
