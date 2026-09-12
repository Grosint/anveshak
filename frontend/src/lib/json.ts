/**
 * Parsing JSON that arrived without a type.
 *
 * JSONB columns reach the frontend double-encoded: asyncpg hands the API a
 * string, the API serialises it again, and the browser then sees a string
 * holding a string. `JSON.parse` returns `any` either way, so nothing past
 * this module handles a raw parse result.
 *
 * See: frontend/AGENTS.md, "JSONB double-encoding".
 */

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/**
 * `raw` as an object, unwrapping up to one extra layer of JSON encoding.
 *
 * Returns an empty object for null, malformed JSON, or a value that parses to
 * something other than an object, so a call site can read fields without a
 * try/catch.
 */
export function parseJsonObject(raw: unknown): Record<string, unknown> {
  if (isRecord(raw)) return raw
  if (typeof raw !== 'string') return {}
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return {}
  }
  if (typeof parsed === 'string') {
    try {
      parsed = JSON.parse(parsed)
    } catch {
      return {}
    }
  }
  return isRecord(parsed) ? parsed : {}
}
