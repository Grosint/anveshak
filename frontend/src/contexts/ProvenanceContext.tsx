import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

export type ProvenanceEntityType = 'identifier' | 'content' | 'source' | 'cluster' | 'signal'

export interface ProvenanceStackEntry {
  entityType: ProvenanceEntityType
  entityId: string
  /** topicId needed for scoping provenance queries */
  topicId?: string
  /** Human-readable label for breadcrumb display */
  label?: string
}

interface ProvenanceContextValue {
  stack: ProvenanceStackEntry[]
  isOpen: boolean
  /** Push a new entity view onto the stack (opens panel if closed) */
  push: (entry: ProvenanceStackEntry) => void
  /** Pop the top entry, closing panel if stack becomes empty */
  pop: () => void
  /** Clear entire stack and close panel */
  close: () => void
  /** Jump to a specific stack index, discarding entries above it */
  jumpTo: (index: number) => void
  /** Current top-of-stack entry (or null if empty) */
  current: ProvenanceStackEntry | null
}

const ProvenanceContext = createContext<ProvenanceContextValue | null>(null)

export function ProvenanceProvider({ children }: { children: ReactNode }) {
  const [stack, setStack] = useState<ProvenanceStackEntry[]>([])

  const isOpen = stack.length > 0

  const push = useCallback((entry: ProvenanceStackEntry) => {
    setStack((prev) => [...prev, entry])
  }, [])

  const pop = useCallback(() => {
    setStack((prev) => prev.slice(0, -1))
  }, [])

  const close = useCallback(() => {
    setStack([])
  }, [])

  const jumpTo = useCallback((index: number) => {
    setStack((prev) => prev.slice(0, index + 1))
  }, [])

  const current = stack.length > 0 ? stack[stack.length - 1] : null

  return (
    <ProvenanceContext.Provider value={{ stack, isOpen, push, pop, close, jumpTo, current }}>
      {children}
    </ProvenanceContext.Provider>
  )
}

export function useProvenance(): ProvenanceContextValue {
  const ctx = useContext(ProvenanceContext)
  if (!ctx) {
    throw new Error('useProvenance must be used within ProvenanceProvider')
  }
  return ctx
}
