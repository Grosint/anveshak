import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react'

interface JWTPayload {
  sub: string
  username?: string
  role?: string
  exp: number
  iat: number
}

interface AuthContextValue {
  user: JWTPayload | null
  token: string | null
  isAuthenticated: boolean
  /** Seconds until token expiry, null when not authenticated */
  secondsUntilExpiry: number | null
  login: (token: string) => void
  logout: () => void
}

export function decodeJWT(token: string): JWTPayload | null {
  try {
    const payload = token.split('.')[1]
    return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
  } catch {
    return null
  }
}

export function isExpired(payload: JWTPayload): boolean {
  return Date.now() / 1000 >= payload.exp
}

function loadInitial(): { user: JWTPayload | null; token: string | null } {
  const token = localStorage.getItem('anveshak_token')
  if (!token) return { user: null, token: null }
  const payload = decodeJWT(token)
  if (!payload || isExpired(payload)) {
    localStorage.removeItem('anveshak_token')
    return { user: null, token: null }
  }
  return { user: payload, token }
}

const AuthContext = createContext<AuthContextValue | null>(null)

/** Warn the analyst 5 minutes before token expires */
const WARN_BEFORE_EXPIRY_S = 300

export function AuthProvider({ children }: { children: ReactNode }) {
  const initial = loadInitial()
  const [user, setUser] = useState<JWTPayload | null>(initial.user)
  const [token, setToken] = useState<string | null>(initial.token)
  const [secondsUntilExpiry, setSecondsUntilExpiry] = useState<number | null>(
    initial.user ? Math.max(0, initial.user.exp - Math.floor(Date.now() / 1000)) : null,
  )
  const [showExpiryWarning, setShowExpiryWarning] = useState(false)

  const login = useCallback((newToken: string) => {
    const payload = decodeJWT(newToken)
    if (payload && !isExpired(payload)) {
      localStorage.setItem('anveshak_token', newToken)
      setToken(newToken)
      setUser(payload)
      setShowExpiryWarning(false)
    }
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('anveshak_token')
    localStorage.removeItem('anveshak_session_id')
    setToken(null)
    setUser(null)
    setSecondsUntilExpiry(null)
    setShowExpiryWarning(false)
  }, [])

  // Runtime expiry countdown — ticks every second while authenticated
  useEffect(() => {
    if (!user) return

    const tick = () => {
      const secs = Math.max(0, user.exp - Math.floor(Date.now() / 1000))
      setSecondsUntilExpiry(secs)
      if (secs === 0) {
        logout()
        return
      }
      if (secs <= WARN_BEFORE_EXPIRY_S) {
        setShowExpiryWarning(true)
      }
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [user, logout])

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated: !!user, secondsUntilExpiry, login, logout }}>
      {children}
      {showExpiryWarning && secondsUntilExpiry !== null && secondsUntilExpiry > 0 && (
        <div
          role="alertdialog"
          aria-modal="true"
          aria-label="Session expiry warning"
          className="fixed inset-0 z-50 flex items-end justify-center p-4 pointer-events-none"
        >
          <div className="bg-anveshak-card border border-signal-high/60 rounded-lg shadow-lg px-5 py-4 max-w-sm w-full pointer-events-auto animate-fade-in">
            <p className="text-sm font-semibold text-signal-high mb-1">Session expiring soon</p>
            <p className="text-xs text-text-muted mb-3">
              Your session expires in{' '}
              <span className="font-mono text-text-primary">
                {Math.floor(secondsUntilExpiry / 60)}m {secondsUntilExpiry % 60}s
              </span>
              . Save your work and re-login to continue.
            </p>
            <div className="flex gap-2">
              <button
                onClick={logout}
                className="flex-1 px-3 py-1.5 text-xs rounded border border-anveshak-border text-text-muted hover:border-anveshak-accent transition-colors"
              >
                Log out now
              </button>
              <button
                onClick={() => setShowExpiryWarning(false)}
                className="flex-1 px-3 py-1.5 text-xs rounded bg-anveshak-accent text-white hover:bg-anveshak-accent/80 transition-colors"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
