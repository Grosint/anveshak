import { lazy, Suspense } from 'react'
import { Modal } from '../ui/Modal'
import { Spinner } from '../ui/Spinner'

const ReportsTab = lazy(() => import('../workspace/ReportsTab'))

interface ReportGenerationModalProps {
  open: boolean
  onClose: () => void
  topicId: string
}

export function ReportGenerationModal({ open, onClose, topicId }: ReportGenerationModalProps) {
  return (
    <Modal fullScreen open={open} onClose={onClose} title="Generate Report">
      <Suspense fallback={<div className="p-6"><Spinner label="Loading reports..." /></div>}>
        <ReportsTab topicId={topicId} />
      </Suspense>
    </Modal>
  )
}
