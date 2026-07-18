import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { identifiersApi, type IdentifierType, type TopIdentifier, type IdentifierCluster, type ClusterDetail } from '../api/identifiers'
import { Spinner } from '../components/ui/Spinner'
import ExportButton from '../components/ui/ExportButton'
import { format } from 'date-fns'

const IDENTIFIER_TYPES: { value: IdentifierType; label: string }[] = [
  { value: 'PHONE_IN', label: 'Phone' },
  { value: 'PHONE_INTL', label: 'Phone (Intl)' },
  { value: 'UPI', label: 'UPI' },
  { value: 'EMAIL', label: 'Email' },
  { value: 'CRYPTO_BTC', label: 'BTC' },
  { value: 'CRYPTO_ETH', label: 'ETH' },
  { value: 'CRYPTO_TRC20', label: 'TRC-20' },
  { value: 'TELEGRAM_HANDLE', label: 'Telegram' },
  { value: 'INSTAGRAM_HANDLE', label: 'Instagram' },
  { value: 'FACEBOOK_HANDLE', label: 'Facebook' },
  { value: 'X_HANDLE', label: 'X/Twitter' },
  { value: 'URL_DOMAIN', label: 'URL' },
  { value: 'GSTIN', label: 'GSTIN' },
  { value: 'PAN', label: 'PAN' },
  { value: 'IFSC', label: 'IFSC' },
  { value: 'BANK_ACCOUNT', label: 'Bank A/C' },
  { value: 'SEBI_REG', label: 'SEBI' },
  { value: 'AIRCRAFT_ID', label: 'Aircraft ID' },
]

type ViewMode = 'top' | 'clusters' | 'search'

interface IdentifiersProps {
  embedded?: boolean
  topicId?: string
}

export default function Identifiers({ embedded = false, topicId: propTopicId }: IdentifiersProps) {
  const [topicId, setTopicId] = useState(propTopicId || '')
  const [view, setView] = useState<ViewMode>('top')
  const [typeFilter, setTypeFilter] = useState<IdentifierType | ''>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(null)

  const activeTopicId = propTopicId || topicId

  // Top identifiers
  const { data: topIdentifiers = [], isLoading: topLoading } = useQuery({
    queryKey: ['identifiers-top', activeTopicId, typeFilter],
    queryFn: () => identifiersApi.top(activeTopicId, typeFilter || undefined),
    enabled: !!activeTopicId && view === 'top',
    staleTime: 30_000,
  })

  // Clusters
  const { data: clusters = [], isLoading: clustersLoading } = useQuery({
    queryKey: ['identifiers-clusters', activeTopicId, typeFilter],
    queryFn: () => identifiersApi.clusters(activeTopicId, typeFilter || undefined),
    enabled: !!activeTopicId && view === 'clusters',
    staleTime: 30_000,
  })

  // Search
  const { data: searchResults = [], isLoading: searchLoading } = useQuery({
    queryKey: ['identifiers-search', activeTopicId, searchQuery, typeFilter],
    queryFn: () => identifiersApi.search(activeTopicId, searchQuery, typeFilter || undefined),
    enabled: !!activeTopicId && view === 'search' && searchQuery.length >= 2,
    staleTime: 30_000,
  })

  // Cluster detail
  const { data: clusterDetail, isLoading: detailLoading } = useQuery({
    queryKey: ['identifiers-cluster-detail', selectedClusterId, activeTopicId],
    queryFn: () => identifiersApi.clusterDetail(selectedClusterId!, activeTopicId),
    enabled: !!selectedClusterId && !!activeTopicId,
    staleTime: 30_000,
  })

  const isLoading = topLoading || clustersLoading || searchLoading

  return (
    <div className={embedded ? '' : 'p-6 max-w-7xl mx-auto'}>
      {!embedded && (
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold text-text-primary">Identifiers</h1>
          {activeTopicId && (
            <ExportButton
              endpoint="/api/v1/identifiers/export"
              params={{ topic_id: activeTopicId }}
              label="Export CSV"
            />
          )}
        </div>
      )}

      {/* Topic ID input (only when not embedded) */}
      {!propTopicId && (
        <div className="mb-4">
          <input
            type="text"
            placeholder="Enter topic ID..."
            value={topicId}
            onChange={(e) => setTopicId(e.target.value)}
            className="w-64 px-3 py-1.5 rounded bg-anveshak-muted border border-anveshak-border text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent"
          />
        </div>
      )}

      {/* View tabs + type filter */}
      <div className="flex items-center gap-3 mb-4 flex-wrap px-1 pt-1">
        <div className="flex bg-anveshak-muted rounded p-0.5 gap-0.5">
          {(['top', 'clusters', 'search'] as ViewMode[]).map((v) => (
            <button
              key={v}
              onClick={() => { setView(v); setSelectedClusterId(null) }}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                view === v
                  ? 'bg-anveshak-accent text-white'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {v === 'top' ? 'Top' : v === 'clusters' ? 'Clusters' : 'Search'}
            </button>
          ))}
        </div>

        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as IdentifierType | '')}
          className="px-2 py-1 rounded bg-anveshak-muted border border-anveshak-border text-text-primary text-xs"
        >
          <option value="">All types</option>
          {IDENTIFIER_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>

        {view === 'search' && (
          <input
            type="text"
            placeholder="Search identifier..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="px-3 py-1 rounded bg-anveshak-muted border border-anveshak-border text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent w-64"
          />
        )}
      </div>

      {!activeTopicId && (
        <p className="text-text-muted text-sm">Select a topic to view identifiers.</p>
      )}

      {isLoading && <Spinner />}

      {/* Cluster detail overlay */}
      {selectedClusterId && (
        <ClusterDetailPanel
          detail={clusterDetail}
          loading={detailLoading}
          onClose={() => setSelectedClusterId(null)}
        />
      )}

      {/* Top identifiers table */}
      {view === 'top' && !isLoading && activeTopicId && (
        <TopIdentifiersTable items={topIdentifiers} />
      )}

      {/* Clusters grid */}
      {view === 'clusters' && !isLoading && activeTopicId && (
        <ClustersGrid
          clusters={clusters}
          onSelect={(id) => setSelectedClusterId(id)}
        />
      )}

      {/* Search results */}
      {view === 'search' && !isLoading && activeTopicId && searchQuery.length >= 2 && (
        <SearchResultsTable items={searchResults} />
      )}
    </div>
  )
}


// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TypeBadge({ type }: { type: string }) {
  const label = IDENTIFIER_TYPES.find((t) => t.value === type)?.label || type
  const colorMap: Record<string, string> = {
    PHONE_IN: 'bg-blue-500/20 text-blue-400',
    PHONE_INTL: 'bg-teal-500/20 text-teal-400',
    UPI: 'bg-green-500/20 text-green-400',
    EMAIL: 'bg-purple-500/20 text-purple-400',
    CRYPTO_BTC: 'bg-orange-500/20 text-orange-400',
    CRYPTO_ETH: 'bg-indigo-500/20 text-indigo-400',
    CRYPTO_TRC20: 'bg-red-500/20 text-red-400',
    TELEGRAM_HANDLE: 'bg-cyan-500/20 text-cyan-400',
    INSTAGRAM_HANDLE: 'bg-pink-500/20 text-pink-400',
    FACEBOOK_HANDLE: 'bg-blue-600/20 text-blue-400',
    X_HANDLE: 'bg-slate-500/20 text-slate-400',
  }
  const color = colorMap[type] || 'bg-gray-500/20 text-gray-400'
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${color}`}>
      {label}
    </span>
  )
}

function formatDate(iso: string | null): string {
  if (!iso) return '-'
  try { return format(new Date(iso), 'dd MMM yy HH:mm') }
  catch { return iso }
}

const PHONE_COUNTRY: Record<string, string> = {
  '+86': 'China', '+852': 'Hong Kong', '+971': 'UAE',
  '+92': 'Pakistan', '+977': 'Nepal', '+880': 'Bangladesh', '+95': 'Myanmar',
  '+91': 'India',
}

function getPhoneCountry(value: string): string | null {
  for (const [prefix, name] of Object.entries(PHONE_COUNTRY)) {
    if (value.startsWith(prefix)) return name
  }
  return null
}

function formatIdentifierValue(item: TopIdentifier): string {
  if (item.identifier_type === 'TELEGRAM_HANDLE' || item.identifier_type === 'INSTAGRAM_HANDLE') {
    return `@${item.identifier_value}`
  }
  return item.identifier_value
}

function IdentifierContext({ type, value }: { type: string; value: string }) {
  let label = ''
  let color = 'text-text-muted'

  if (type === 'PHONE_INTL') {
    const country = getPhoneCountry(value)
    if (country) { label = country; color = 'text-teal-400/70' }
  } else if (type === 'PHONE_IN') {
    label = 'India'
    color = 'text-blue-400/70'
  }

  if (!label) return null
  return <span className={`ml-2 text-[10px] ${color}`}>{label}</span>
}

function TopIdentifiersTable({ items }: { items: TopIdentifier[] }) {
  if (items.length === 0) {
    return <p className="text-text-muted text-sm">No identifiers found.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-anveshak-border text-text-muted text-xs uppercase tracking-wide">
            <th className="text-left py-2 px-3">Type</th>
            <th className="text-left py-2 px-3">Value</th>
            <th className="text-right py-2 px-3">Sources</th>
            <th className="text-right py-2 px-3">Items</th>
            <th className="text-left py-2 px-3">First Seen</th>
            <th className="text-left py-2 px-3">Last Seen</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr
              key={`${item.identifier_type}-${item.identifier_value}-${i}`}
              className="border-b border-anveshak-border/50 hover:bg-anveshak-muted/50 transition-colors"
            >
              <td className="py-2 px-3"><TypeBadge type={item.identifier_type} /></td>
              <td className="py-2 px-3">
                <span className="font-mono text-text-primary text-xs">{formatIdentifierValue(item)}</span>
                <IdentifierContext type={item.identifier_type} value={item.identifier_value} />
              </td>
              <td className="py-2 px-3 text-right">
                <span className={`font-bold ${item.source_count >= 3 ? 'text-signal-high' : item.source_count >= 2 ? 'text-green-400' : 'text-text-primary'}`}>
                  {item.source_count}
                </span>
                {item.source_count >= 2 && (
                  <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">Multi</span>
                )}
                {item.source_count === 1 && item.content_item_count >= 2 && (
                  <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400">Repeated</span>
                )}
              </td>
              <td className="py-2 px-3 text-right text-text-secondary">{item.content_item_count}</td>
              <td className="py-2 px-3 text-text-muted text-xs">{formatDate(item.first_seen_at)}</td>
              <td className="py-2 px-3 text-text-muted text-xs">{formatDate(item.last_seen_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ClustersGrid({ clusters, onSelect }: { clusters: IdentifierCluster[]; onSelect: (id: string) => void }) {
  if (clusters.length === 0) {
    return <p className="text-text-muted text-sm">No identifier clusters found.</p>
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
      {clusters.map((c) => (
        <button
          key={c.id}
          onClick={() => onSelect(c.id)}
          className="text-left bg-anveshak-card border border-anveshak-border rounded-lg p-4 hover:border-anveshak-accent transition-colors"
        >
          <div className="flex items-center justify-between mb-2">
            <TypeBadge type={c.identifier_type} />
            <span className={`text-xs font-bold ${
              c.source_count >= 5 ? 'text-signal-high' : c.source_count >= 3 ? 'text-yellow-400' : 'text-text-muted'
            }`}>
              {c.source_count} sources
            </span>
          </div>
          <p className="font-mono text-sm text-text-primary truncate">{c.identifier_value}</p>
          <div className="flex items-center gap-3 mt-2 text-xs text-text-muted">
            <span>{c.content_item_count} items</span>
            {c.first_seen_at && <span>since {formatDate(c.first_seen_at)}</span>}
          </div>
        </button>
      ))}
    </div>
  )
}

const PLATFORM_COLORS: Record<string, { dot: string; badge: string }> = {
  telegram: { dot: 'bg-cyan-400', badge: 'bg-cyan-500/20 text-cyan-400' },
  rss: { dot: 'bg-blue-400', badge: 'bg-blue-500/20 text-blue-400' },
  web: { dot: 'bg-emerald-400', badge: 'bg-emerald-500/20 text-emerald-400' },
  reddit: { dot: 'bg-orange-400', badge: 'bg-orange-500/20 text-orange-400' },
  instagram: { dot: 'bg-pink-400', badge: 'bg-pink-500/20 text-pink-400' },
  youtube: { dot: 'bg-red-400', badge: 'bg-red-500/20 text-red-400' },
  darkweb: { dot: 'bg-purple-400', badge: 'bg-purple-500/20 text-purple-400' },
}

function ClusterDetailPanel({
  detail,
  loading,
  onClose,
}: {
  detail: ClusterDetail | undefined
  loading: boolean
  onClose: () => void
}) {
  return (
    <div className="mb-4 bg-anveshak-card border border-anveshak-accent/30 rounded-lg p-5">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-sm font-bold text-text-primary mb-2">Identifier Timeline</h3>
          {detail && (
            <div className="flex items-center gap-3 flex-wrap">
              <TypeBadge type={detail.identifier_type} />
              <span className="font-mono text-base font-bold text-text-primary">{detail.identifier_value}</span>
              <span className="text-xs text-text-muted">
                {detail.source_count} sources &middot; {detail.content_item_count} sightings
              </span>
              {detail.first_seen_at && detail.last_seen_at && (
                <span className="text-[10px] text-text-muted">
                  {formatDate(detail.first_seen_at)} &rarr; {formatDate(detail.last_seen_at)}
                </span>
              )}
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-text-muted hover:text-text-primary text-xs px-2 py-1 rounded hover:bg-white/[0.05] transition-colors"
        >
          Close
        </button>
      </div>

      {loading && <Spinner />}

      {/* Vertical timeline */}
      {detail && (
        <div className="relative pl-6 max-h-[400px] overflow-y-auto">
          {/* Vertical line */}
          <div className="absolute left-[9px] top-2 bottom-2 w-px bg-anveshak-border/60" />

          <div className="space-y-1">
            {detail.items.map((item, i) => {
              const colors = PLATFORM_COLORS[item.platform] || { dot: 'bg-gray-400', badge: 'bg-gray-500/20 text-gray-400' }
              const isFirst = i === 0
              const isLast = i === detail.items.length - 1
              return (
                <div key={item.content_item_id} className="relative group">
                  {/* Timeline dot */}
                  <div className={`absolute -left-6 top-3 w-[11px] h-[11px] rounded-full border-2 border-anveshak-bg ${colors.dot} ${
                    isFirst || isLast ? 'ring-2 ring-offset-1 ring-offset-anveshak-bg ring-current opacity-100' : ''
                  }`} />

                  {/* Content card */}
                  <div className={`rounded-lg p-3 transition-colors ${
                    isFirst ? 'bg-anveshak-accent/[0.06] border border-anveshak-accent/20' : 'bg-white/[0.02] border border-transparent hover:border-anveshak-border/30 hover:bg-white/[0.04]'
                  }`}>
                    {/* Top row: platform + source + date */}
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider ${colors.badge}`}>
                        {item.platform}
                      </span>
                      <span className="text-xs font-medium text-text-primary">{item.source_name}</span>
                      <span className="text-[10px] text-text-muted ml-auto whitespace-nowrap">
                        {formatDate(item.captured_at)}
                      </span>
                    </div>

                    {/* Content snippet */}
                    <p className="text-xs text-text-secondary leading-relaxed line-clamp-2">
                      {item.clean_text}
                    </p>

                    {/* Source link */}
                    {item.url && (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[10px] text-anveshak-accent/70 hover:text-anveshak-accent hover:underline mt-1 inline-block"
                      >
                        {item.url.replace(/^https?:\/\//, '').slice(0, 50)}{item.url.length > 60 ? '...' : ''} &rarr;
                      </a>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function SearchResultsTable({ items }: { items: { entity_type: string; entity_text: string; confidence: number; content_url: string | null; source_name: string; source_platform: string; captured_at: string }[] }) {
  if (items.length === 0) {
    return <p className="text-text-muted text-sm">No results found.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-anveshak-border text-text-muted text-xs uppercase tracking-wide">
            <th className="text-left py-2 px-3">Type</th>
            <th className="text-left py-2 px-3">Value</th>
            <th className="text-right py-2 px-3">Confidence</th>
            <th className="text-left py-2 px-3">Source</th>
            <th className="text-left py-2 px-3">Platform</th>
            <th className="text-left py-2 px-3">Captured</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr
              key={`${item.entity_text}-${i}`}
              className="border-b border-anveshak-border/50 hover:bg-anveshak-muted/50 transition-colors"
            >
              <td className="py-2 px-3"><TypeBadge type={item.entity_type} /></td>
              <td className="py-2 px-3 font-mono text-text-primary text-xs">{item.entity_text}</td>
              <td className="py-2 px-3 text-right text-text-secondary">{(item.confidence * 100).toFixed(0)}%</td>
              <td className="py-2 px-3 text-text-secondary">{item.source_name}</td>
              <td className="py-2 px-3 text-text-muted">{item.source_platform}</td>
              <td className="py-2 px-3 text-text-muted text-xs">{formatDate(item.captured_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
