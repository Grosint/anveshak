import { useState } from 'react'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { CreateSourcePayload, Platform } from '../../api/sources'

const PLATFORMS: { value: Platform; label: string }[] = [
  { value: 'web',      label: 'Web (URL)' },
  { value: 'telegram', label: 'Telegram' },
  { value: 'reddit',   label: 'Reddit' },
  { value: 'bluesky',  label: 'Bluesky' },
  { value: 'twitter',  label: 'X / Twitter' },
  { value: 'rss',      label: 'RSS Feed' },
]

interface AddSourceModalProps {
  open: boolean
  onClose: () => void
  onSubmit: (payload: CreateSourcePayload) => Promise<void>
}

export function AddSourceModal({ open, onClose, onSubmit }: AddSourceModalProps) {
  const [name, setName]             = useState('')
  const [handle, setHandle]         = useState('')
  const [platform, setPlatform]     = useState<Platform>('web')
  const [credibility, setCredibility] = useState(50)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError]           = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim() || !handle.trim()) { setError('Name and URL/handle are required.'); return }
    setError('')
    setSubmitting(true)
    try {
      await onSubmit({ name: name.trim(), url_or_handle: handle.trim(), platform, credibility_score: credibility })
      setName(''); setHandle(''); setPlatform('web'); setCredibility(50)
      onClose()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? 'Failed to add source.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add source"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>Cancel</Button>
          <Button form="add-source-form" type="submit" loading={submitting}>Add source</Button>
        </>
      }
    >
      <form id="add-source-form" onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div>
          <label htmlFor="src-name" className="block text-xs font-medium text-text-secondary mb-1.5">
            Source name <span className="text-signal-high">*</span>
          </label>
          <input
            id="src-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-anveshak-accent"
            placeholder="e.g. South China Morning Post"
          />
        </div>

        <div>
          <label htmlFor="src-platform" className="block text-xs font-medium text-text-secondary mb-1.5">Platform</label>
          <select
            id="src-platform"
            value={platform}
            onChange={(e) => setPlatform(e.target.value as Platform)}
            className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-anveshak-accent"
          >
            {PLATFORMS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="src-handle" className="block text-xs font-medium text-text-secondary mb-1.5">
            URL / Handle <span className="text-signal-high">*</span>
          </label>
          <input
            id="src-handle"
            type="text"
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-anveshak-accent"
            placeholder={platform === 'web' ? 'https://example.com' : platform === 'reddit' ? 'r/worldnews' : '@handle'}
          />
        </div>

        <div>
          <label htmlFor="src-cred" className="block text-xs font-medium text-text-secondary mb-1.5">
            Initial credibility score: <span className="text-anveshak-accent font-semibold">{credibility}</span>
          </label>
          <input
            id="src-cred"
            type="range"
            min={0}
            max={100}
            value={credibility}
            onChange={(e) => setCredibility(Number(e.target.value))}
            className="w-full accent-anveshak-accent"
            aria-label={`Credibility score: ${credibility}`}
          />
          <div className="flex justify-between text-[10px] text-text-muted mt-1">
            <span>0 (untrusted)</span><span>50</span><span>100 (trusted)</span>
          </div>
        </div>

        {error && (
          <p role="alert" className="text-signal-high text-xs bg-signal-high/10 border border-signal-high/20 rounded px-3 py-2">
            {error}
          </p>
        )}
      </form>
    </Modal>
  )
}
