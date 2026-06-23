import { useQuery } from '@tanstack/react-query'
import { identifiersApi, TopIdentifier } from '../../api/identifiers'

const TYPE_COLORS: Record<string, string> = {
  PHONE_IN: 'text-green-400',
  PHONE_INTL: 'text-teal-400',
  UPI: 'text-purple-400',
  TELEGRAM_HANDLE: 'text-blue-400',
  CRYPTO_BTC: 'text-amber-400',
  EMAIL: 'text-cyan-400',
  GSTIN: 'text-orange-400',
  SEBI_REG: 'text-pink-400',
}

const TYPE_SHORT: Record<string, string> = {
  PHONE_IN: 'PH', PHONE_INTL: 'INTL', UPI: 'UPI', TELEGRAM_HANDLE: 'TG', CRYPTO_BTC: 'BTC',
  CRYPTO_ETH: 'ETH', EMAIL: 'EM', GSTIN: 'GST', URL_DOMAIN: 'URL',
  SEBI_REG: 'SEBI', INSTAGRAM_HANDLE: 'IG', PAN: 'PAN', IFSC: 'IFSC',
  BANK_ACCOUNT: 'BA',
}

interface TopIdentifiersProps {
  topicId: string
  onSelectIdentifier: (id: TopIdentifier) => void
  onViewAll: () => void
}

export function TopIdentifiers({ topicId, onSelectIdentifier, onViewAll }: TopIdentifiersProps) {
  const { data: identifiers = [], isLoading } = useQuery({
    queryKey: ['identifiers-top', topicId, 5],
    queryFn: () => identifiersApi.top(topicId, undefined, 5),
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest">
          Top Identifiers
        </h3>
        {identifiers.length > 0 && (
          <button
            onClick={onViewAll}
            className="text-[9px] text-anveshak-accent hover:underline"
          >
            View all
          </button>
        )}
      </div>

      {isLoading ? (
        <p className="text-[11px] text-text-muted">Loading...</p>
      ) : identifiers.length === 0 ? (
        <p className="text-[11px] text-text-muted">No identifiers found</p>
      ) : (
        <div className="space-y-1">
          {identifiers.map((id, i) => (
            <button
              key={`${id.identifier_type}-${id.identifier_value}-${i}`}
              onClick={() => onSelectIdentifier(id)}
              className="w-full text-left flex items-center gap-2 px-2 py-1.5 rounded hover:bg-anveshak-muted/50 transition-colors"
            >
              <span className={`text-[9px] font-bold ${TYPE_COLORS[id.identifier_type] ?? 'text-text-muted'}`}>
                {TYPE_SHORT[id.identifier_type] ?? id.identifier_type}
              </span>
              <span className="text-[11px] text-text-primary font-mono truncate flex-1">
                {id.identifier_value}
              </span>
              <span className={`text-[10px] font-bold ${id.source_count >= 3 ? 'text-signal-high' : 'text-text-muted'}`}>
                {id.source_count}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
