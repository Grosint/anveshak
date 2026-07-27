import { lazy, Suspense } from 'react'
import { useProvenance } from '../../contexts/ProvenanceContext'
import { ProvenanceBreadcrumb } from './ProvenanceBreadcrumb'
import { Spinner } from '../ui/Spinner'

const IdentifierDetail = lazy(() => import('./IdentifierDetail'))
const ContentDetailView = lazy(() => import('./ContentDetailView'))
const SourceDetail = lazy(() => import('./SourceDetail'))
const ClusterDetail = lazy(() => import('./ClusterDetail'))
const SignalDetail = lazy(() => import('./SignalDetail'))

export function ProvenancePanel() {
  const { stack, isOpen, current, pop, close, jumpTo } = useProvenance()

  if (!isOpen || !current) return null

  return (
    <>
      {/* Mobile backdrop (< 768px) */}
      <div
        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
        onClick={close}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside
        className={
          'fixed right-0 top-0 bottom-0 z-50 flex flex-col overflow-hidden bg-[#0b1222] border-l border-anveshak-border/50 shadow-2xl animate-fade-in ' +
          // Full-screen on mobile, 400px on desktop
          'w-full md:w-[400px] md:static md:shrink-0 md:z-auto md:shadow-none'
        }
        aria-label="Provenance panel"
        role="complementary"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-anveshak-border/50 bg-[#0f1729] shrink-0">
          <div className="flex items-center gap-2">
            {stack.length > 1 && (
              <button
                onClick={pop}
                className="text-text-muted hover:text-text-primary transition-colors"
                aria-label="Back"
              >
                <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                  <path fillRule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clipRule="evenodd" />
                </svg>
              </button>
            )}
            <span className="text-[10px] font-bold text-text-muted uppercase tracking-widest">
              Provenance
            </span>
          </div>
          <button
            onClick={close}
            className="text-text-muted hover:text-text-primary transition-colors"
            aria-label="Close panel"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        {/* Breadcrumb trace */}
        <ProvenanceBreadcrumb stack={stack} onJumpTo={jumpTo} />

        {/* Body — lazy-loaded entity detail */}
        <div className="flex-1 overflow-y-auto">
          <Suspense fallback={<div className="p-4"><Spinner label="Loading..." /></div>}>
            {current.entityType === 'identifier' && (
              <IdentifierDetail
                identifierValue={current.entityId}
                topicId={current.topicId ?? ''}
              />
            )}
            {current.entityType === 'content' && (
              <ContentDetailView contentId={current.entityId} />
            )}
            {current.entityType === 'source' && (
              <SourceDetail
                sourceId={current.entityId}
                topicId={current.topicId ?? ''}
              />
            )}
            {current.entityType === 'cluster' && (
              <ClusterDetail
                clusterId={current.entityId}
                topicId={current.topicId ?? ''}
              />
            )}
            {current.entityType === 'signal' && (
              <SignalDetail
                signalId={current.entityId}
                topicId={current.topicId ?? ''}
              />
            )}
          </Suspense>
        </div>
      </aside>
    </>
  )
}
