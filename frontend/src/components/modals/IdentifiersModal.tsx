import { lazy, Suspense } from 'react'
import { Modal } from '../ui/Modal'
import { Spinner } from '../ui/Spinner'

const Identifiers = lazy(() => import('../../pages/Identifiers'))

interface IdentifiersModalProps {
  open: boolean
  onClose: () => void
  topicId: string
  onSelectIdentifier?: (type: string, value: string) => void
}

export function IdentifiersModal({ open, onClose, topicId, onSelectIdentifier }: IdentifiersModalProps) {
  const handleSelect = (type: string, value: string) => {
    onSelectIdentifier?.(type, value)
    onClose()
  }

  return (
    <Modal fullScreen open={open} onClose={onClose} title="All Identifiers">
      <Suspense fallback={<div className="p-6"><Spinner label="Loading identifiers..." /></div>}>
        <Identifiers embedded topicId={topicId} onSelectIdentifier={handleSelect} />
      </Suspense>
    </Modal>
  )
}
