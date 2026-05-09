# Mock Shape Unwrap Mismatch (R5)

## Problem
Frontend API functions do `.then(r => r.data)` internally, returning the
unwrapped response. But test mocks were returning `{ data: [] }` — the
pre-unwrap shape. Tests passed because the component received `{ data: [] }`
(an object, truthy) but the component expected `[]` (an array).

This is the frontend equivalent of the backend's "both sides have 100%
coverage but the seam is broken" bug.

## How it manifests
```ts
// Real API client:
list: () => api.get<Signal[]>('/api/v1/signals').then(r => r.data)
// Returns: Signal[]

// BAD mock:
vi.mock('../../api/signals', () => ({
  signalsApi: { list: vi.fn().mockResolvedValue({ data: [] }) }
}))
// Returns: { data: [] } — NOT what the component expects!

// GOOD mock:
vi.mock('../../api/signals', () => ({
  signalsApi: { list: vi.fn().mockResolvedValue([]) }
}))
// Returns: [] — matches real behavior
```

## Prevention
1. Create mock factories in `test/mocks/api.ts` with correct shapes
2. Add a contract test: `expect(makeSignal()).not.toHaveProperty('data')`
3. Rule: if the real API function has `.then(r => r.data)`, mock must return
   the inner shape, not the axios response wrapper
