# Pattern: Vitest Setup for Vite + React + TypeScript

## When to load: adding frontend tests to a Vite project for the first time

---

## The complete setup

### 1. Add deps to package.json

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "devDependencies": {
    "vitest": "^1.6.0",
    "@vitest/ui": "^1.6.0",
    "jsdom": "^24.1.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/user-event": "^14.5.0"
  }
}
```

### 2. Add test config to vite.config.ts

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // ... existing server/build config ...
  test: {
    environment: 'jsdom',
    globals: true,               // enables describe/it/expect without imports
    setupFiles: ['./src/test/setup.ts'],
  },
})
```

### 3. Create setup file

```ts
// src/test/setup.ts
import '@testing-library/jest-dom'
```

### 4. CRITICAL — exclude test files from prod tsconfig

```json
// tsconfig.json
{
  "compilerOptions": { ... },
  "include": ["src"],
  "exclude": ["src/test"]   // ← without this, tsc errors on missing vitest types
}
```

**Why:** `vitest` is a devDependency. Before `npm install` runs (and even in CI before
install), `tsc --noEmit` will fail with `Cannot find module 'vitest'` on every test file
that imports from vitest. The solution is to exclude the test directory from the production
TypeScript build. Vitest does its own type-checking using its own tsconfig during `vitest run`.

### 5. Test file structure

```
src/
  test/
    setup.ts          ← jest-dom matchers
    auth.test.ts      ← pure logic tests (no React)
    topics.test.ts
    signals.test.ts
    reports.test.ts
```

## What to test without React rendering

For a fast, zero-dep test suite, test pure logic functions without component rendering:

```ts
// Good candidates for logic-only tests
// - JWT decode/expiry logic
// - Severity inference functions
// - Data transformation helpers
// - Type guards and validators
// - Domain rule implementations (e.g. confidence badge variant logic)

import { describe, it, expect, vi } from 'vitest'

describe('inferSeverity', () => {
  it('returns HIGH for critical signal types', () => {
    expect(inferSeverity({ signal_type: 'critical_threshold' })).toBe('HIGH')
  })
})
```

## Fake timers for time-dependent logic

```ts
import { vi } from 'vitest'

it('treats exp === now as expired', () => {
  vi.useFakeTimers()
  vi.setSystemTime(1_700_000_000 * 1000)  // set wall clock
  const payload = { sub: 'u', exp: 1_700_000_000, iat: 0 }
  expect(isExpired(payload)).toBe(true)
  vi.useRealTimers()
})
```

## localStorage in tests

jsdom provides `localStorage`. Just use it directly — it resets between test files
but NOT between tests in the same file. Use `beforeEach` / `afterEach`:

```ts
beforeEach(() => localStorage.clear())
afterEach(() => localStorage.clear())
```

## Component tests — when you need them

Use `@testing-library/react` for components that have complex interaction logic:

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

test('Pause button toggles topic status', async () => {
  render(
    <MemoryRouter>
      <TopicCard topic={mockTopic} onClick={() => {}} onToggleStatus={() => {}} isToggling={false} />
    </MemoryRouter>
  )
  expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument()
})
```

Wrap with `MemoryRouter` when components use `useNavigate`.
Wrap with `QueryClientProvider` + `QueryClient` when components use `useQuery`.

## Running

```bash
npm test          # one-shot (CI)
npm run test:watch  # watch mode (dev)
```
