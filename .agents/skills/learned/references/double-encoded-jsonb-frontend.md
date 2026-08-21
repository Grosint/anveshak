---
name: double-encoded-jsonb-frontend
description: JSONB columns can arrive as double-encoded strings in the frontend; always parse defensively
type: pitfall
---

# Double-Encoded JSONB in Frontend

## Problem
Backend stores `json.dumps(dict)` into a JSONB column. asyncpg returns it as a Python dict,
but FastAPI serialises it again → frontend receives `'"{\"key\": \"value\"}"'` (string of string).

This causes:
- `Object.entries(details)` iterates over individual characters: `{0: "{", 1: "\"", ...}`
- Audit trail modal showing `4: d`, `5: _`, `6: s` instead of key-value pairs
- `.get()` on a string throws `'str object' has no attribute 'get'` (Jinja2 PDF crash)

## Solution
Parse defensively — check if result is still a string after first parse:

```typescript
function parseDetails(raw: unknown): Record<string, unknown> {
  if (!raw) return {}
  if (typeof raw === 'object' && !Array.isArray(raw)) return raw
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      if (typeof parsed === 'string') {
        try { return JSON.parse(parsed) } catch { return {} }
      }
      return typeof parsed === 'object' && parsed !== null ? parsed : {}
    } catch { return {} }
  }
  return {}
}
```

Python equivalent (used in reporter PDF):
```python
def _parse_labels(labels):
    if isinstance(labels, dict): return labels
    if isinstance(labels, str):
        parsed = json.loads(labels)
        return json.loads(parsed) if isinstance(parsed, str) else parsed
    return {}
```

## Where it bit us
- `audit_trail.details` — modal showed individual chars
- `reports.labels` — PDF generation crashed with Jinja2 UndefinedError
- `reports.source_snapshot` — same pattern

## Rule
Every JSONB field consumed in frontend or Jinja2 templates MUST go through a
double-decode-safe parser. Never assume the ORM/driver returns a dict.
