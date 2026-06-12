import { Signal } from '../../api/signals'
import { TopIdentifier } from '../../api/identifiers'
import { SignalsSidebar } from './SignalsSidebar'
import { TopIdentifiers } from './TopIdentifiers'
import { QuickStats } from './QuickStats'
import { ActiveTemplates } from './ActiveTemplates'
import { RecentActivity } from './RecentActivity'

interface IntelSidebarProps {
  topicId: string
  onSelectSignal: (signal: Signal) => void
  onSelectIdentifier: (id: TopIdentifier) => void
  onViewAllIdentifiers: () => void
  onManageTemplates: () => void
}

export function IntelSidebar({
  topicId,
  onSelectSignal,
  onSelectIdentifier,
  onViewAllIdentifiers,
  onManageTemplates,
}: IntelSidebarProps) {
  return (
    <aside className="w-[280px] shrink-0 border-r border-anveshak-border overflow-y-auto bg-[#0b1222]">
      <div className="p-3 space-y-4">
        <SignalsSidebar topicId={topicId} onSelectSignal={onSelectSignal} />

        <div className="border-t border-anveshak-border/50 pt-3">
          <TopIdentifiers
            topicId={topicId}
            onSelectIdentifier={onSelectIdentifier}
            onViewAll={onViewAllIdentifiers}
          />
        </div>

        <div className="border-t border-anveshak-border/50 pt-3">
          <QuickStats topicId={topicId} />
        </div>

        <div className="border-t border-anveshak-border/50 pt-3">
          <ActiveTemplates topicId={topicId} onManage={onManageTemplates} />
        </div>

        <div className="border-t border-anveshak-border/50 pt-3">
          <RecentActivity topicId={topicId} />
        </div>
      </div>
    </aside>
  )
}
