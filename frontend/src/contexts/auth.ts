/**
 * Auth context object, hook and JWT helpers.
 *
 * Separate from `AuthContext.tsx` so that file exports only the provider
 * component, which is what Vite's fast refresh needs to hot-swap it.
 */
import { createContext, useContext } from 'react'
import { parseJsonObject } from '../lib/json'

export interface JWTPayload {
  sub: string
  username?: string
  role?: string
  org_id?: string
  exp: number
  iat: number
}

export interface AuthContextValue {
  user: JWTPayload | null
  token: string | null
  isAuthenticated: boolean
  /** Seconds until token expiry, null when not authenticated */
  secondsUntilExpiry: number | null
  login: (token: string) => void
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function decodeJWT(token: string): JWTPayload | null {
  let decoded: Record<string, unknown>
  try {
    const payload = token.split('.')[1]
    decoded = parseJsonObject(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
  } catch {
    // atob throws on a segment that is not valid base64.
    return null
  }
  // sub, exp and iat are what the app reads; a token missing one is unusable.
  if (
    typeof decoded.sub !== 'string' ||
    typeof decoded.exp !== 'number' ||
    typeof decoded.iat !== 'number'
  ) {
    return null
  }
  return {
    sub: decoded.sub,
    exp: decoded.exp,
    iat: decoded.iat,
    username: typeof decoded.username === 'string' ? decoded.username : undefined,
    role: typeof decoded.role === 'string' ? decoded.role : undefined,
    org_id: typeof decoded.org_id === 'string' ? decoded.org_id : undefined,
  }
}

export function isExpired(payload: JWTPayload): boolean {
  return Date.now() / 1000 >= payload.exp
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
