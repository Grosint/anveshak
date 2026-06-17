import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { identifiersApi, type IdentifierType } from '../../api/identifiers'
import { Spinner } from '../ui/Spinner'

const IDENTIFIER_TYPES: { value: IdentifierType; label: string }[] = [
  { value: 'PHONE_IN', label: 'Phone' },
  { value: 'UPI', label: 'UPI' },
  { value: 'EMAIL', label: 'Email' },
  { value: 'CRYPTO_BTC', label: 'BTC' },
  { value: 'CRYPTO_ETH', label: 'ETH' },
  { value: 'CRYPTO_TRC20', label: 'TRC-20' },
  { value: 'TELEGRAM_HANDLE', label: 'Telegram' },
  { value: 'INSTAGRAM_HANDLE', label: 'Instagram' },
  { value: 'URL_DOMAIN', label: 'URL' },
  { value: 'GSTIN', label: 'GSTIN' },
  { value: 'PAN', label: 'PAN' },
  { value: 'IFSC', label: 'IFSC' },
  { value: 'BANK_ACCOUNT', label: 'Bank A/C' },
  { value: 'SEBI_REG', label: 'SEBI' },
]

interface IdentifierSearchProps {
  open: boolean
  onClose: () => void
}

export default function IdentifierSearch({ open, onClose }: IdentifierSearchProps) {
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<IdentifierType | ''>('')
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  // Focus input when modal opens
  useEffect(() => {
    if (open) {
      setQuery('')
      setTypeFilter('')
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  // Escape to close
  useEffect(() => {
    if (!open) return
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  // Global Cmd+K shortcut
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        if (open) onClose()
        else {
          // Trigger parent to open — handled via the Layout state
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  const { data: results = [], isLoading } = useQuery({
    queryKey: ['identifiers-global-search', query, typeFilter],
    queryFn: () => identifiersApi.searchGlobal(query, typeFilter || undefined),
    enabled: open && query.length >= 2,
    staleTime: 15_000,
  })

  function handleRowClick(topicId: string) {
    onClose()
    navigate(`/topics/${topicId}/feed`)
  }

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-x-4 top-[10%] z-50 max-w-2xl mx-auto bg-[#0b1222] border border-anveshak-border rounded-xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-anveshak-border">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="w-4 h-4 text-text-muted shrink-0">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <h2 className="text-sm font-semibold text-text-primary">Search Identifiers</h2>
          <div className="ml-auto">
            <button
              onClick={onClose}
              className="text-text-muted hover:text-text-primary text-xs px-2 py-1 rounded hover:bg-anveshak-muted transition-colors"
              aria-label="Close"
            >
              Esc
            </button>
          </div>
        </div>

        {/* Search bar */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-anveshak-border">
          <input
            ref={inputRef}
            type="text"
            placeholder="Search identifier (phone, UPI, wallet, email...)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-muted focus:outline-none"
          />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as IdentifierType | '')}
            className="px-2 py-1 rounded bg-anveshak-muted border border-anveshak-border text-text-primary text-xs"
            role="combobox"
          >
            <option value="">All types</option>
            {IDENTIFIER_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        {/* Results */}
        <div className="max-h-[60vh] overflow-y-auto">
          {isLoading && (
            <div className="flex justify-center py-8">
              <Spinner size="sm" label="Searching..." />
            </div>
          )}

          {!isLoading && query.length >= 2 && results.length === 0 && (
            <div className="py-8 text-center text-text-muted text-sm">
              No identifiers found for "{query}"
            </div>
          )}

          {!isLoading && query.length < 2 && (
            <div className="py-8 text-center text-text-muted text-sm">
              Type at least 2 characters to search across all topics
            </div>
          )}

          {results.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-anveshak-border text-text-muted text-xs uppercase tracking-wide">
                  <th className="text-left py-2 px-4">Type</th>
                  <th className="text-left py-2 px-4">Value</th>
                  <th className="text-left py-2 px-4">Topic</th>
                  <th className="text-right py-2 px-4">Sources</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <tr
                    key={`${r.identifier_value}-${r.topic_id}-${i}`}
                    onClick={() => handleRowClick(r.topic_id)}
                    className="border-b border-anveshak-border/50 hover:bg-anveshak-accent/10 cursor-pointer transition-colors"
                  >
                    <td className="py-2 px-4">
                      <TypeBadge type={r.identifier_type} />
                    </td>
                    <td className="py-2 px-4 font-mono text-text-primary text-xs">
                      {r.identifier_value}
                    </td>
                    <td className="py-2 px-4 text-text-secondary text-xs truncate max-w-[200px]">
                      {r.topic_name}
                    </td>
                    <td className="py-2 px-4 text-right">
                      <span className={`font-bold ${r.source_count >= 3 ? 'text-signal-high' : 'text-text-primary'}`}>
                        {r.source_count}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer hint */}
        <div className="px-4 py-2 border-t border-anveshak-border flex items-center gap-4 text-[10px] text-text-muted">
          <span>Click a row to navigate to topic</span>
          <span className="ml-auto">Results scoped to your org</span>
        </div>
      </div>
    </>
  )
}


function TypeBadge({ type }: { type: string }) {
  const label = IDENTIFIER_TYPES.find((t) => t.value === type)?.label || type
  const colorMap: Record<string, string> = {
    PHONE_IN: 'bg-blue-500/20 text-blue-400',
    UPI: 'bg-green-500/20 text-green-400',
    EMAIL: 'bg-purple-500/20 text-purple-400',
    CRYPTO_BTC: 'bg-orange-500/20 text-orange-400',
    CRYPTO_ETH: 'bg-indigo-500/20 text-indigo-400',
    CRYPTO_TRC20: 'bg-red-500/20 text-red-400',
    TELEGRAM_HANDLE: 'bg-cyan-500/20 text-cyan-400',
    INSTAGRAM_HANDLE: 'bg-pink-500/20 text-pink-400',
  }
  const color = colorMap[type] || 'bg-gray-500/20 text-gray-400'
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${color}`}>
      {label}
    </span>
  )
}
