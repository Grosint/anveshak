/**
 * Tests for the axios API client (src/api/client.ts).
 *
 * Tests the request interceptor (JWT injection) and response interceptor (401 handler).
 * This is the most critical untested infrastructure — R1 risk.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// We need to test the interceptor behavior directly.
// The module creates the axios instance and registers interceptors at import time.
// We mock axios to capture the interceptor functions.

let requestInterceptor: (config: any) => any
let responseSuccessInterceptor: (res: any) => any
let responseErrorInterceptor: (err: any) => any

vi.mock('axios', () => {
  const interceptors = {
    request: {
      use: vi.fn((fn: any) => {
        requestInterceptor = fn
      }),
    },
    response: {
      use: vi.fn((successFn: any, errorFn: any) => {
        responseSuccessInterceptor = successFn
        responseErrorInterceptor = errorFn
      }),
    },
  }

  return {
    default: {
      create: vi.fn(() => ({
        interceptors,
        get: vi.fn(),
        post: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
      })),
    },
  }
})

// Force module evaluation to register interceptors
beforeEach(async () => {
  vi.resetModules()
  localStorage.clear()
  await import('../../api/client')
})

afterEach(() => {
  localStorage.clear()
})

describe('Request interceptor', () => {
  it('attaches Authorization header when token exists', () => {
    localStorage.setItem('anveshak_token', 'my-jwt-token')
    const config = { headers: {} as Record<string, string> }
    const result = requestInterceptor(config)
    expect(result.headers.Authorization).toBe('Bearer my-jwt-token')
  })

  it('does not attach header when no token', () => {
    const config = { headers: {} as Record<string, string> }
    const result = requestInterceptor(config)
    expect(result.headers.Authorization).toBeUndefined()
  })

  it('uses Bearer prefix', () => {
    localStorage.setItem('anveshak_token', 'xyz')
    const config = { headers: {} as Record<string, string> }
    const result = requestInterceptor(config)
    expect(result.headers.Authorization).toMatch(/^Bearer /)
  })
})

describe('Response interceptor', () => {
  it('passes through successful responses', () => {
    const response = { status: 200, data: { ok: true } }
    expect(responseSuccessInterceptor(response)).toBe(response)
  })

  describe('401 handler (R1)', () => {
    let originalHref: string

    beforeEach(() => {
      localStorage.setItem('anveshak_token', 'will-be-cleared')
      localStorage.setItem('anveshak_session_id', 'sess-123')
      originalHref = window.location.href

      // Mock window.location.href setter
      Object.defineProperty(window, 'location', {
        writable: true,
        value: { ...window.location, href: originalHref },
      })
    })

    it('clears anveshak_token from localStorage', async () => {
      const err = { response: { status: 401 } }
      await expect(responseErrorInterceptor(err)).rejects.toBe(err)
      expect(localStorage.getItem('anveshak_token')).toBeNull()
    })

    it('clears anveshak_session_id from localStorage', async () => {
      const err = { response: { status: 401 } }
      await expect(responseErrorInterceptor(err)).rejects.toBe(err)
      expect(localStorage.getItem('anveshak_session_id')).toBeNull()
    })

    it('redirects to /login', async () => {
      const err = { response: { status: 401 } }
      await expect(responseErrorInterceptor(err)).rejects.toBe(err)
      expect(window.location.href).toBe('/login')
    })

    it('still rejects the promise (callers get the error too)', async () => {
      const err = { response: { status: 401 } }
      await expect(responseErrorInterceptor(err)).rejects.toBe(err)
    })
  })

  it('403 does NOT trigger logout/redirect', async () => {
    localStorage.setItem('anveshak_token', 'should-remain')
    const err = { response: { status: 403 } }
    await expect(responseErrorInterceptor(err)).rejects.toBe(err)
    expect(localStorage.getItem('anveshak_token')).toBe('should-remain')
  })

  it('500 propagates error without side effects', async () => {
    localStorage.setItem('anveshak_token', 'should-remain')
    const err = { response: { status: 500 } }
    await expect(responseErrorInterceptor(err)).rejects.toBe(err)
    expect(localStorage.getItem('anveshak_token')).toBe('should-remain')
  })

  it('network error (no response object) propagates without crash', async () => {
    const err = { message: 'Network Error' }
    await expect(responseErrorInterceptor(err)).rejects.toBe(err)
  })
})
