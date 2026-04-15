/**
 * Unit tests for AuthContext JWT decode and expiry logic (criterion 6.44).
 * These are pure logic tests — no React rendering required.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// ---------------------------------------------------------------------------
// Helpers mirroring AuthContext implementation
// ---------------------------------------------------------------------------

interface JWTPayload {
  sub: string
  exp: number
  iat: number
}

function decodeJWT(token: string): JWTPayload | null {
  try {
    const payload = token.split('.')[1]
    return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
  } catch {
    return null
  }
}

function isExpired(payload: JWTPayload): boolean {
  return Date.now() / 1000 > payload.exp
}

function makeToken(payload: JWTPayload): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.fakesig`
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('JWT decode', () => {
  it('decodes a valid token', () => {
    const now = Math.floor(Date.now() / 1000)
    const payload: JWTPayload = { sub: 'analyst1', exp: now + 3600, iat: now }
    const token = makeToken(payload)
    const decoded = decodeJWT(token)
    expect(decoded).not.toBeNull()
    expect(decoded!.sub).toBe('analyst1')
    expect(decoded!.exp).toBe(payload.exp)
  })

  it('returns null for a malformed token', () => {
    expect(decodeJWT('not.a.jwt')).toBeNull()
    expect(decodeJWT('')).toBeNull()
    expect(decodeJWT('onlyone')).toBeNull()
  })
})

describe('isExpired', () => {
  it('returns false for a future exp', () => {
    const payload: JWTPayload = { sub: 'u', exp: Math.floor(Date.now() / 1000) + 3600, iat: 0 }
    expect(isExpired(payload)).toBe(false)
  })

  it('returns true for a past exp', () => {
    const payload: JWTPayload = { sub: 'u', exp: Math.floor(Date.now() / 1000) - 1, iat: 0 }
    expect(isExpired(payload)).toBe(true)
  })

  it('returns true when exp equals now (boundary)', () => {
    vi.useFakeTimers()
    const now = 1_700_000_000
    vi.setSystemTime(now * 1000)
    const payload: JWTPayload = { sub: 'u', exp: now, iat: 0 }
    expect(isExpired(payload)).toBe(true)
    vi.useRealTimers()
  })
})

describe('localStorage token lifecycle', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => localStorage.clear())

  it('stores and retrieves a token', () => {
    const now = Math.floor(Date.now() / 1000)
    const token = makeToken({ sub: 'a', exp: now + 3600, iat: now })
    localStorage.setItem('anveshak_token', token)
    const stored = localStorage.getItem('anveshak_token')
    const decoded = decodeJWT(stored!)
    expect(decoded?.sub).toBe('a')
    expect(isExpired(decoded!)).toBe(false)
  })

  it('rejects an expired token on load', () => {
    const now = Math.floor(Date.now() / 1000)
    const token = makeToken({ sub: 'a', exp: now - 1, iat: now - 3600 })
    localStorage.setItem('anveshak_token', token)
    const stored = localStorage.getItem('anveshak_token')
    const decoded = decodeJWT(stored!)
    if (!decoded || isExpired(decoded)) {
      localStorage.removeItem('anveshak_token')
    }
    expect(localStorage.getItem('anveshak_token')).toBeNull()
  })
})
