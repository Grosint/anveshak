import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { topicsApi, Topic, CreateTopicPayload } from '../api/topics'
import { CreateTopicModal } from '../components/topics/CreateTopicModal'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { SignalBadge, NewContentBadge, SourceHealthDot } from '../components/ui/UrgencyBadge'
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
  const signalCount = topic.signal_count ?? 0
  const newContent = topic.new_content_24h ?? 0
  const healthStatus = topic.worst_source_health ?? 'healthy'
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
            <SignalBadge count={signalCount} />
            <NewContentBadge count={newContent} />
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
          <SourceHealthDot status={healthStatus} />
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
          {topic.last_activity
            ? `Last activity ${formatDistanceToNow(new Date(topic.last_activity), { addSuffix: true })}`
            : `Created ${formatDistanceToNow(new Date(topic.created_at), { addSuffix: true })}`}
        </span>
      </div>
    </article>
  )
}

type StatusFilter = 'all' | 'active' | 'paused'
type SortBy = 'urgency' | 'newest' | 'oldest' | 'most_content' | 'most_signals'

export default function TopicsDashboard() {
  const [showModal, setShowModal] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('active')
  const [sortBy, setSortBy] = useState<SortBy>('urgency')
  const qc = useQueryClient()
  const navigate = useNavigate()

  const { data: topics = [], isLoading } = useQuery({
    queryKey: ['topics'],
    queryFn: topicsApi.list,
  })

  const activeCount = topics.filter((t) => t.status === 'active').length
  const pausedCount = topics.filter((t) => t.status === 'paused').length

  const filteredTopics = useMemo(() => {
    let list = [...topics]

    if (search) {
      const q = search.toLowerCase()
      list = list.filter((t) => t.name.toLowerCase().includes(q))
    }

    if (statusFilter !== 'all') {
      list = list.filter((t) => t.status === statusFilter)
    }

    list.sort((a, b) => {
      switch (sortBy) {
        case 'urgency': {
          const aSig = a.signal_count ?? 0
          const bSig = b.signal_count ?? 0
          if (aSig !== bSig) return bSig - aSig
          const aTime = a.last_activity ? new Date(a.last_activity).getTime() : 0
          const bTime = b.last_activity ? new Date(b.last_activity).getTime() : 0
          return bTime - aTime
        }
        case 'oldest':
          return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        case 'most_content':
          return (b.content_count ?? 0) - (a.content_count ?? 0)
        case 'most_signals':
          return (b.signal_count ?? 0) - (a.signal_count ?? 0)
        case 'newest':
        default:
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      }
    })

    return list
  }, [topics, search, statusFilter, sortBy])

  const isFiltered = search || statusFilter !== 'active'

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
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border space-y-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-text-primary">Topics</h1>
            <p className="text-sm text-text-muted mt-0.5">
              {isFiltered
                ? `${filteredTopics.length} of ${topics.length} topics`
                : `${topics.length} topics`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search topics..."
                className="bg-anveshak-bg border border-anveshak-border rounded px-3 py-1.5 pl-8 text-sm text-text-primary focus:border-anveshak-accent outline-none w-56"
              />
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 absolute left-2.5 top-2 text-text-muted" aria-hidden="true">
                <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clipRule="evenodd" />
              </svg>
            </div>
            <Button onClick={() => setShowModal(true)} aria-label="Create new topic">
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden="true">
                <path d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" />
              </svg>
              New topic
            </Button>
          </div>
        </div>

        {/* Filter chips + sort */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex gap-1.5" role="group" aria-label="Filter by status">
            {([
              { value: 'all' as StatusFilter, label: 'All', count: topics.length },
              { value: 'active' as StatusFilter, label: 'Active', count: activeCount },
              { value: 'paused' as StatusFilter, label: 'Paused', count: pausedCount },
            ]).map((f) => (
              <button
                key={f.value}
                onClick={() => setStatusFilter(f.value)}
                aria-pressed={statusFilter === f.value}
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  statusFilter === f.value
                    ? 'bg-anveshak-accent text-white'
                    : 'bg-anveshak-muted text-text-secondary hover:text-text-primary'
                }`}
              >
                {f.label}
                <span
                  className={`text-[10px] font-bold min-w-[18px] h-[18px] flex items-center justify-center rounded-full ${
                    statusFilter === f.value
                      ? 'bg-white/20 text-white'
                      : 'bg-anveshak-border text-text-muted'
                  }`}
                >
                  {f.count}
                </span>
              </button>
            ))}
          </div>
          <div>
            <label htmlFor="topic-sort" className="sr-only">Sort topics</label>
            <select
              id="topic-sort"
              aria-label="Sort topics"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortBy)}
              className="bg-anveshak-bg border border-anveshak-border rounded px-2.5 py-1.5 text-xs text-text-primary focus:border-anveshak-accent outline-none"
            >
              <option value="urgency">Urgency</option>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="most_content">Most content</option>
              <option value="most_signals">Most signals</option>
            </select>
          </div>
        </div>
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
        ) : filteredTopics.length === 0 ? (
          <EmptyState
            icon="🔍"
            title="No matching topics"
            description="Try adjusting your search or filter."
            action={<Button variant="secondary" onClick={() => { setSearch(''); setStatusFilter('all') }}>Clear filters</Button>}
          />
        ) : (
          <div className="max-w-4xl space-y-3">
            {filteredTopics.map((topic) => (
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
