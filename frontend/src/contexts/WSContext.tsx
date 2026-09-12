/**
 * Singleton WebSocket connection for real-time signal delivery.
 *
 * API endpoint: WS /api/v1/signals/ws/{session_id}?token={jwt}&since={iso}
 * Auth: JWT via query param (confirmed from signals.py — WS can't send headers)
 * Reconnect: exponential back-off 1s → 2s → 4s → 8s (capped)
 * Missed signals: `since` param sends last-disconnect ISO timestamp on reconnect
 */
import {
  useEffect,
  useRef,
  useCallback,
  ReactNode,
} from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from './auth'
import {
  WSContext,
  type MessageHandler,
  type WSContextValue,
  type WSMessage,
} from './ws'

function getSessionId(): string {
  let id = localStorage.getItem('anveshak_session_id')
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem('anveshak_session_id', id)
  }
  return id
}

function buildWsUrl(token: string, since?: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = window.location.host
  const sessionId = getSessionId()
  const params = new URLSearchParams({ token })
  if (since) params.set('since', since)
  return `${proto}://${host}/api/v1/signals/ws/${sessionId}?${params}`
}

export function WSProvider({ children }: { children: ReactNode }) {
  const { token, isAuthenticated } = useAuth()
  const queryClient = useQueryClient()
  const wsRef = useRef<WebSocket | null>(null)
  const handlersRef = useRef<Set<MessageHandler>>(new Set())
  const statusRef = useRef<'connected' | 'disconnected' | 'connecting'>('disconnected')
  const retryDelay = useRef(1000)
  const disconnectedAt = useRef<string | undefined>(undefined)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmounted = useRef(false)
  // Holds the current `connect` so the reconnect timer can call it without
  // `connect` referring to itself while it is still being declared.
  const connectRef = useRef<() => void>(() => undefined)

  const connect = useCallback(() => {
    if (!token || unmounted.current) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    statusRef.current = 'connecting'
    const ws = new WebSocket(buildWsUrl(token, disconnectedAt.current))
    wsRef.current = ws

    ws.onopen = () => {
      statusRef.current = 'connected'
      retryDelay.current = 1000 // reset back-off on success
      disconnectedAt.current = undefined
    }

    ws.onmessage = (evt) => {
      let msg: WSMessage
      try {
        msg = JSON.parse(evt.data as string) as WSMessage
      } catch {
        return
      }
      if (msg.type === 'ping') return

      // Invalidate signals query so SignalsInbox re-fetches
      void queryClient.invalidateQueries({ queryKey: ['signals'] })

      // Notify local subscribers
      handlersRef.current.forEach((h) => h(msg))
    }

    ws.onclose = () => {
      if (unmounted.current) return
      statusRef.current = 'disconnected'
      disconnectedAt.current = new Date().toISOString()
      reconnectTimer.current = setTimeout(() => {
        retryDelay.current = Math.min(retryDelay.current * 2, 8000)
        connectRef.current()
      }, retryDelay.current)
    }

    ws.onerror = () => ws.close()
  }, [token, queryClient])

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  useEffect(() => {
    if (!isAuthenticated) return
    unmounted.current = false
    connect()
    return () => {
      unmounted.current = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
      statusRef.current = 'disconnected'
    }
  }, [isAuthenticated, connect])

  const subscribe = useCallback((handler: MessageHandler) => {
    handlersRef.current.add(handler)
    return () => handlersRef.current.delete(handler)
  }, [])

  // Expose status as a stable value (not reactive — avoids re-renders)
  const ctx: WSContextValue = {
    subscribe,
    get status() {
      return statusRef.current
    },
  }

  return <WSContext.Provider value={ctx}>{children}</WSContext.Provider>
}
