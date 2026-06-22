import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell,
} from 'recharts'
import { assessmentsApi, type SourceAssessment, type SourceStats } from '../../api/assessments'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'

const PIE_COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
const SENTIMENT_COLORS = { negative: '#ef4444', neutral: '#94a3b8', positive: '#22c55e' }

interface SourceAssessmentPanelProps {
  topicId: string
  sourceId: string
  sourceName: string
  onClose: () => void
}

export default function SourceAssessmentPanel({
  topicId,
  sourceId,
  sourceName,
  onClose,
}: SourceAssessmentPanelProps) {
  const [assessment, setAssessment] = useState<SourceAssessment | null>(null)

  const assessMut = useMutation({
    mutationFn: () => assessmentsApi.create(topicId, sourceId),
    onSuccess: (data) => setAssessment(data),
  })

  if (!assessment && !assessMut.isPending && !assessMut.isError) {
    return (
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-text-primary">
            Source Assessment: {sourceName}
          </h3>
          <Button size="sm" variant="ghost" onClick={onClose}>Close</Button>
        </div>
        <p className="text-sm text-text-muted">
          Generate a deterministic intelligence card for this source within this topic.
          Includes posting patterns, engagement, entities, identifier overlap, and narrative participation.
        </p>
        <Button onClick={() => assessMut.mutate()} disabled={assessMut.isPending}>
          Assess Source (Last 30 Days)
        </Button>
      </div>
    )
  }

  if (assessMut.isPending) {
    return (
      <div className="p-6 flex flex-col items-center justify-center gap-3">
        <Spinner label="Computing source assessment..." />
      </div>
    )
  }

  if (assessMut.isError) {
    const errMsg = (assessMut.error as { response?: { data?: { detail?: string } } })
      ?.response?.data?.detail || 'Failed to compute assessment'
    return (
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-text-primary">Assessment Failed</h3>
          <Button size="sm" variant="ghost" onClick={onClose}>Close</Button>
        </div>
        <p className="text-sm text-red-400">{errMsg}</p>
        <Button onClick={() => assessMut.mutate()}>Retry</Button>
      </div>
    )
  }

  if (!assessment) return null
  const stats = assessment.stats

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(100vh-200px)]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">
            Source Assessment: {sourceName}
          </h3>
          <p className="text-xs text-text-muted mt-1">
            {assessment.content_item_count} items &middot;{' '}
            {new Date(assessment.time_window_start).toLocaleDateString()} –{' '}
            {new Date(assessment.time_window_end).toLocaleDateString()}
          </p>
        </div>
        <Button size="sm" variant="ghost" onClick={onClose}>Close</Button>
      </div>

      {/* Platform metadata (Phase 1) */}
      {assessment.platform_metadata && (
        <PlatformProfile metadata={assessment.platform_metadata} />
      )}

      {/* Stat cards */}
      <StatCards stats={stats} />

      {/* Volume timeline */}
      {stats.volume_timeline.length > 0 && (
        <Section title="Posting Volume">
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={stats.volume_timeline}>
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} width={30} />
              <Tooltip contentStyle={{ background: '#1e1e2e', border: 'none', fontSize: 12 }} />
              <Area type="monotone" dataKey="count" stroke="#6366f1" fill="#6366f140" />
            </AreaChart>
          </ResponsiveContainer>
        </Section>
      )}

      {/* Two-column: Language + Sentiment */}
      <div className="grid grid-cols-2 gap-4">
        {stats.language_breakdown.length > 0 && (
          <Section title="Languages">
            <ResponsiveContainer width="100%" height={140}>
              <PieChart>
                <Pie
                  data={stats.language_breakdown}
                  dataKey="count"
                  nameKey="language"
                  cx="50%"
                  cy="50%"
                  outerRadius={55}
                  label={({ language, pct }: { language: string; pct: number }) =>
                    `${language} ${pct}%`
                  }
                  labelLine={false}
                >
                  {stats.language_breakdown.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#1e1e2e', border: 'none', fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </Section>
        )}

        <Section title="Sentiment">
          <ResponsiveContainer width="100%" height={140}>
            <BarChart
              data={[stats.sentiment_distribution]}
              layout="vertical"
              margin={{ left: 0 }}
            >
              <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis type="category" dataKey="name" hide />
              <Tooltip contentStyle={{ background: '#1e1e2e', border: 'none', fontSize: 12 }} />
              <Bar dataKey="negative" stackId="s" fill={SENTIMENT_COLORS.negative} />
              <Bar dataKey="neutral" stackId="s" fill={SENTIMENT_COLORS.neutral} />
              <Bar dataKey="positive" stackId="s" fill={SENTIMENT_COLORS.positive} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-3 text-xs text-text-muted mt-1">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full" style={{ background: SENTIMENT_COLORS.negative }} />
              Neg: {stats.sentiment_distribution.negative}
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full" style={{ background: SENTIMENT_COLORS.neutral }} />
              Neu: {stats.sentiment_distribution.neutral}
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full" style={{ background: SENTIMENT_COLORS.positive }} />
              Pos: {stats.sentiment_distribution.positive}
            </span>
          </div>
        </Section>
      </div>

      {/* Top entities */}
      {stats.top_entities.length > 0 && (
        <Section title="Top Entities">
          <div className="max-h-48 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-text-muted text-xs border-b border-anveshak-border">
                  <th className="pb-1">Entity</th>
                  <th className="pb-1">Type</th>
                  <th className="pb-1 text-right">Count</th>
                </tr>
              </thead>
              <tbody>
                {stats.top_entities.map((e, i) => (
                  <tr key={i} className="border-b border-anveshak-border/30">
                    <td className="py-1 text-text-primary">{e.entity_text}</td>
                    <td className="py-1">
                      <Badge variant="ghost" className="text-[9px]">{e.entity_type}</Badge>
                    </td>
                    <td className="py-1 text-right text-text-muted">{e.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* Cluster participation (narrative role) */}
      {stats.cluster_participation.length > 0 && (
        <Section title="Narrative Participation">
          <div className="space-y-1">
            {stats.cluster_participation.map((c) => (
              <div
                key={c.cluster_id}
                className="flex items-center justify-between text-sm p-2 bg-anveshak-card/50 rounded"
              >
                <span className="text-text-primary truncate">{c.label}</span>
                <Badge variant="ghost">{c.item_count} items</Badge>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Identifier overlap (Engine C) */}
      {stats.identifier_overlap.length > 0 && (
        <Section title="Cross-Source Identifiers">
          <div className="max-h-48 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-text-muted text-xs border-b border-anveshak-border">
                  <th className="pb-1">Identifier</th>
                  <th className="pb-1">Type</th>
                  <th className="pb-1 text-right">Other Sources</th>
                </tr>
              </thead>
              <tbody>
                {stats.identifier_overlap.map((id, i) => (
                  <tr key={i} className="border-b border-anveshak-border/30">
                    <td className="py-1 text-text-primary font-mono text-xs truncate max-w-[200px]">
                      {id.identifier_value}
                    </td>
                    <td className="py-1">
                      <Badge variant="warning" className="text-[9px]">{id.identifier_type}</Badge>
                    </td>
                    <td className="py-1 text-right text-text-muted">{id.source_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* Credibility trajectory */}
      {stats.credibility_trajectory.length > 0 && (
        <Section title="Credibility History">
          <div className="space-y-1 max-h-36 overflow-y-auto">
            {stats.credibility_trajectory.map((c, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-text-muted">
                <span>{new Date(c.date).toLocaleDateString()}</span>
                <span className={c.new_score > c.old_score ? 'text-green-400' : 'text-red-400'}>
                  {c.old_score.toFixed(1)} → {c.new_score.toFixed(1)}
                </span>
                <span className="truncate">{c.reason}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* LLM Brief — Phase 2 */}
      <AssessmentBriefSection
        topicId={topicId}
        sourceId={sourceId}
        assessmentId={assessment.id}
        briefMd={assessment.brief_md}
      />
    </div>
  )
}

/* ---------- LLM Brief Section ---------- */

function AssessmentBriefSection({
  topicId,
  sourceId,
  assessmentId,
  briefMd,
}: {
  topicId: string
  sourceId: string
  assessmentId: string
  briefMd: string | null
}) {
  const [polling, setPolling] = useState(false)

  const briefMut = useMutation({
    mutationFn: () => assessmentsApi.generateBrief(topicId, sourceId, assessmentId),
    onSuccess: () => setPolling(true),
  })

  // Poll for brief completion
  const { data: polledAssessment } = useQuery({
    queryKey: ['assessment-poll', assessmentId],
    queryFn: () => assessmentsApi.get(topicId, sourceId, assessmentId),
    refetchInterval: polling ? 5000 : false,
    enabled: polling,
  })

  // Stop polling when brief is ready or failed
  useEffect(() => {
    if (polledAssessment?.brief_md || polledAssessment?.generation_status === 'failed') {
      setPolling(false)
    }
  }, [polledAssessment])

  const finalBrief = polledAssessment?.brief_md ?? briefMd
  const failed = polledAssessment?.generation_status === 'failed'

  if (finalBrief) {
    return (
      <Section title="AI Assessment Brief">
        <div className="prose prose-sm prose-anveshak max-w-none text-text-primary">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{finalBrief}</ReactMarkdown>
        </div>
        {polledAssessment?.confidence_score != null && (
          <p className="text-xs text-text-muted mt-2">
            Confidence: {(polledAssessment.confidence_score * 100).toFixed(0)}%
          </p>
        )}
      </Section>
    )
  }

  return (
    <Section title="AI Assessment Brief">
      {polling ? (
        <div className="flex items-center gap-2">
          <Spinner label="Generating brief..." />
          <span className="text-xs text-text-muted">This may take 30-60 seconds on CPU</span>
        </div>
      ) : failed ? (
        <div className="space-y-2">
          <p className="text-sm text-red-400">Brief generation failed.</p>
          <Button size="sm" onClick={() => briefMut.mutate()}>Retry</Button>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-text-muted">
            Generate an LLM-powered narrative assessment with per-claim citations.
          </p>
          <Button
            size="sm"
            onClick={() => briefMut.mutate()}
            disabled={briefMut.isPending}
          >
            Generate Brief
          </Button>
        </div>
      )}
    </Section>
  )
}


/* ---------- Helper components ---------- */

function StatCards({ stats }: { stats: SourceStats }) {
  const cards = [
    { label: 'Posts', value: stats.total_posts.toLocaleString() },
    { label: 'Avg/Day', value: stats.avg_posts_per_day.toFixed(1) },
    { label: 'Likes', value: stats.engagement.likes.toLocaleString() },
    { label: 'Views', value: stats.engagement.views.toLocaleString() },
    { label: 'Shares', value: stats.engagement.shares.toLocaleString() },
    { label: 'Clusters', value: stats.cluster_participation.length.toString() },
  ]
  return (
    <div className="grid grid-cols-3 gap-3">
      {cards.map((c) => (
        <div
          key={c.label}
          className="p-3 bg-anveshak-card border border-anveshak-border rounded-lg text-center"
        >
          <div className="text-xl font-bold text-text-primary">{c.value}</div>
          <div className="text-[10px] text-text-muted uppercase tracking-wide">{c.label}</div>
        </div>
      ))}
    </div>
  )
}

function PlatformProfile({ metadata }: { metadata: Record<string, unknown> }) {
  const fields: { label: string; key: string; fmt?: (v: unknown) => string }[] = [
    { label: 'Title', key: 'title' },
    { label: 'Description', key: 'about' },
    { label: 'Description', key: 'description' },
    { label: 'Subscribers', key: 'subscriber_count', fmt: (v) => Number(v).toLocaleString() },
    { label: 'Members', key: 'participants_count', fmt: (v) => Number(v).toLocaleString() },
    { label: 'Videos', key: 'video_count', fmt: (v) => Number(v).toLocaleString() },
    { label: 'Total Views', key: 'view_count', fmt: (v) => Number(v).toLocaleString() },
    { label: 'Created', key: 'created_at', fmt: (v) => new Date(String(v)).toLocaleDateString() },
    { label: 'Created', key: 'published_at', fmt: (v) => new Date(String(v)).toLocaleDateString() },
    { label: 'Country', key: 'country' },
    { label: 'Verified', key: 'is_verified', fmt: (v) => v ? 'Yes' : 'No' },
  ]
  const visible = fields.filter((f) => metadata[f.key] != null && metadata[f.key] !== '')
  if (visible.length === 0) return null

  return (
    <Section title="Platform Profile">
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        {visible.map((f) => (
          <div key={f.key} className="flex justify-between">
            <span className="text-text-muted">{f.label}</span>
            <span className="text-text-primary truncate max-w-[200px]">
              {f.fmt ? f.fmt(metadata[f.key]) : String(metadata[f.key])}
            </span>
          </div>
        ))}
      </div>
    </Section>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">
        {title}
      </h4>
      {children}
    </div>
  )
}
