# Pattern: JWT Expiry Countdown with Re-login Warning

## When to load: implementing session awareness in any React app that uses JWT auth

---

## The problem

JWT tokens expire silently. The analyst is mid-workflow when API calls start returning 401.
The 401 interceptor redirects to login — losing all in-progress work.

Good UX: warn the analyst 5 minutes before expiry so they can finish their task and log in
again before the session dies.

## The pattern

```tsx
// contexts/AuthContext.tsx

const WARN_BEFORE_EXPIRY_S = 300  // 5 minutes

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<JWTPayload | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [secondsUntilExpiry, setSecondsUntilExpiry] = useState<number | null>(null)
  const [showExpiryWarning, setShowExpiryWarning] = useState(false)

  // 1s countdown — fires as long as user is authenticated
  useEffect(() => {
    if (!user) return

    const tick = () => {
      const secs = Math.max(0, user.exp - Math.floor(Date.now() / 1000))
      setSecondsUntilExpiry(secs)
      if (secs === 0) { logout(); return }
      if (secs <= WARN_BEFORE_EXPIRY_S) setShowExpiryWarning(true)
    }

    tick()  // run immediately so UI shows current value
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [user, logout])

  return (
    <AuthContext.Provider value={{ user, token, secondsUntilExpiry, login, logout, isAuthenticated: !!user }}>
      {children}

      {/* Warning toast — renders in-tree so it always shows above content */}
      {showExpiryWarning && secondsUntilExpiry !== null && secondsUntilExpiry > 0 && (
        <div role="alertdialog" aria-modal="true" className="fixed inset-0 z-50 flex items-end justify-center p-4 pointer-events-none">
          <div className="bg-anveshak-card border border-signal-high/60 rounded-lg px-5 py-4 max-w-sm w-full pointer-events-auto">
            <p className="text-sm font-semibold text-signal-high">Session expiring soon</p>
            <p className="text-xs text-text-muted mt-1">
              {Math.floor(secondsUntilExpiry / 60)}m {secondsUntilExpiry % 60}s remaining
            </p>
            <div className="flex gap-2 mt-3">
              <button onClick={logout}>Log out now</button>
              <button onClick={() => setShowExpiryWarning(false)}>Dismiss</button>
            </div>
          </div>
        </div>
      )}
    </AuthContext.Provider>
  )
}
```

## On load — reject already-expired tokens

```tsx
function loadInitial(): { user: JWTPayload | null; token: string | null } {
  const token = localStorage.getItem('anveshak_token')
  if (!token) return { user: null, token: null }
  const payload = decodeJWT(token)
  if (!payload || payload.exp < Date.now() / 1000) {
    localStorage.removeItem('anveshak_token')
    return { user: null, token: null }
  }
  return { user: payload, token }
}
```

## JWT decode — no library required

```tsx
function decodeJWT(token: string): JWTPayload | null {
  try {
    const payload = token.split('.')[1]
    // Handle URL-safe Base64: - → +, _ → /
    return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
  } catch {
    return null
  }
}
```

## Key decisions

| Decision | Why |
|----------|-----|
| `setInterval(tick, 1000)` | Countdown updates every second — matches wall clock |
| `Math.max(0, ...)` | Prevents negative values if browser tab is backgrounded |
| `logout()` at `secs === 0` | Auto-logout, never let an expired token linger in state |
| Warning at `WARN_BEFORE_EXPIRY_S = 300` | 5 minutes gives analyst time to finish a thought |
| `useEffect` depends on `[user]` | Restarts countdown when user re-logs in with a new token |
| Rendered inside `AuthProvider` | Warning always shows regardless of which page is active |
| `role="alertdialog"` | Screen readers announce the warning |

## Context interface — expose `secondsUntilExpiry` for components that want it

```tsx
interface AuthContextValue {
  user: JWTPayload | null
  token: string | null
  isAuthenticated: boolean
  secondsUntilExpiry: number | null  // null when not authenticated
  login: (token: string) => void
  logout: () => void
}
```

Example use: show a "Session: 4m 23s" indicator in the sidebar header.
