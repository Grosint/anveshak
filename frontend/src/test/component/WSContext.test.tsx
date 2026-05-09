/**
 * Tests for the real WSProvider component.
 *
 * Tests WebSocket connection, message handling, reconnect backoff (R3),
 * and cleanup behavior.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { WSProvider, useWS } from '../../contexts/WSContext'

// ── Mock WebSocket ──────────────────────────────────────────────────────

class MockWebSocket {
  static instances: MockWebSocket[] = []

  url: string
  readyState = 0 // CONNECTING
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onmessage: ((evt: { data: string }) => void) | null = null
  onerror: (() => void) | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  close() {
    this.readyState = 3 // CLOSED
  }

  // Test helpers
  simulateOpen() {
    this.readyState = 1 // OPEN
    this.onopen?.()
  }

  simulateClose() {
    this.readyState = 3
    this.onclose?.()
  }

  simulateMessage(data: string) {
    this.onmessage?.({ data })
  }

  simulateError() {
    this.onerror?.()
  }

  static readonly OPEN = 1
  static readonly CLOSED = 3
}

// ── Mock AuthContext ────────────────────────────────────────────────────

const mockAuth = {
  token: 'test-jwt-token',
  isAuthenticated: true,
}

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}))

// ── Helpers ─────────────────────────────────────────────────────────────

let subscribedHandler: ((msg: any) => void) | null = null

function WSConsumer() {
  const { subscribe, status } = useWS()

  // Subscribe on mount
  React.useEffect(() => {
    const handler = (msg: any) => {
      subscribedHandler?.(msg)
    }
    const unsub = subscribe(handler)
    return unsub
  }, [subscribe])

  return <span data-testid="ws-status">{status}</span>
}

import React from 'react'

function renderWS(authOverrides?: Partial<typeof mockAuth>) {
  if (authOverrides) Object.assign(mockAuth, authOverrides)

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  // Spy on query invalidation
  const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

  const result = render(
    <QueryClientProvider client={queryClient}>
      <WSProvider>
        <WSConsumer />
      </WSProvider>
    </QueryClientProvider>,
  )

  return { ...result, queryClient, invalidateSpy }
}

function latestWS(): MockWebSocket {
  return MockWebSocket.instances[MockWebSocket.instances.length - 1]
}

// ── Setup / Teardown ────────────────────────────────────────────────────

beforeEach(() => {
  vi.useFakeTimers()
  MockWebSocket.instances = []
  subscribedHandler = null
  localStorage.clear()
  vi.stubGlobal('WebSocket', MockWebSocket)
  // Reset auth mock
  mockAuth.token = 'test-jwt-token'
  mockAuth.isAuthenticated = true
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  localStorage.clear()
})

// ── Tests ───────────────────────────────────────────────────────────────

describe('WSProvider — connection', () => {
  it('connects with JWT token as query param', () => {
    renderWS()
    const ws = latestWS()
    expect(ws.url).toContain('token=test-jwt-token')
  })

  it('includes session_id in URL path', () => {
    renderWS()
    const ws = latestWS()
    expect(ws.url).toMatch(/\/api\/v1\/signals\/ws\/[a-f0-9-]+/)
  })

  it('persists session_id in localStorage', () => {
    renderWS()
    expect(localStorage.getItem('anveshak_session_id')).not.toBeNull()
  })

  it('uses ws:// for http: origin', () => {
    renderWS()
    const ws = latestWS()
    expect(ws.url).toMatch(/^ws:\/\//)
  })

  it('does not connect when not authenticated', () => {
    renderWS({ isAuthenticated: false, token: null })
    expect(MockWebSocket.instances).toHaveLength(0)
  })
})

describe('WSProvider — message handling', () => {
  it('dispatches JSON signal messages to subscribers', () => {
    renderWS()
    const ws = latestWS()
    ws.simulateOpen()

    const received: any[] = []
    subscribedHandler = (msg) => received.push(msg)

    act(() => {
      ws.simulateMessage(JSON.stringify({
        type: 'signal',
        signal_id: 'sig-1',
        topic_id: 'topic-1',
        cluster_id: null,
        signal_type: 'narrative_spike',
        created_at: '2026-05-09T12:00:00Z',
      }))
    })

    expect(received).toHaveLength(1)
    expect(received[0].signal_id).toBe('sig-1')
  })

  it('filters out ping messages', () => {
    renderWS()
    const ws = latestWS()
    ws.simulateOpen()

    const received: any[] = []
    subscribedHandler = (msg) => received.push(msg)

    act(() => {
      ws.simulateMessage(JSON.stringify({ type: 'ping' }))
    })

    expect(received).toHaveLength(0)
  })

  it('malformed JSON does not crash', () => {
    renderWS()
    const ws = latestWS()
    ws.simulateOpen()

    // Should not throw
    act(() => {
      ws.simulateMessage('not valid json {{{')
    })
  })

  it('invalidates signals query on signal message', () => {
    const { invalidateSpy } = renderWS()
    const ws = latestWS()
    ws.simulateOpen()

    act(() => {
      ws.simulateMessage(JSON.stringify({
        type: 'signal',
        signal_id: 'sig-1',
        topic_id: 'topic-1',
        cluster_id: null,
        signal_type: 'test',
        created_at: '2026-05-09T12:00:00Z',
      }))
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['signals'] })
  })
})

describe('WSProvider — reconnect (R3)', () => {
  it('schedules reconnect on close', () => {
    renderWS()
    const ws = latestWS()
    ws.simulateOpen()

    const instancesBefore = MockWebSocket.instances.length

    act(() => {
      ws.simulateClose()
    })

    // Advance past the initial 1s delay
    act(() => { vi.advanceTimersByTime(1000) })

    expect(MockWebSocket.instances.length).toBeGreaterThan(instancesBefore)
  })

  it('backoff doubles: 1s → 2s → 4s', () => {
    renderWS()

    // First connection
    let ws = latestWS()
    ws.simulateOpen()

    // First close → reconnect after 1s
    act(() => { ws.simulateClose() })
    const count1 = MockWebSocket.instances.length
    act(() => { vi.advanceTimersByTime(999) })
    expect(MockWebSocket.instances.length).toBe(count1) // not yet
    act(() => { vi.advanceTimersByTime(1) })
    expect(MockWebSocket.instances.length).toBe(count1 + 1) // now

    // Second close → reconnect after 2s
    ws = latestWS()
    act(() => { ws.simulateClose() })
    const count2 = MockWebSocket.instances.length
    act(() => { vi.advanceTimersByTime(1999) })
    expect(MockWebSocket.instances.length).toBe(count2)
    act(() => { vi.advanceTimersByTime(1) })
    expect(MockWebSocket.instances.length).toBe(count2 + 1)

    // Third close → reconnect after 4s
    ws = latestWS()
    act(() => { ws.simulateClose() })
    const count3 = MockWebSocket.instances.length
    act(() => { vi.advanceTimersByTime(3999) })
    expect(MockWebSocket.instances.length).toBe(count3)
    act(() => { vi.advanceTimersByTime(1) })
    expect(MockWebSocket.instances.length).toBe(count3 + 1)
  })

  it('resets backoff on successful reconnect', () => {
    renderWS()

    // Open, close, reconnect (uses 1s)
    let ws = latestWS()
    ws.simulateOpen()
    act(() => { ws.simulateClose() })
    act(() => { vi.advanceTimersByTime(1000) })

    // Reconnect succeeds
    ws = latestWS()
    ws.simulateOpen()

    // Close again → should use 1s (reset), not 2s
    act(() => { ws.simulateClose() })
    const countBefore = MockWebSocket.instances.length
    act(() => { vi.advanceTimersByTime(1000) })
    expect(MockWebSocket.instances.length).toBe(countBefore + 1)
  })

  it('caps backoff at 8s', () => {
    renderWS()

    // Simulate 5 close events without successful reconnect
    for (let i = 0; i < 5; i++) {
      const ws = latestWS()
      act(() => { ws.simulateClose() })
      act(() => { vi.advanceTimersByTime(10000) }) // advance well past any delay
    }

    // The next close should still cap at 8s
    const ws = latestWS()
    act(() => { ws.simulateClose() })
    const countBefore = MockWebSocket.instances.length

    act(() => { vi.advanceTimersByTime(7999) })
    expect(MockWebSocket.instances.length).toBe(countBefore)

    act(() => { vi.advanceTimersByTime(1) })
    expect(MockWebSocket.instances.length).toBe(countBefore + 1)
  })

  it('error event triggers close', () => {
    renderWS()
    const ws = latestWS()
    ws.simulateOpen()

    const closeSpy = vi.spyOn(ws, 'close')
    act(() => { ws.simulateError() })
    expect(closeSpy).toHaveBeenCalled()
  })
})

describe('WSProvider — cleanup', () => {
  it('closes WebSocket on unmount', () => {
    const { unmount } = renderWS()
    const ws = latestWS()
    ws.simulateOpen()
    const closeSpy = vi.spyOn(ws, 'close')

    unmount()
    expect(closeSpy).toHaveBeenCalled()
  })

  it('unsubscribe removes handler', () => {
    renderWS()
    const ws = latestWS()
    ws.simulateOpen()

    const received: any[] = []
    let unsub: (() => void) | undefined

    // Render a component that subscribes then unsubscribes
    function SubUnsub() {
      const { subscribe } = useWS()
      React.useEffect(() => {
        unsub = subscribe((msg: any) => received.push(msg))
      }, [subscribe])
      return null
    }

    const { unmount: unmountSub } = render(
      <QueryClientProvider client={new QueryClient()}>
        <WSProvider>
          <SubUnsub />
        </WSProvider>
      </QueryClientProvider>,
    )

    // Unsubscribe
    unsub?.()

    act(() => {
      ws.simulateMessage(JSON.stringify({
        type: 'signal',
        signal_id: 'sig-1',
        topic_id: 'topic-1',
        cluster_id: null,
        signal_type: 'test',
        created_at: '2026-05-09T12:00:00Z',
      }))
    })

    // Handler was unsubscribed so nothing should be received
    expect(received).toHaveLength(0)

    unmountSub()
  })
})
