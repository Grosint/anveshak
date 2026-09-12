/**
 * Provenance context object, hook and stack types.
 *
 * Separate from `ProvenanceContext.tsx` so that file exports only the provider
 * component, which is what Vite's fast refresh needs to hot-swap it.
 */
import { createContext, useContext } from 'react'

export type ProvenanceEntityType = 'identifier' | 'content' | 'source' | 'cluster' | 'signal' | 'actor'

export interface ProvenanceStackEntry {
  entityType: ProvenanceEntityType
  entityId: string
  /** topicId needed for scoping provenance queries */
  topicId?: string
  /** Human-readable label for breadcrumb display */
  label?: string
}

export interface ProvenanceContextValue {
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

export const ProvenanceContext = createContext<ProvenanceContextValue | null>(null)

export function useProvenance(): ProvenanceContextValue {
  const ctx = useContext(ProvenanceContext)
  if (!ctx) {
    throw new Error('useProvenance must be used within ProvenanceProvider')
  }
  return ctx
}
