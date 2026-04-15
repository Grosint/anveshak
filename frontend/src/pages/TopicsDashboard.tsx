import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { topicsApi, Topic, CreateTopicPayload } from '../api/topics'
import { CreateTopicModal } from '../components/topics/CreateTopicModal'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { formatDistanceToNow } from 'date-fns'

function TopicCard({
  topic,
  onClick,
  onToggleStatus,
  isToggling,
}: {
  topic: Topic
  onClick: () => void
  onToggleStatus: (e: React.MouseEvent) => void
  isToggling: boolean
}) {
  const statusVariant = topic.status === 'active' ? 'success' : 'default'
  return (
    <article
      className="bg-anveshak-card border border-anveshak-border rounded-lg p-4 hover:border-anveshak-accent/50 hover:shadow-card-hover transition-all cursor-pointer group animate-fade-in"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      aria-label={`Open topic: ${topic.name}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-text-primary group-hover:text-anveshak-accent transition-colors truncate">
              {topic.name}
            </h3>
            <Badge variant={statusVariant}>{topic.status}</Badge>
            {(topic.signal_count ?? 0) > 0 && (
              <Badge variant="warning">{topic.signal_count} signals</Badge>
            )}
          </div>
          <p className="text-xs text-text-muted">
            {topic.content_count ?? 0} items
            {' · '}
            Threshold: {topic.signal_threshold} platforms
            {' · '}
            Min cred: {topic.credibility_min}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={onToggleStatus}
            disabled={isToggling}
            aria-label={topic.status === 'active' ? 'Pause topic' : 'Activate topic'}
            className="text-xs px-2 py-1 rounded border border-anveshak-border text-text-muted hover:border-anveshak-accent hover:text-text-primary transition-colors"
          >
            {topic.status === 'active' ? 'Pause' : 'Activate'}
          </button>
          <svg
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            className="w-4 h-4 text-text-muted group-hover:text-anveshak-accent transition-colors mt-0.5"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </div>

      <div className="flex items-center gap-3 mt-3 text-xs text-text-muted">
        <span>
          Created {formatDistanceToNow(new Date(topic.created_at), { addSuffix: true })}
        </span>
      </div>
    </article>
  )
}

export default function TopicsDashboard() {
  const [showModal, setShowModal] = useState(false)
  const qc = useQueryClient()
  const navigate = useNavigate()

  const { data: topics = [], isLoading } = useQuery({
    queryKey: ['topics'],
    queryFn: topicsApi.list,
  })

  const createTopic = useMutation({
    mutationFn: (payload: CreateTopicPayload) => topicsApi.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['topics'] }),
  })

  const toggleStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'active' | 'paused' }) =>
      topicsApi.updateStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['topics'] }),
  })

  async function handleCreate(payload: CreateTopicPayload) {
    await createTopic.mutateAsync(payload)
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Topics</h1>
          <p className="text-sm text-text-muted mt-0.5">Active intelligence monitoring topics</p>
        </div>
        <Button onClick={() => setShowModal(true)} aria-label="Create new topic">
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
            <path d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" />
          </svg>
          New topic
        </Button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex justify-center py-20"><Spinner label="Loading topics…" /></div>
        ) : topics.length === 0 ? (
          <EmptyState
            icon="🎯"
            title="No topics yet"
            description="Create a topic to start monitoring open-source intelligence."
            action={<Button onClick={() => setShowModal(true)}>Create your first topic</Button>}
          />
        ) : (
          <div className="max-w-2xl space-y-3">
            {topics.map((topic) => (
              <TopicCard
                key={topic.id}
                topic={topic}
                onClick={() => navigate(`/topics/${topic.id}/feed`)}
                onToggleStatus={(e) => {
                  e.stopPropagation()
                  toggleStatus.mutate({
                    id: topic.id,
                    status: topic.status === 'active' ? 'paused' : 'active',
                  })
                }}
                isToggling={toggleStatus.isPending}
              />
            ))}
          </div>
        )}
      </div>

      <CreateTopicModal
        open={showModal}
        onClose={() => setShowModal(false)}
        onSubmit={handleCreate}
      />
    </div>
  )
}
