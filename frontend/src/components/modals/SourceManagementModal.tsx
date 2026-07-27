import { lazy, Suspense } from 'react'
import { Modal } from '../ui/Modal'
import { Spinner } from '../ui/Spinner'

const SourcesTab = lazy(() => import('../workspace/SourcesTab'))

interface SourceManagementModalProps {
  open: boolean
  onClose: () => void
  topicId: string
}

export function SourceManagementModal({ open, onClose, topicId }: SourceManagementModalProps) {
  return (
    <Modal fullScreen open={open} onClose={onClose} title="Manage Sources">
      <Suspense fallback={<div className="p-6"><Spinner label="Loading sources..." /></div>}>
        <SourcesTab topicId={topicId} />
      </Suspense>
    </Modal>
  )
}
