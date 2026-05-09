/**
 * Tests for the real AuthProvider component.
 *
 * Tests login/logout, JWT expiry countdown (R4), and session restoration.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act, fireEvent } from '@testing-library/react'
import { AuthProvider, useAuth } from '../../contexts/AuthContext'

function makeToken(payload: { sub: string; exp: number; iat: number }): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.fakesig`
}

function now(): number {
  return Math.floor(Date.now() / 1000)
}

/** Test consumer that exposes AuthContext values */
function AuthConsumer() {
  const ctx = useAuth()
  return (
    <div>
      <span data-testid="authenticated">{String(ctx.isAuthenticated)}</span>
      <span data-testid="user-sub">{ctx.user?.sub ?? 'none'}</span>
      <span data-testid="seconds">{ctx.secondsUntilExpiry ?? 'null'}</span>
      <button onClick={() => ctx.login(makeToken({
        sub: 'new-analyst',
        exp: now() + 3600,
        iat: now(),
      }))}>
        Login
      </button>
      <button onClick={ctx.logout}>Logout</button>
    </div>
  )
}

function renderAuth() {
  return render(
    <AuthProvider>
      <AuthConsumer />
    </AuthProvider>,
  )
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

describe('AuthProvider — login flow', () => {
  it('login sets isAuthenticated = true', () => {
    renderAuth()
    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')

    fireEvent.click(screen.getByText('Login'))
    act(() => { vi.advanceTimersByTime(1100) })

    expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
  })

  it('login decodes user from JWT payload', () => {
    renderAuth()
    fireEvent.click(screen.getByText('Login'))
    act(() => { vi.advanceTimersByTime(1100) })

    expect(screen.getByTestId('user-sub')).toHaveTextContent('new-analyst')
  })

  it('login stores token in localStorage', () => {
    renderAuth()
    fireEvent.click(screen.getByText('Login'))

    expect(localStorage.getItem('anveshak_token')).not.toBeNull()
  })
})

describe('AuthProvider — logout flow', () => {
  it('logout clears isAuthenticated', () => {
    const token = makeToken({ sub: 'analyst-1', exp: now() + 3600, iat: now() })
    localStorage.setItem('anveshak_token', token)

    renderAuth()
    expect(screen.getByTestId('authenticated')).toHaveTextContent('true')

    fireEvent.click(screen.getByText('Logout'))

    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
  })

  it('logout clears localStorage', () => {
    const token = makeToken({ sub: 'analyst-1', exp: now() + 3600, iat: now() })
    localStorage.setItem('anveshak_token', token)
    localStorage.setItem('anveshak_session_id', 'sess-123')

    renderAuth()
    fireEvent.click(screen.getByText('Logout'))

    expect(localStorage.getItem('anveshak_token')).toBeNull()
    expect(localStorage.getItem('anveshak_session_id')).toBeNull()
  })

  it('logout sets user to null', () => {
    const token = makeToken({ sub: 'analyst-1', exp: now() + 3600, iat: now() })
    localStorage.setItem('anveshak_token', token)

    renderAuth()
    fireEvent.click(screen.getByText('Logout'))

    expect(screen.getByTestId('user-sub')).toHaveTextContent('none')
  })
})

describe('AuthProvider — mount restoration', () => {
  it('valid token in localStorage → restores session', () => {
    const token = makeToken({ sub: 'restored-analyst', exp: now() + 3600, iat: now() })
    localStorage.setItem('anveshak_token', token)

    renderAuth()

    expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
    expect(screen.getByTestId('user-sub')).toHaveTextContent('restored-analyst')
  })

  it('expired token in localStorage → clears and starts unauthenticated', () => {
    const token = makeToken({ sub: 'old', exp: now() - 1, iat: now() - 3601 })
    localStorage.setItem('anveshak_token', token)

    renderAuth()

    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    expect(localStorage.getItem('anveshak_token')).toBeNull()
  })

  it('malformed token in localStorage → clears and starts unauthenticated', () => {
    localStorage.setItem('anveshak_token', 'not-a-jwt')

    renderAuth()

    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    expect(localStorage.getItem('anveshak_token')).toBeNull()
  })

  it('no token → starts unauthenticated', () => {
    renderAuth()

    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    expect(screen.getByTestId('user-sub')).toHaveTextContent('none')
  })
})

describe('AuthProvider — expiry countdown (R4)', () => {
  it('countdown starts at correct value', () => {
    const token = makeToken({ sub: 'analyst-1', exp: now() + 600, iat: now() })
    localStorage.setItem('anveshak_token', token)

    renderAuth()

    expect(screen.getByTestId('seconds')).toHaveTextContent('600')
  })

  it('countdown ticks every second', () => {
    const token = makeToken({ sub: 'analyst-1', exp: now() + 600, iat: now() })
    localStorage.setItem('anveshak_token', token)

    renderAuth()

    act(() => { vi.advanceTimersByTime(1000) })
    expect(screen.getByTestId('seconds')).toHaveTextContent('599')

    act(() => { vi.advanceTimersByTime(1000) })
    expect(screen.getByTestId('seconds')).toHaveTextContent('598')
  })

  it('shows warning banner at 300s before expiry', () => {
    const token = makeToken({ sub: 'analyst-1', exp: now() + 310, iat: now() })
    localStorage.setItem('anveshak_token', token)

    renderAuth()

    // At 310s remaining — no warning yet
    expect(screen.queryByRole('alertdialog')).toBeNull()

    // Advance 11 seconds → 299s remaining → warning should appear
    act(() => { vi.advanceTimersByTime(11000) })
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
  })

  it('triggers logout when countdown reaches 0', () => {
    const token = makeToken({ sub: 'analyst-1', exp: now() + 5, iat: now() })
    localStorage.setItem('anveshak_token', token)

    renderAuth()
    expect(screen.getByTestId('authenticated')).toHaveTextContent('true')

    // Advance past expiry
    act(() => { vi.advanceTimersByTime(6000) })
    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
  })
})
