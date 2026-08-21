# Characterization Testing for Existing Frontend Code

## Problem
TDD is for building NEW features (write test → fail → implement → pass).
When the code already exists and works in production, TDD is wrong — you
don't know what the code does until you read it. Writing a test that
"should" pass before reading the code risks encoding your assumptions,
not the actual behavior.

## Solution: Characterization Testing
1. Read the code — understand what it ACTUALLY does
2. Write tests that pin the current behavior — including bugs
3. Mark known bugs explicitly: `test('BUG R2: defaults to HIGH for unknown types')`
4. Fix bugs separately — with the safety net already in place

## When to use
- Adding tests to existing, working frontend code
- Auditing test quality (41 of 45 existing tests were hollow)
- Building a safety net before refactoring

## When NOT to use
- New feature development → use TDD
- Extracting a function from a component to `lib/domain.ts` → TDD the extraction

## Bug documentation pattern
```ts
it('BUG R2: defaults to HIGH for unknown signal types — should be LOW', () => {
  // Documents the bug, pins current behavior, prevents regression
  // if someone fixes it without updating the test
  expect(inferSeverity(makeSignal({
    independent_source_count: 0,
    signal_type: 'narrative_spike'
  }))).toBe('HIGH')
})
```

## Hollow test detection
A test is hollow if it passes regardless of component behavior:
- `expect(document.body).toBeTruthy()` — always true
- `expect(text.length).toBeGreaterThan(0)` — any render passes
- `expect(container.firstChild).toBeTruthy()` — any element passes

Replace with: `screen.getByText('specific text')` or `screen.getByRole('button', { name: /specific/i })`
