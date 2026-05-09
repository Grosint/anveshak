/**
 * Integration tests for auth data flow seams:
 *
 * Seam 3: Login → AuthContext → authenticated state
 * Seam 4: 401 interceptor → localStorage clear → AuthContext
 * Seam 11: AuthContext expiry → WSContext disconnect
 *
 * Tests the full flow: user action → context state change → downstream effect.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { AuthProvider, useAuth } from '../../contexts/AuthContext'

function makeToken(sub: string, expInSeconds: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const payload = btoa(JSON.stringify({
    sub,
    exp: Math.floor(Date.now() / 1000) + expInSeconds,
    iat: Math.floor(Date.now() / 1000),
  }))
  return `${header}.${payload}.fakesig`
}

beforeEach(() => {
  localStorage.clear()
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-05-09T12:00:00Z'))
})

afterEach(() => {
  localStorage.clear()
  vi.useRealTimers()
})

// ── Seam 3: Login → AuthContext → localStorage → API client ─────────────

describe('Seam 3: Login → AuthContext → downstream', () => {
  it('login stores token → AuthContext reads it → API client can access it', () => {
    // Simulate what Login page does: call login() with a valid token
    function LoginSimulator() {
      const { login, isAuthenticated, token } = useAuth()
      return (
        <div>
          <span data-testid="auth">{String(isAuthenticated)}</span>
          <span data-testid="has-token">{String(!!token)}</span>
          <button onClick={() => login(makeToken('analyst-1', 3600))}>Login</button>
        </div>
      )
    }

    render(<AuthProvider><LoginSimulator /></AuthProvider>)

    expect(screen.getByTestId('auth')).toHaveTextContent('false')

    // Login
    act(() => { screen.getByText('Login').click() })
    act(() => { vi.advanceTimersByTime(1100) })

    // AuthContext has the token
    expect(screen.getByTestId('auth')).toHaveTextContent('true')
    expect(screen.getByTestId('has-token')).toHaveTextContent('true')

    // localStorage has the token (API client reads this for Bearer header)
    expect(localStorage.getItem('anveshak_token')).not.toBeNull()
  })

  it('login with nearly-expired token → authenticates but warns quickly', () => {
    function ExpiryTest() {
      const { login, isAuthenticated, secondsUntilExpiry } = useAuth()
      return (
        <div>
          <span data-testid="auth">{String(isAuthenticated)}</span>
          <span data-testid="secs">{secondsUntilExpiry ?? 'null'}</span>
          <button onClick={() => login(makeToken('analyst-1', 200))}>Login</button>
        </div>
      )
    }

    render(<AuthProvider><ExpiryTest /></AuthProvider>)
    act(() => { screen.getByText('Login').click() })
    act(() => { vi.advanceTimersByTime(1100) })

    expect(screen.getByTestId('auth')).toHaveTextContent('true')
    // Less than WARN_BEFORE_EXPIRY_S (300), so warning should show soon
    expect(Number(screen.getByTestId('secs').textContent)).toBeLessThanOrEqual(200)
  })
})

// ── Seam 4: 401 → localStorage clear → AuthContext on next mount ────────

describe('Seam 4: 401 → localStorage → AuthContext', () => {
  it('cleared localStorage causes AuthContext to start unauthenticated on remount', () => {
    // Step 1: Simulate a session with a valid token
    const token = makeToken('analyst-1', 3600)
    localStorage.setItem('anveshak_token', token)

    function StatusDisplay() {
      const { isAuthenticated } = useAuth()
      return <span data-testid="auth">{String(isAuthenticated)}</span>
    }

    const { unmount } = render(<AuthProvider><StatusDisplay /></AuthProvider>)
    expect(screen.getByTestId('auth')).toHaveTextContent('true')
    unmount()

    // Step 2: Simulate what the 401 interceptor does
    localStorage.removeItem('anveshak_token')
    localStorage.removeItem('anveshak_session_id')

    // Step 3: Remount AuthProvider (simulates navigating to /login then back)
    render(<AuthProvider><StatusDisplay /></AuthProvider>)
    expect(screen.getByTestId('auth')).toHaveTextContent('false')
  })
})

// ── Seam 11: Auth expiry → downstream effects ──────────────────────────

describe('Seam 11: Auth expiry → session teardown', () => {
  it('expired token triggers logout → clears all session state', () => {
    const token = makeToken('analyst-1', 3) // expires in 3 seconds
    localStorage.setItem('anveshak_token', token)
    localStorage.setItem('anveshak_session_id', 'sess-123')

    function SessionState() {
      const { isAuthenticated, user } = useAuth()
      return (
        <div>
          <span data-testid="auth">{String(isAuthenticated)}</span>
          <span data-testid="user">{user?.sub ?? 'none'}</span>
        </div>
      )
    }

    render(<AuthProvider><SessionState /></AuthProvider>)
    expect(screen.getByTestId('auth')).toHaveTextContent('true')

    // Advance past expiry
    act(() => { vi.advanceTimersByTime(4000) })

    expect(screen.getByTestId('auth')).toHaveTextContent('false')
    expect(screen.getByTestId('user')).toHaveTextContent('none')
    expect(localStorage.getItem('anveshak_token')).toBeNull()
    expect(localStorage.getItem('anveshak_session_id')).toBeNull()
  })

  it('session warning appears then logout fires if not dismissed', () => {
    const token = makeToken('analyst-1', 295) // 295 seconds, under 300 warning threshold
    localStorage.setItem('anveshak_token', token)

    function WarningTest() {
      const { isAuthenticated } = useAuth()
      return <span data-testid="auth">{String(isAuthenticated)}</span>
    }

    render(<AuthProvider><WarningTest /></AuthProvider>)

    // Warning should appear immediately (295 < 300)
    act(() => { vi.advanceTimersByTime(1100) })
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()

    // Advance to expiry
    act(() => { vi.advanceTimersByTime(295000) })
    expect(screen.getByTestId('auth')).toHaveTextContent('false')
  })
})
