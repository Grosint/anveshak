import { useState, useCallback, type ReactNode } from 'react'
import { ProvenanceContext, type ProvenanceStackEntry } from './provenance'

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
