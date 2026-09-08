import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { candidatesApi, type CandidateTopic } from '../api/candidates'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { Spinner } from '../components/ui/Spinner'

/**
 * Candidate Topic inbox — issues #26 and #27.
 *
 * Its own top-level page because triage is a different task from monitoring,
 * and mixing them buries it.
 *
 * Every card leads with the narrative and the measurements that surfaced it,
 * so an analyst judges for themselves rather than trusting a score. Ordering
 * comes from the API and is by propagation only. No concern category appears
 * here, and none orders anything. See ADR 0001.
 */

function Measurement({
  label,
  value,
  threshold,
}: {
  label: string
  value: number | string
  threshold?: number
}) {
  return (
    <div className="min-w-[92px]">
      <p className="text-sm font-semibold text-text-primary">{value}</p>
      <p className="text-[10px] text-text-muted">
        {label}
        {threshold !== undefined && ` · gate ${threshold}`}
      </p>
    </div>
  )
}

function CandidateCard({
  candidate,
  onAccept,
  onDismiss,
  busy,
}: {
  candidate: CandidateTopic
  onAccept: (candidate: CandidateTopic) => void
  onDismiss: (candidate: CandidateTopic) => void
  busy: boolean
}) {
  const thresholds = candidate.evidence?.measurements?.thresholds ?? {}
  const label = candidate.cluster_label || 'Unlabelled narrative'

  return (
    <article className="bg-anveshak-card border border-anveshak-border rounded-lg p-4 animate-fade-in">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-text-primary">{label}</h3>
          <p className="text-[11px] text-text-muted mt-0.5">
            Found in {candidate.watch_space_name ?? 'a Watch Space'}
            {' · '}
            surfaced {formatDistanceToNow(new Date(candidate.created_at), { addSuffix: true })}
          </p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <Button
            size="sm"
            onClick={() => onAccept(candidate)}
            disabled={busy}
            aria-label={`Accept ${label}`}
          >
            Accept
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDismiss(candidate)}
            disabled={busy}
            aria-label={`Dismiss ${label}`}
          >
            Dismiss
          </Button>
        </div>
      </div>

      {/* Why it surfaced: the four gates, with the numbers that cleared them. */}
      <div className="flex flex-wrap gap-4 mt-3 pt-3 border-t border-anveshak-border/50">
        <Measurement
          label="independent sources"
          value={candidate.independent_source_count}
          threshold={thresholds.min_independent_sources}
        />
        <Measurement
          label="items"
          value={candidate.item_count}
          threshold={thresholds.min_item_count}
        />
        <Measurement label="contributing accounts" value={candidate.contributing_account_count} />
        <Measurement
          label="novelty"
          value={candidate.novelty_score === null ? '—' : candidate.novelty_score.toFixed(2)}
          threshold={thresholds.min_novelty}
        />
        <Measurement
          label="clustering runs"
          value={candidate.run_count}
          threshold={thresholds.min_runs}
        />
      </div>
    </article>
  )
}

export default function CandidateInbox() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [busyId, setBusyId] = useState<string | null>(null)

  const { data: candidates, isLoading } = useQuery({
    queryKey: ['candidate-topics', 'pending'],
    queryFn: () => candidatesApi.list('pending'),
  })

  const accept = useMutation({
    mutationFn: (candidate: CandidateTopic) =>
      candidatesApi.accept(candidate.id, {
        name: candidate.cluster_label ?? undefined,
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['candidate-topics'] })
      queryClient.invalidateQueries({ queryKey: ['topics'] })
      navigate(`/topics/${result.topic_id}`)
    },
    onSettled: () => setBusyId(null),
  })

  const dismiss = useMutation({
    mutationFn: (candidate: CandidateTopic) => candidatesApi.dismiss(candidate.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['candidate-topics'] }),
    onSettled: () => setBusyId(null),
  })

  if (isLoading) {
    return <div className="p-8"><Spinner label="Loading candidates..." /></div>
  }

  return (
    <div className="p-6 max-w-5xl">
      <header className="mb-4">
        <h1 className="text-lg font-semibold text-text-primary">Candidate topics</h1>
        <p className="text-xs text-text-secondary mt-1">
          Narratives that formed inside a Watch Space without anyone configuring them. They
          are not monitored until you accept one.
        </p>
      </header>

      {!candidates || candidates.length === 0 ? (
        <EmptyState
          icon="📥"
          title="Nothing waiting"
          description="No narrative has crossed all four promotion gates yet."
        />
      ) : (
        <div className="space-y-3">
          {candidates.map((candidate) => (
            <CandidateCard
              key={candidate.id}
              candidate={candidate}
              busy={busyId === candidate.id}
              onAccept={(c) => {
                setBusyId(c.id)
                accept.mutate(c)
              }}
              onDismiss={(c) => {
                setBusyId(c.id)
                dismiss.mutate(c)
              }}
            />
          ))}
        </div>
      )}
    </div>
  )
}
