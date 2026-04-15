import { useState, KeyboardEvent } from 'react'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { CreateTopicPayload } from '../../api/topics'

interface CreateTopicModalProps {
  open: boolean
  onClose: () => void
  onSubmit: (payload: CreateTopicPayload) => Promise<void>
}

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'ru', label: 'Russian' },
  { code: 'zh', label: 'Chinese' },
  { code: 'hi', label: 'Hindi' },
  { code: 'ar', label: 'Arabic' },
]

function TagInput({
  label,
  placeholder,
  tags,
  onChange,
}: {
  label: string
  placeholder: string
  tags: string[]
  onChange: (tags: string[]) => void
}) {
  const [input, setInput] = useState('')

  function add() {
    const val = input.trim()
    if (val && !tags.includes(val)) onChange([...tags, val])
    setInput('')
  }

  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add() }
    if (e.key === 'Backspace' && !input && tags.length) {
      onChange(tags.slice(0, -1))
    }
  }

  return (
    <div>
      <label className="block text-xs font-medium text-text-secondary mb-1.5">{label}</label>
      <div className="flex flex-wrap gap-1.5 p-2 bg-anveshak-bg border border-anveshak-border rounded min-h-[42px]">
        {tags.map((t) => (
          <span
            key={t}
            className="inline-flex items-center gap-1 bg-anveshak-accent/20 text-anveshak-accent text-xs px-2 py-0.5 rounded"
          >
            {t}
            <button
              type="button"
              onClick={() => onChange(tags.filter((x) => x !== t))}
              className="hover:text-white ml-0.5"
              aria-label={`Remove ${t}`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          className="flex-1 min-w-[120px] bg-transparent text-sm text-text-primary placeholder:text-text-muted outline-none"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKey}
          onBlur={add}
          placeholder={tags.length === 0 ? placeholder : 'Add more…'}
        />
      </div>
      <p className="text-[10px] text-text-muted mt-1">Press Enter or comma to add</p>
    </div>
  )
}

export function CreateTopicModal({ open, onClose, onSubmit }: CreateTopicModalProps) {
  const [name, setName]               = useState('')
  const [keywords, setKeywords]       = useState<string[]>([])
  const [languages, setLanguages]     = useState<string[]>(['en'])
  const [threshold, setThreshold]     = useState(3)
  const [credMin, setCredMin]         = useState(30)
  const [clipCats, setClipCats]       = useState<string[]>([])
  const [submitting, setSubmitting]   = useState(false)
  const [error, setError]             = useState('')

  function toggleLang(code: string) {
    setLanguages((prev) =>
      prev.includes(code) ? prev.filter((l) => l !== code) : [...prev, code],
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) { setError('Name is required.'); return }
    if (keywords.length === 0) { setError('Add at least one keyword.'); return }
    if (languages.length === 0) { setError('Select at least one language.'); return }
    setError('')
    setSubmitting(true)
    try {
      await onSubmit({
        name: name.trim(),
        keywords,
        languages,
        signal_threshold: threshold,
        credibility_min: credMin,
        clip_categories: clipCats,
      })
      // Reset form
      setName(''); setKeywords([]); setLanguages(['en'])
      setThreshold(3); setCredMin(30); setClipCats([])
      onClose()
    } catch {
      setError('Failed to create topic. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Create monitoring topic"
      maxWidth="max-w-xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>Cancel</Button>
          <Button form="create-topic-form" type="submit" loading={submitting}>
            Create topic
          </Button>
        </>
      }
    >
      <form id="create-topic-form" onSubmit={handleSubmit} className="space-y-4" noValidate>
        {/* Name */}
        <div>
          <label htmlFor="topic-name" className="block text-xs font-medium text-text-secondary mb-1.5">
            Topic name <span className="text-signal-high">*</span>
          </label>
          <input
            id="topic-name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent"
            placeholder="e.g. China Sea territorial disputes"
          />
        </div>

        {/* Keywords */}
        <TagInput
          label="Keywords *"
          placeholder="e.g. South China Sea, PLA Navy…"
          tags={keywords}
          onChange={setKeywords}
        />

        {/* Languages */}
        <div>
          <p className="text-xs font-medium text-text-secondary mb-1.5">Monitor languages</p>
          <div className="flex flex-wrap gap-2">
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                type="button"
                onClick={() => toggleLang(l.code)}
                className={`px-3 py-1 rounded text-xs font-medium border transition-colors ${
                  languages.includes(l.code)
                    ? 'bg-anveshak-accent/20 text-anveshak-accent border-anveshak-accent/40'
                    : 'border-anveshak-border text-text-muted hover:border-anveshak-accent/40'
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>

        {/* Thresholds */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="signal-threshold" className="block text-xs font-medium text-text-secondary mb-1.5">
              Signal threshold (platforms)
            </label>
            <input
              id="signal-threshold"
              type="number"
              min={1}
              max={10}
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-anveshak-accent"
            />
            <p className="text-[10px] text-text-muted mt-1">Alert when cluster spans N independent platforms</p>
          </div>
          <div>
            <label htmlFor="cred-min" className="block text-xs font-medium text-text-secondary mb-1.5">
              Min. source credibility
            </label>
            <input
              id="cred-min"
              type="number"
              min={0}
              max={100}
              value={credMin}
              onChange={(e) => setCredMin(Number(e.target.value))}
              className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-anveshak-accent"
            />
          </div>
        </div>

        {/* CLIP categories */}
        <TagInput
          label="CLIP vision categories (optional)"
          placeholder="e.g. military aircraft, warship…"
          tags={clipCats}
          onChange={setClipCats}
        />

        {error && (
          <p role="alert" className="text-signal-high text-xs bg-signal-high/10 border border-signal-high/20 rounded px-3 py-2">
            {error}
          </p>
        )}
      </form>
    </Modal>
  )
}
