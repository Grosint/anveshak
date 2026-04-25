import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { topicsApi, TopicSource } from '../../api/topics'
import { sourcesApi, Source } from '../../api/sources'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'

interface ManageSourcesModalProps {
  open: boolean
  onClose: () => void
  topicId: string
  topicName: string
}

const HEALTH_VARIANT: Record<string, 'success' | 'warning' | 'danger' | 'default'> = {
  healthy: 'success',
  degraded: 'warning',
  down: 'danger',
  unverified: 'default',
}

function credColor(score: number) {
  if (score >= 70) return 'text-cred-high'
  if (score >= 40) return 'text-signal-med'
  return 'text-signal-high'
}

export function ManageSourcesModal({ open, onClose, topicId, topicName }: ManageSourcesModalProps) {
  const [search, setSearch] = useState('')
  const qc = useQueryClient()

  const { data: linkedSources = [], isLoading: loadingLinked } = useQuery({
    queryKey: ['topic-sources', topicId],
    queryFn: () => topicsApi.listSources(topicId),
    enabled: open,
  })

  const { data: allSources = [], isLoading: loadingAll } = useQuery({
    queryKey: ['sources'],
    queryFn: sourcesApi.list,
    enabled: open,
  })

  const linkedIds = useMemo(
    () => new Set(linkedSources.map((s) => s.id)),
    [linkedSources],
  )

  const unlinkedSources = useMemo(() => {
    const q = search.toLowerCase()
    return allSources
      .filter((s) => !linkedIds.has(s.id))
      .filter(
        (s) =>
          !q ||
          s.name.toLowerCase().includes(q) ||
          s.url_or_handle.toLowerCase().includes(q) ||
          s.platform.toLowerCase().includes(q),
      )
  }, [allSources, linkedIds, search])

  const linkSource = useMutation({
    mutationFn: (sourceId: string) => topicsApi.linkSource(topicId, sourceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topic-sources', topicId] })
      qc.invalidateQueries({ queryKey: ['sources'] })
    },
  })

  const unlinkSource = useMutation({
    mutationFn: (sourceId: string) => topicsApi.unlinkSource(topicId, sourceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topic-sources', topicId] })
      qc.invalidateQueries({ queryKey: ['sources'] })
    },
  })

  const isLoading = loadingLinked || loadingAll

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Sources — ${topicName}`}
      maxWidth="max-w-2xl"
      footer={
        <Button variant="ghost" onClick={onClose}>
          Done
        </Button>
      }
    >
      {isLoading ? (
        <div className="flex justify-center py-10">
          <Spinner label="Loading sources..." />
        </div>
      ) : (
        <div className="space-y-5">
          {/* Linked sources */}
          <div>
            <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
              Linked sources ({linkedSources.length})
            </h3>
            {linkedSources.length === 0 ? (
              <p className="text-xs text-text-muted py-3">
                No sources linked. Add sources below to start monitoring.
              </p>
            ) : (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {linkedSources.map((src) => (
                  <LinkedSourceRow
                    key={src.id}
                    source={src}
                    onUnlink={() => unlinkSource.mutate(src.id)}
                    isUnlinking={unlinkSource.isPending}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Divider */}
          <div className="border-t border-anveshak-border" />

          {/* Available sources */}
          <div>
            <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
              Available sources ({unlinkedSources.length})
            </h3>
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter by name, URL, or platform..."
              className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-anveshak-accent mb-2"
              aria-label="Filter available sources"
            />
            {unlinkedSources.length === 0 ? (
              <p className="text-xs text-text-muted py-3">
                {allSources.length === linkedSources.length
                  ? 'All sources are already linked to this topic.'
                  : 'No matching sources found.'}
              </p>
            ) : (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {unlinkedSources.map((src) => (
                  <UnlinkedSourceRow
                    key={src.id}
                    source={src}
                    onLink={() => linkSource.mutate(src.id)}
                    isLinking={linkSource.isPending}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}

function LinkedSourceRow({
  source,
  onUnlink,
  isUnlinking,
}: {
  source: TopicSource
  onUnlink: () => void
  isUnlinking: boolean
}) {
  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded border border-anveshak-border bg-anveshak-bg group hover:border-anveshak-accent/30 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary truncate">
            {source.name}
          </span>
          <Badge variant={HEALTH_VARIANT[source.health_status] ?? 'default'}>
            {source.platform}
          </Badge>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[11px] text-text-muted truncate font-mono">
            {source.url_or_handle}
          </span>
          <span className={`text-[11px] font-semibold ${credColor(source.credibility_score)}`}>
            {Math.round(source.credibility_score)}
          </span>
          <span className="text-[11px] text-text-muted">
            {source.item_count} item{source.item_count !== 1 ? 's' : ''}
          </span>
        </div>
      </div>
      <button
        type="button"
        onClick={onUnlink}
        disabled={isUnlinking}
        className="text-xs px-2 py-1 rounded border border-signal-high/30 text-signal-high hover:bg-signal-high/10 transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100 shrink-0"
        aria-label={`Unlink ${source.name}`}
      >
        Unlink
      </button>
    </div>
  )
}

function UnlinkedSourceRow({
  source,
  onLink,
  isLinking,
}: {
  source: Source
  onLink: () => void
  isLinking: boolean
}) {
  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded border border-anveshak-border bg-anveshak-bg group hover:border-anveshak-accent/30 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary truncate">
            {source.name}
          </span>
          <Badge variant={HEALTH_VARIANT[source.health_status] ?? 'default'}>
            {source.platform}
          </Badge>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[11px] text-text-muted truncate font-mono">
            {source.url_or_handle}
          </span>
          <span className={`text-[11px] font-semibold ${credColor(source.credibility_score)}`}>
            {Math.round(source.credibility_score)}
          </span>
        </div>
      </div>
      <button
        type="button"
        onClick={onLink}
        disabled={isLinking}
        className="text-xs px-2 py-1 rounded border border-anveshak-accent/30 text-anveshak-accent hover:bg-anveshak-accent/10 transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100 shrink-0"
        aria-label={`Link ${source.name}`}
      >
        + Link
      </button>
    </div>
  )
}
