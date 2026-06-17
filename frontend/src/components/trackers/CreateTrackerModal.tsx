import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { trackersApi, type Tracker } from '../../api/trackers'
import { topicsApi } from '../../api/topics'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'

interface CreateTrackerModalProps {
  open: boolean
  onClose: () => void
  onCreated: (tracker: Tracker) => void
}

export function CreateTrackerModal({ open, onClose, onCreated }: CreateTrackerModalProps) {
  const [title, setTitle] = useState('')
  const [topicId, setTopicId] = useState('')
  const [externalRef, setExternalRef] = useState('')
  const [priority, setPriority] = useState<'low' | 'medium' | 'high' | 'critical'>('medium')
  const [error, setError] = useState<string | null>(null)

  const { data: topics = [] } = useQuery({
    queryKey: ['topics'],
    queryFn: topicsApi.list,
    staleTime: 60_000,
    enabled: open,
  })

  const createMutation = useMutation({
    mutationFn: () =>
      trackersApi.create({
        title: title.trim(),
        topic_id: topicId,
        external_case_ref: externalRef.trim() || undefined,
        priority,
      }),
    onSuccess: (tracker) => {
      resetForm()
      onCreated(tracker)
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to create tracker.')
    },
  })

  function resetForm() {
    setTitle('')
    setTopicId('')
    setExternalRef('')
    setPriority('medium')
    setError(null)
  }

  function handleClose() {
    resetForm()
    onClose()
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!title.trim()) { setError('Title is required.'); return }
    if (!topicId) { setError('Topic is required.'); return }
    createMutation.mutate()
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="New Tracker"
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={handleClose} disabled={createMutation.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleSubmit}
            loading={createMutation.isPending}
          >
            Create Tracker
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded px-3 py-2">
            {error}
          </p>
        )}

        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">
            Title <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Short descriptive title for this tracker"
            className="w-full bg-anveshak-card border border-anveshak-border rounded px-3 py-2 text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent"
            autoFocus
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">
            Topic <span className="text-red-400">*</span>
          </label>
          <select
            value={topicId}
            onChange={(e) => setTopicId(e.target.value)}
            className="w-full bg-anveshak-card border border-anveshak-border rounded px-3 py-2 text-text-primary text-sm focus:outline-none focus:border-anveshak-accent"
          >
            <option value="">Select a topic…</option>
            {topics.map((topic) => (
              <option key={topic.id} value={topic.id}>
                {topic.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">
            External Case Ref <span className="text-text-muted font-normal">(optional)</span>
          </label>
          <input
            type="text"
            value={externalRef}
            onChange={(e) => setExternalRef(e.target.value)}
            placeholder="FIR number, ECIR, case reference…"
            className="w-full bg-anveshak-card border border-anveshak-border rounded px-3 py-2 text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">
            Priority <span className="text-text-muted font-normal">(optional)</span>
          </label>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as typeof priority)}
            className="w-full bg-anveshak-card border border-anveshak-border rounded px-3 py-2 text-text-primary text-sm focus:outline-none focus:border-anveshak-accent"
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>
      </form>
    </Modal>
  )
}
