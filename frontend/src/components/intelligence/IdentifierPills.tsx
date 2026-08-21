import type { IntelIdentifier } from '../../api/intelligence'

const TYPE_COLORS: Record<string, string> = {
  PHONE_IN: 'text-green-400', PHONE_INTL: 'text-teal-400', UPI: 'text-purple-400',
  TELEGRAM_HANDLE: 'text-blue-400', CRYPTO_BTC: 'text-amber-400', EMAIL: 'text-cyan-400',
  GSTIN: 'text-orange-400', SEBI_REG: 'text-pink-400', URL_DOMAIN: 'text-violet-400',
  INSTAGRAM_HANDLE: 'text-rose-400', FACEBOOK_HANDLE: 'text-blue-500', X_HANDLE: 'text-slate-400',
  PAN: 'text-text-muted', IFSC: 'text-text-muted', BANK_ACCOUNT: 'text-amber-500',
}

const TYPE_SHORT: Record<string, string> = {
  PHONE_IN: 'PH', PHONE_INTL: 'INTL', UPI: 'UPI', TELEGRAM_HANDLE: 'TG', CRYPTO_BTC: 'BTC',
  CRYPTO_ETH: 'ETH', EMAIL: 'EM', GSTIN: 'GST', URL_DOMAIN: 'URL',
  SEBI_REG: 'SEBI', INSTAGRAM_HANDLE: 'IG', FACEBOOK_HANDLE: 'FB', X_HANDLE: 'X',
  PAN: 'PAN', IFSC: 'IFSC', BANK_ACCOUNT: 'BA',
}

/** Max identifier rows shown inline */
const INLINE_LIMIT = 6

interface IdentifierPillsProps {
  identifiers: IntelIdentifier[]
  onSelect: (identifier: IntelIdentifier) => void
  onShowAll?: () => void
}

export function IdentifierPills({ identifiers, onSelect, onShowAll }: IdentifierPillsProps) {
  if (identifiers.length === 0) return null

  const inline = identifiers.slice(0, INLINE_LIMIT)

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[11px] font-bold text-text-muted uppercase tracking-widest">
          Key Identifiers
        </h2>
      </div>
      <div className="bg-anveshak-card border border-anveshak-border rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-anveshak-border/50 text-text-muted text-[9px] uppercase tracking-wider">
              <th className="text-left py-2 px-3">Type</th>
              <th className="text-left py-2 px-3">Value</th>
              <th className="text-right py-2 px-3">Sources</th>
              <th className="text-right py-2 px-3">Mentions</th>
            </tr>
          </thead>
          <tbody>
            {inline.map((id, i) => (
              <tr
                key={`${id.identifier_type}-${id.identifier_value}-${i}`}
                onClick={() => onSelect(id)}
                className="border-b border-anveshak-border/30 last:border-0 cursor-pointer hover:bg-anveshak-muted/30 transition-colors"
              >
                <td className="py-1.5 px-3">
                  <span className={`text-[9px] font-bold ${TYPE_COLORS[id.identifier_type] ?? 'text-text-muted'}`}>
                    {TYPE_SHORT[id.identifier_type] ?? id.identifier_type}
                  </span>
                </td>
                <td className="py-1.5 px-3 font-mono text-text-primary text-[11px] truncate max-w-[200px]">
                  {id.identifier_value}
                </td>
                <td className="py-1.5 px-3 text-right">
                  <span className={`font-bold ${id.source_count >= 3 ? 'text-signal-high' : 'text-text-primary'}`}>
                    {id.source_count}
                  </span>
                </td>
                <td className="py-1.5 px-3 text-right text-text-muted">{id.mention_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* View all button */}
      {(identifiers.length > INLINE_LIMIT || onShowAll) && (
        <div className="mt-3 text-center">
          <button
            onClick={onShowAll}
            className="text-[11px] text-anveshak-accent hover:underline"
          >
            View all {identifiers.length} identifiers →
          </button>
        </div>
      )}
    </section>
  )
}
