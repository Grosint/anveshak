import { lazy, Suspense } from 'react'
import { Modal } from '../ui/Modal'
import { Spinner } from '../ui/Spinner'

const SignalsInbox = lazy(() => import('../../pages/SignalsInbox'))

interface SignalsModalProps {
  open: boolean
  onClose: () => void
}

export function SignalsModal({ open, onClose }: SignalsModalProps) {
  return (
    <Modal fullScreen open={open} onClose={onClose} title="All Signals">
      <Suspense fallback={<div className="p-6"><Spinner label="Loading signals..." /></div>}>
        <SignalsInbox />
      </Suspense>
    </Modal>
  )
}
