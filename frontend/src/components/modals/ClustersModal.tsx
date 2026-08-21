import { Modal } from '../ui/Modal'
import { ClusterBrowser } from '../clusters/ClusterBrowser'

interface ClustersModalProps {
  open: boolean
  onClose: () => void
  topicId: string
  onSelectContent?: (contentId: string, title?: string) => void
}

export function ClustersModal({ open, onClose, topicId, onSelectContent }: ClustersModalProps) {
  const handleSelect = (contentId: string, title?: string) => {
    onSelectContent?.(contentId, title)
    onClose()
  }

  return (
    <Modal fullScreen open={open} onClose={onClose} title="All Clusters">
      <ClusterBrowser topicId={topicId} onSelectContent={handleSelect} />
    </Modal>
  )
}
