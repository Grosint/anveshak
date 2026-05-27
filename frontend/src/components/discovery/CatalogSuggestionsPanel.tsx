import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { catalogApi, CatalogEntry, ReliabilityTier, RecommendationRank } from '../../api/catalog'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Spinner } from '../ui/Spinner'
import { EmptyState } from '../ui/EmptyState'

const tierColors: Record<ReliabilityTier, string> = {
  S: 'text-cred-high font-bold',
  A: 'text-anveshak-accent font-semibold',
  B: 'text-text-primary',
  C: 'text-text-muted',
}

const rankBadge: Record<RecommendationRank, { label: string; variant: 'success' | 'accent' | 'default' | 'warning' } | null> = {
  most_recommended: { label: 'Most Recommended', variant: 'success' },
  proven: { label: 'Proven', variant: 'accent' },
  curated: null,
  low_performer: { label: 'Low Relevance', variant: 'warning' },
}

function CatalogCard({
  entry,
  onApprove,
  isApproving,
}: {
  entry: CatalogEntry
  onApprove: (id: string) => void
  isApproving: boolean
}) {
  const badge = rankBadge[entry.recommendation_rank]
  return (
    <div className="bg-anveshak-card border border-anveshak-border rounded-lg p-3 animate-fade-in">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-mono ${tierColors[entry.reliability_tier]}`}>
              [{entry.reliability_tier}]
            </span>
            <h4 className="text-sm font-medium text-text-primary truncate">{entry.name}</h4>
            <Badge variant="ghost">{entry.platform}</Badge>
            {badge && <Badge variant={badge.variant}>{badge.label}</Badge>}
          </div>
          <p className="text-xs text-text-muted mb-1">{entry.description}</p>
          <div className="flex flex-wrap gap-1">
            {entry.domain_tags.map(tag => (
              <span key={tag} className="text-xs bg-anveshak-muted px-1.5 py-0.5 rounded">
                {tag}
              </span>
            ))}
          </div>
          {entry.signal_contribution_count > 0 && (
            <p className="text-xs text-cred-high mt-1">
              Contributed to {entry.signal_contribution_count} signals across {entry.topics_approved_count} topics
            </p>
          )}
        </div>
        <Button
          size="sm"
          onClick={() => onApprove(entry.id)}
          disabled={isApproving}
        >
          {isApproving ? 'Adding...' : 'Add'}
        </Button>
      </div>
    </div>
  )
}

export function CatalogSuggestionsPanel({ topicId }: { topicId: string }) {
  const queryClient = useQueryClient()
  const [approvingId, setApprovingId] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['catalog-suggestions', topicId],
    queryFn: () => catalogApi.suggestions(topicId),
    staleTime: 60_000,
  })

  const approveMut = useMutation({
    mutationFn: (entryId: string) => catalogApi.approve(topicId, entryId),
    onMutate: (entryId) => setApprovingId(entryId),
    onSettled: () => {
      setApprovingId(null)
      queryClient.invalidateQueries({ queryKey: ['catalog-suggestions', topicId] })
      queryClient.invalidateQueries({ queryKey: ['sources'] })
    },
  })

  if (isLoading) return <Spinner />
  if (error) return <p className="text-signal-high text-sm">Failed to load suggestions</p>

  const suggestions = data?.suggestions ?? []

  if (suggestions.length === 0) {
    return <EmptyState title="No catalog suggestions match this topic's keywords" />
  }

  // Group by category
  const grouped = suggestions.reduce<Record<string, CatalogEntry[]>>((acc, entry) => {
    const cat = entry.category || 'other'
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(entry)
    return acc
  }, {})

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">
          Curated Sources ({suggestions.length})
        </h3>
      </div>
      {Object.entries(grouped).map(([category, entries]) => (
        <details key={category} open className="group">
          <summary className="cursor-pointer text-xs font-medium text-text-secondary uppercase tracking-wider mb-2">
            {category} ({entries.length})
          </summary>
          <div className="space-y-2 ml-2">
            {entries.map(entry => (
              <CatalogCard
                key={entry.id}
                entry={entry}
                onApprove={(id) => approveMut.mutate(id)}
                isApproving={approvingId === entry.id}
              />
            ))}
          </div>
        </details>
      ))}
    </div>
  )
}
