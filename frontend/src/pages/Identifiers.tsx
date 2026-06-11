import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { identifiersApi, type IdentifierType, type TopIdentifier, type IdentifierCluster, type ClusterDetail } from '../api/identifiers'
import { Spinner } from '../components/ui/Spinner'
import ExportButton from '../components/ui/ExportButton'
import { format } from 'date-fns'

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
      <div className="flex items-center gap-3 mb-4 flex-wrap">
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

function formatDate(iso: string | null): string {
  if (!iso) return '-'
  try { return format(new Date(iso), 'dd MMM yy HH:mm') }
  catch { return iso }
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
              key={`${item.entity_type}-${item.entity_text}-${i}`}
              className="border-b border-anveshak-border/50 hover:bg-anveshak-muted/50 transition-colors"
            >
              <td className="py-2 px-3"><TypeBadge type={item.entity_type} /></td>
              <td className="py-2 px-3 font-mono text-text-primary text-xs">{item.entity_text}</td>
              <td className="py-2 px-3 text-right">
                <span className={`font-bold ${item.source_count >= 3 ? 'text-signal-high' : 'text-text-primary'}`}>
                  {item.source_count}
                </span>
              </td>
              <td className="py-2 px-3 text-right text-text-secondary">{item.content_item_count}</td>
              <td className="py-2 px-3 text-text-muted text-xs">{formatDate(item.first_seen)}</td>
              <td className="py-2 px-3 text-text-muted text-xs">{formatDate(item.last_seen)}</td>
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
    <div className="mb-4 bg-anveshak-card border border-anveshak-accent/50 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-text-primary">Cluster Detail</h3>
        <button
          onClick={onClose}
          className="text-text-muted hover:text-text-primary text-xs"
        >
          Close
        </button>
      </div>
      {loading && <Spinner />}
      {detail && (
        <>
          <div className="flex items-center gap-3 mb-3">
            <TypeBadge type={detail.identifier_type} />
            <span className="font-mono text-sm text-text-primary">{detail.identifier_value}</span>
            <span className="text-xs text-text-muted">{detail.source_count} sources, {detail.content_item_count} items</span>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {detail.items.map((item) => (
              <div
                key={item.content_item_id}
                className="bg-anveshak-muted rounded p-2 text-xs"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-text-muted">{item.platform}</span>
                  <span className="text-text-muted">{item.source_name}</span>
                  <span className="text-text-muted ml-auto">{formatDate(item.captured_at)}</span>
                </div>
                <p className="text-text-secondary line-clamp-2">{item.clean_text}</p>
                {item.url && (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-anveshak-accent hover:underline mt-1 inline-block"
                  >
                    Source link
                  </a>
                )}
              </div>
            ))}
          </div>
        </>
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
