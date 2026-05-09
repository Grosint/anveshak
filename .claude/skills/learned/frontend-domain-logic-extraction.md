# Frontend Domain Logic Extraction

## Problem
Business logic embedded inside React components can't be imported by tests.
Tests re-implement the logic inline, creating drift: the test passes but tests
different code than the component uses.

Example: `inferSeverity` was defined inside `SignalCard.tsx` (checks
`independent_source_count` first), but `signals.test.ts` re-implemented it
with only string matching. Test passed, behavior was wrong.

## Solution
Extract all pure business logic functions into `src/lib/domain.ts`:
- `inferSeverity`, `confidenceVariant`, `credibilityLabel`, `deepfakeLabel`
- `resolveTimeRange`, `applyClientFilters`

Components import from `lib/domain.ts`. Tests import the same functions.
Zero drift possible.

## When to apply
Any time a React component contains a pure function (no hooks, no JSX) that
has non-trivial logic worth testing. If you'd copy-paste the function into a
test file to test it — extract it instead.

## Anti-pattern
```tsx
// BAD: function defined inside component, tested via inline copy
function SignalCard({ signal }) {
  function inferSeverity(s) { /* logic */ }
  // ...
}

// test.ts
function inferSeverity(s) { /* DIFFERENT logic */ }  // drift!
```

## Correct pattern
```tsx
// lib/domain.ts — single source of truth
export function inferSeverity(signal: Signal): string { /* logic */ }

// SignalCard.tsx
import { inferSeverity } from '../../lib/domain'

// test.ts
import { inferSeverity } from '../lib/domain'  // same function!
```
