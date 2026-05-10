import { useQuery } from '@tanstack/react-query'
import { topicsApi } from '../api/topics'
import { Spinner } from '../components/ui/Spinner'
import ScheduleManager from '../components/reports/ScheduleManager'

export default function ScheduledReports() {
  const { data: topics = [], isLoading } = useQuery({
    queryKey: ['topics'],
    queryFn: topicsApi.list,
  })

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 pt-6 pb-4 border-b border-anveshak-border">
        <h1 className="text-xl font-semibold text-text-primary">Scheduled Reports</h1>
        <p className="text-sm text-text-muted mt-0.5">
          {topics.filter((t) => t.scheduled_report_cron).length} of {topics.length} topics have scheduled reports
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Spinner label="Loading topics..." />
          </div>
        ) : (
          <ScheduleManager topics={topics} />
        )}
      </div>
    </div>
  )
}
