import { useRef, useState, DragEvent } from 'react'

interface DropZoneProps {
  onFile: (file: File) => void
  accept?: string
  disabled?: boolean
}

export function DropZone({ onFile, accept = 'image/*,video/*', disabled }: DropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function handleDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    if (disabled) return
    const file = e.dataTransfer.files[0]
    if (file) onFile(file)
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) onFile(file)
    e.target.value = '' // reset so same file can be re-selected
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Drop zone for image or video upload"
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => e.key === 'Enter' && !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`
        border-2 border-dashed rounded-lg p-10 text-center transition-colors cursor-pointer
        ${dragging ? 'border-anveshak-accent bg-anveshak-accent/10' : 'border-anveshak-border hover:border-anveshak-accent/50'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={handleChange}
        aria-hidden="true"
      />
      <div className="flex flex-col items-center gap-3">
        <svg viewBox="0 0 48 48" fill="none" className="w-12 h-12 text-text-muted" aria-hidden="true">
          <path d="M28 8H20a2 2 0 00-2 2v20a2 2 0 002 2h8a2 2 0 002-2V10a2 2 0 00-2-2z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
          <path d="M6 32v4a4 4 0 004 4h28a4 4 0 004-4v-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          <path d="M24 28V16m0 0l-4 4m4-4l4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <div>
          <p className="text-sm font-medium text-text-primary">
            {dragging ? 'Drop file here' : 'Drag & drop or click to upload'}
          </p>
          <p className="text-xs text-text-muted mt-1">
            Supports JPEG, PNG, WebP, MP4, MOV
          </p>
        </div>
      </div>
    </div>
  )
}
