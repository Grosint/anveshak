import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { catalogApi, DiscoveredSource, DiscoveryMethod, DiscoveryStatus } from '../../api/catalog'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Spinner } from '../ui/Spinner'
import { EmptyState } from '../ui/EmptyState'

const methodLabels: Record<DiscoveryMethod, string> = {
  snowball: 'Cited by sources',
  forwarding: 'Telegram forwarding',
  entity_search: 'Entity match',
  llm_suggestion: 'AI suggestion',
}

const methodVariants: Record<DiscoveryMethod, 'accent' | 'success' | 'warning' | 'default'> = {
  snowball: 'accent',
  forwarding: 'success',
  entity_search: 'warning',
  llm_suggestion: 'default',
}

function DiscoveredCard({
  item,
  onApprove,
  onDismiss,
  isActioning,
}: {
  item: DiscoveredSource
  onApprove: (id: string) => void
  onDismiss: (id: string) => void
  isActioning: boolean
}) {
  const evidence = typeof item.evidence === 'string'
    ? JSON.parse(item.evidence)
    : item.evidence ?? {}

  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-3 animate-fade-in">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="text-sm font-medium text-text-primary truncate">
              {item.domain_or_handle}
            </h4>
            <Badge variant="ghost">{item.platform}</Badge>
            <Badge variant={methodVariants[item.discovery_method]}>
              {methodLabels[item.discovery_method]}
            </Badge>
          </div>
          <p className="text-xs text-text-muted">
            {item.citation_count > 1 && `Cited ${item.citation_count} times`}
            {item.confidence_score != null && ` · Confidence: ${(item.confidence_score * 100).toFixed(0)}%`}
          </p>
          {evidence.reasoning && (
            <p className="text-xs text-text-secondary mt-1 italic">{evidence.reasoning}</p>
          )}
          {evidence.channel_name && (
            <p className="text-xs text-text-secondary mt-1">
              Channel: {evidence.channel_name} ({evidence.forward_count} forwards)
            </p>
          )}
        </div>
        {item.status === 'pending' && (
          <div className="flex gap-1 shrink-0">
            <Button
              size="sm"
              onClick={() => onApprove(item.id)}
              disabled={isActioning}
            >
              Add
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onDismiss(item.id)}
              disabled={isActioning}
            >
              Dismiss
            </Button>
          </div>
        )}
        {item.status === 'approved' && <Badge variant="success">Added</Badge>}
        {item.status === 'dismissed' && <Badge variant="default">Dismissed</Badge>}
      </div>
    </div>
  )
}

export function DiscoveredSourcesPanel({ topicId }: { topicId: string }) {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<DiscoveryStatus | undefined>('pending')
  const [actioningId, setActioningId] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['discovered', topicId, statusFilter],
    queryFn: () => catalogApi.discovered(topicId, statusFilter),
    staleTime: 30_000,
  })

  const approveMut = useMutation({
    mutationFn: (id: string) => catalogApi.approveDiscovered(topicId, id),
    onMutate: (id) => setActioningId(id),
    onSettled: () => {
      setActioningId(null)
      queryClient.invalidateQueries({ queryKey: ['discovered', topicId] })
      queryClient.invalidateQueries({ queryKey: ['sources'] })
    },
  })

  const dismissMut = useMutation({
    mutationFn: (id: string) => catalogApi.dismissDiscovered(topicId, id),
    onMutate: (id) => setActioningId(id),
    onSettled: () => {
      setActioningId(null)
      queryClient.invalidateQueries({ queryKey: ['discovered', topicId] })
    },
  })

  if (isLoading) return <Spinner />
  if (error) return <p className="text-signal-high text-sm">Failed to load discovered sources</p>

  const items = data?.discovered ?? []

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">
          Discovered Sources ({data?.total ?? 0})
        </h3>
        <div className="flex gap-1">
          {(['pending', 'approved', 'dismissed', undefined] as const).map(status => (
            <button
              key={status ?? 'all'}
              className={`text-xs px-2 py-1 rounded ${
                statusFilter === status
                  ? 'bg-anveshak-accent text-white'
                  : 'bg-anveshak-muted text-text-secondary hover:text-text-primary'
              }`}
              onClick={() => setStatusFilter(status)}
            >
              {status ?? 'All'}
            </button>
          ))}
        </div>
      </div>

      {items.length === 0 ? (
        <EmptyState title="No discovered sources yet. Sources will appear as content is scraped and analysed." />
      ) : (
        <div className="space-y-2">
          {items.map(item => (
            <DiscoveredCard
              key={item.id}
              item={item}
              onApprove={(id) => approveMut.mutate(id)}
              onDismiss={(id) => dismissMut.mutate(id)}
              isActioning={actioningId === item.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}
