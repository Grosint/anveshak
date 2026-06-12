import { useQuery } from '@tanstack/react-query'
import { topicsApi } from '../../api/topics'
import { signalsApi } from '../../api/signals'
import { identifiersApi } from '../../api/identifiers'

interface QuickStatsProps {
  topicId: string
}

export function QuickStats({ topicId }: QuickStatsProps) {
  const { data: topic } = useQuery({
    queryKey: ['topics', topicId],
    queryFn: () => topicsApi.get(topicId),
  })

  const { data: clusters = [] } = useQuery({
    queryKey: ['clusters', topicId],
    queryFn: () => topicsApi.listClusters(topicId),
  })

  const { data: signals = [] } = useQuery({
    queryKey: ['signals-topic', topicId, 'new'],
    queryFn: () => signalsApi.listByTopic(topicId, 'new'),
  })

  const { data: identifiers = [] } = useQuery({
    queryKey: ['identifiers-top', topicId],
    queryFn: () => identifiersApi.top(topicId, undefined, 5),
  })

  const stats = [
    { label: 'Content', value: topic?.content_count ?? 0 },
    { label: 'Clusters', value: clusters.length },
    { label: 'Signals', value: signals.length, accent: signals.length > 0 },
    { label: 'Identifiers', value: identifiers.length },
  ]

  return (
    <div className="grid grid-cols-2 gap-1.5">
      {stats.map((s) => (
        <div
          key={s.label}
          className="bg-anveshak-muted/50 rounded px-2.5 py-2 text-center"
        >
          <p className={`text-lg font-bold ${s.accent ? 'text-signal-high' : 'text-text-primary'}`}>
            {s.value}
          </p>
          <p className="text-[9px] text-text-muted uppercase tracking-wider">{s.label}</p>
        </div>
      ))}
    </div>
  )
}
