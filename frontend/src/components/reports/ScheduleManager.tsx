import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { topicsApi, Topic } from '../../api/topics'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { EmptyState } from '../ui/EmptyState'
import { Modal } from '../ui/Modal'

const REPORT_TYPES = [
  { value: 'intelligence_brief', label: 'Intelligence Brief' },
  { value: 'research_summary', label: 'Research Summary' },
  { value: 'weekly_digest', label: 'Weekly Digest' },
]

const CRON_PRESETS = [
  { label: 'Every hour', value: '0 * * * *' },
  { label: 'Daily 9 AM', value: '0 9 * * *' },
  { label: 'Weekly Monday', value: '0 9 * * MON' },
  { label: 'Custom', value: '' },
]

function cronToHuman(cron: string): string {
  if (cron === '0 * * * *') return 'Every hour'
  if (cron === '0 9 * * *') return 'Daily at 09:00 UTC'
  if (cron === '0 9 * * MON') return 'Weekly on Monday 09:00 UTC'
  if (/^\*\/\d+ \* \* \* \*$/.test(cron)) return `Every ${cron.split('/')[1]} minutes`
  if (/^0 0 \* \* 0$/.test(cron)) return 'Weekly on Sunday midnight UTC'
  return cron
}

function EditScheduleModal({
  open,
  onClose,
  topic,
}: {
  open: boolean
  onClose: () => void
  topic: Topic | null
}) {
  const [cron, setCron] = useState(topic?.scheduled_report_cron || '')
  const [reportType, setReportType] = useState(topic?.scheduled_report_type || 'intelligence_brief')
  const [preset, setPreset] = useState<string>(() => {
    const match = CRON_PRESETS.find((p) => p.value === (topic?.scheduled_report_cron || ''))
    return match ? match.value : ''
  })
  const [error, setError] = useState('')
  const qc = useQueryClient()

  const update = useMutation({
    mutationFn: () => topicsApi.updateSchedule(topic!.id, cron || null, reportType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topics'] })
      setError('')
      onClose()
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail || 'Failed to update schedule')
    },
  })

  if (!topic) return null

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Schedule: ${topic.name}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={update.isPending} onClick={() => update.mutate()}>
            Save Schedule
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {error && (
          <p className="text-sm text-signal-high bg-signal-high/10 rounded px-3 py-2">{error}</p>
        )}
        <div>
          <label className="block text-sm text-text-secondary mb-1">Preset</label>
          <div className="flex flex-wrap gap-2">
            {CRON_PRESETS.map((p) => (
              <button
                key={p.label}
                onClick={() => {
                  setPreset(p.value)
                  if (p.value) setCron(p.value)
                }}
                className={`px-3 py-1.5 rounded text-xs font-medium border transition-colors ${
                  preset === p.value
                    ? 'border-anveshak-accent bg-anveshak-accent/20 text-anveshak-accent'
                    : 'border-anveshak-border text-text-secondary hover:border-anveshak-accent'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-sm text-text-secondary mb-1">Cron Expression</label>
          <input
            type="text"
            value={cron}
            onChange={(e) => { setCron(e.target.value); setPreset('') }}
            className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary font-mono focus:border-anveshak-accent outline-none"
            placeholder="0 9 * * MON"
          />
          <p className="text-xs text-text-muted mt-1">Format: minute hour day month weekday</p>
        </div>
        <div>
          <label className="block text-sm text-text-secondary mb-1">Report Type</label>
          <select
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
            className="w-full bg-anveshak-bg border border-anveshak-border rounded px-3 py-2 text-sm text-text-primary focus:border-anveshak-accent outline-none"
          >
            {REPORT_TYPES.map((rt) => (
              <option key={rt.value} value={rt.value}>{rt.label}</option>
            ))}
          </select>
        </div>
      </div>
    </Modal>
  )
}

export default function ScheduleManager({ topics }: { topics: Topic[] }) {
  const [editTopic, setEditTopic] = useState<Topic | null>(null)
  const qc = useQueryClient()

  const clearSchedule = useMutation({
    mutationFn: (topicId: string) => topicsApi.updateSchedule(topicId, null, null),
    onSettled: () => qc.invalidateQueries({ queryKey: ['topics'] }),
  })

  const scheduled = topics.filter((t) => t.scheduled_report_cron)
  const unscheduled = topics.filter((t) => !t.scheduled_report_cron)

  if (topics.length === 0) {
    return (
      <EmptyState
        icon="📅"
        title="No topics"
        description="Create a topic first, then configure scheduled reports."
      />
    )
  }

  return (
    <div className="space-y-6">
      {/* Scheduled topics */}
      {scheduled.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
            Active Schedules
          </h2>
          <div className="bg-anveshak-card border border-anveshak-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-anveshak-border text-left text-xs text-text-muted uppercase tracking-wide">
                  <th className="px-4 py-3">Topic</th>
                  <th className="px-4 py-3">Schedule</th>
                  <th className="px-4 py-3">Report Type</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {scheduled.map((t) => (
                  <tr key={t.id} className="border-b border-anveshak-border last:border-0 hover:bg-anveshak-muted/30">
                    <td className="px-4 py-3 text-text-primary font-medium">{t.name}</td>
                    <td className="px-4 py-3">
                      <span className="text-text-primary">{cronToHuman(t.scheduled_report_cron!)}</span>
                      <span className="text-text-muted text-xs ml-2 font-mono">({t.scheduled_report_cron})</span>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="accent">
                        {REPORT_TYPES.find((rt) => rt.value === t.scheduled_report_type)?.label || t.scheduled_report_type || 'Intelligence Brief'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => setEditTopic(t)}>Edit</Button>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => clearSchedule.mutate(t.id)}
                          disabled={clearSchedule.isPending}
                        >
                          Clear
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Unscheduled topics */}
      {unscheduled.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">
            Unscheduled Topics
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {unscheduled.map((t) => (
              <div
                key={t.id}
                className="bg-anveshak-card border border-anveshak-border rounded-lg p-4 flex items-center justify-between"
              >
                <div>
                  <p className="text-sm font-medium text-text-primary">{t.name}</p>
                  <p className="text-xs text-text-muted mt-0.5">{t.content_count ?? 0} items</p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setEditTopic(t)}>
                  Schedule
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      <EditScheduleModal
        open={editTopic !== null}
        onClose={() => setEditTopic(null)}
        topic={editTopic}
      />
    </div>
  )
}
