/**
 * Reading a failed API call.
 *
 * Every route in `services/api` reports a failure as `{"detail": "..."}`, so
 * these two helpers are the only place that shape is spelled out. They take
 * `unknown` because a rejected promise carries no type, and they read the
 * error structurally rather than through `instanceof AxiosError`, since a
 * rejection can also come from a test mock or a non-axios caller.
 */

interface ApiErrorShape {
  response?: {
    status?: number
    data?: {
      detail?: string
    }
  }
}

/** The `detail` the API reported, or `fallback` when it reported none. */
export function apiErrorDetail(error: unknown, fallback: string): string {
  const detail = (error as ApiErrorShape | null | undefined)?.response?.data?.detail
  return typeof detail === 'string' && detail.length > 0 ? detail : fallback
}

/** The HTTP status the API replied with, or null when the call never got one. */
export function apiErrorStatus(error: unknown): number | null {
  const status = (error as ApiErrorShape | null | undefined)?.response?.status
  return typeof status === 'number' ? status : null
}
