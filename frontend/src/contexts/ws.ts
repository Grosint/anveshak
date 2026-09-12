/**
 * WebSocket context object, hook and message types.
 *
 * Separate from `WSContext.tsx` so that file exports only the provider
 * component, which is what Vite's fast refresh needs to hot-swap it.
 */
import { createContext, useContext } from 'react'

export interface WSSignalMessage {
  type: 'signal' | 'signal_replay'
  signal_id: string
  topic_id: string
  cluster_id: string | null
  signal_type: string
  description?: string
  severity?: string
  created_at: string
}

export type WSMessage = WSSignalMessage | { type: 'ping' }

export type MessageHandler = (msg: WSSignalMessage) => void

export interface WSContextValue {
  subscribe: (handler: MessageHandler) => () => void
  status: 'connected' | 'disconnected' | 'connecting'
}

export const WSContext = createContext<WSContextValue | null>(null)

export function useWS() {
  const ctx = useContext(WSContext)
  if (!ctx) throw new Error('useWS must be inside WSProvider')
  return ctx
}
