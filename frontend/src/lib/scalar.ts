/**
 * Rendering a JSON value the type system only knows as `unknown`.
 *
 * GeoJSON feature properties, JSONB audit details and other pass-through
 * payloads arrive untyped. Interpolating one straight into a template gives
 * `[object Object]` for anything that is not a scalar, so every such value
 * goes through one of these first.
 */

/** `value` as text, or `fallback` when it is not a JSON scalar. */
export function asText(value: unknown, fallback = ''): string {
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return fallback
}

/** `value` as a finite number, or `fallback` when it is not one. */
export function asNumber(value: unknown, fallback = 0): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return fallback
}
